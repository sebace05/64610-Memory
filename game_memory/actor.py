"""Fresh per-turn action prompts with at most one output-repair attempt."""

import json
from collections.abc import Iterable

from .components import Message, Model
from .contracts import AgentView


PROMPT_VERSIONS = ("v1", "v2", "v2-mechanics", "v3")

APPLIANCE_RULES = (
    "CookingWorld appliance rules: the stove fries, the oven roasts, and the toaster "
    "grills. Match the recipe's required cooking method exactly when choosing a "
    "'cook ... in ...' command. A legal cooking action can still ruin a required "
    "ingredient and end the game."
)

MECHANICS_PRIMER = (
    "Game mechanics: To prepare a meal, all required ingredients must be in your "
    "inventory at the same time, with the recipe's required preparation completed. "
    "Ingredients on a surface or in another container are not carried. Putting an "
    "ingredient down removes it from your inventory. This experiment has unlimited "
    "inventory: you do not need to put down one item to carry another. Return to "
    "the kitchen with the ingredients. Choose 'prepare meal' when available, then "
    "'eat meal' when available."
)


def validate_action_output(text: str, allowed_actions: Iterable[str] | None) -> tuple[str | None, str | None]:
    """Return proposed/canonical action and a reason, without selecting a fallback.

    ``allowed_actions=None`` supports offline syntax analysis when a trace has
    no preceding public view; it must not be used by the actor.
    """
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return None, "malformed_json"
    action = parsed.get("action") if isinstance(parsed, dict) else None
    if not isinstance(action, str):
        return None, "invalid_action_schema"
    if allowed_actions is None:
        return action, "availability_unknown"
    allowed = {" ".join(a.lower().split()): a for a in allowed_actions}
    normalized = " ".join(action.lower().split())
    if normalized not in allowed:
        return action, "unavailable_action"
    return allowed[normalized], None


def _progress_instructions(context_name: str) -> str:
    # General mechanics only: no seed-specific ingredient, location, or path.
    return (
        "Complete the cooking goal: gather the required ingredients, follow the recipe's "
        "preparation directions, prepare the meal, and eat it. Choose one action using "
        f"only the current observation and supplied {context_name}. "
        "Use that evidence to track your current location, currently carried items, "
        "and remaining prerequisites. An item you put down is no longer carried. "
        "Keep required ingredients available for preparation; avoid putting them down "
        "unless the task requires it. "
        "Copy an exact command from the current allowed_actions list. A recipe naming "
        "an ingredient does not mean it can currently be taken. If a required item "
        "is unavailable here, use permitted movement or container actions to search "
        "for it or satisfy prerequisites. Do not assume an unobserved item's location. "
        "The initial recipe was provided once at reset. Read or examine the cookbook "
        "when needed details are missing or uncertain in the supplied context and "
        "recovering them justifies the stated cost. Repeating a known observation "
        "does not gather missing ingredients; prefer a goal-advancing action when "
        "another identical observation would add no useful information. "
        "Choose an affordable action: recipe rereads cost recheck_cost and other "
        "actions cost 1. Use budget_remaining to assess affordability. "
        'Return only a JSON object of the form {"action": "exact permitted action"}.'
    )


class PromptedActor:
    """Build action requests; the supplied model determines the actual behavior."""

    def __init__(self, *, full_history: bool = False, prompt_version: str = "v1") -> None:
        if prompt_version not in PROMPT_VERSIONS:
            raise ValueError(f"prompt_version must be one of {PROMPT_VERSIONS}")
        self.full_history = full_history
        self.prompt_version = prompt_version

    @property
    def metadata(self) -> dict:
        prefix = "full-history" if self.full_history else "s2-action"
        metadata = {"implementation": "PromptedActor",
                "prompt_version": f"{prefix}-{self.prompt_version}",
                "context_mode": "full_history" if self.full_history else "bounded_memory",
                "max_repairs": 1, "is_fake": False}
        if self.prompt_version in ("v2-mechanics", "v3"):
            metadata["requires_unlimited_inventory"] = True
        return metadata

    def choose_action(self, view: AgentView, memory: str, model: Model) -> str:
        # This list is local to this call. No persistent chat or past observations.
        context_name = "visible interaction history" if self.full_history else "memory"
        context_header = ("\nVisible interaction history (diagnostic):\n" if self.full_history
                          else "\nBounded memory:\n")
        instructions = ("Choose one permitted game action using only the current "
                    f"observation and {context_name}. Recipe rereads consume the stated budget. "
                    'Return only a JSON object of the form {"action": "exact permitted action"}.')
        if self.prompt_version != "v1":
            instructions = _progress_instructions(context_name)
        if self.prompt_version in ("v2-mechanics", "v3"):
            instructions = MECHANICS_PRIMER + "\n\n" + instructions
        if self.prompt_version == "v3":
            instructions = APPLIANCE_RULES + "\n\n" + instructions
        messages = (
            Message("system", instructions),
            # Serialize the public view, then append memory literally. Encoding
            # memory as a JSON string again would add escaping beyond its bound.
            Message("user", "Current game input:\n" + json.dumps({
                "observation": view.observation,
                "goal": view.goal,
                "allowed_actions": view.allowed_actions,
                "budget_remaining": view.budget_remaining,
                "recheck_cost": view.recheck_cost,
            }, sort_keys=True) + context_header + memory),
        )
        # Normalize for matching, but return the engine's canonical command text.
        # Two generations maximum: one original response and one repair.
        # Repairs use inference resources, but are not additional game actions.
        for attempt in range(2):
            generation = model.generate(
                messages, purpose="action" if attempt == 0 else "action_repair"
            )
            action, reason = validate_action_output(generation.text, view.allowed_actions)
            if reason is None:
                return action
            if attempt == 0:
                # Add feedback only within this turn. The next choose_action()
                # call starts over, so this exchange cannot carry hidden memory.
                feedback = ("The output was malformed or not a permitted action. "
                            "Return only the required JSON with one permitted action.")
                if self.prompt_version != "v1":
                    if reason == "malformed_json":
                        feedback = "Your response is not valid JSON. Remove commentary and code fences. "
                    elif reason == "invalid_action_schema":
                        feedback = "Your JSON must be an object whose action field is a string. "
                    else:
                        feedback = (
                            f"The requested action {json.dumps(action)} is not in the current allowed_actions. "
                            "Availability depends on the current location, open containers, and carried items. "
                            "If an ingredient cannot be taken here, choose a permitted exploratory or "
                            "prerequisite action rather than repeating the unavailable command. "
                        )
                    feedback += (
                        "Use only the same supplied observation and context. Select an exact current "
                        "allowed action that advances the cooking goal and fits budget_remaining; "
                        "recipe rereads cost recheck_cost and other actions cost 1. "
                        'Return only {"action": "exact permitted action"}.'
                    )
                messages = (*messages, Message("assistant", generation.text), Message("user", feedback))
        # Ensure malformed text cannot accidentally be interpreted as a legal
        # command after repair failed. The wrapper charges this invalid attempt.
        return "[INVALID_ACTION_OUTPUT] " + generation.text
