"""Fresh per-turn action prompts with at most one output-repair attempt."""
import json
from collections.abc import Iterable
from .contracts import AgentView
from .components import Message, Model, FINALIZATION_REPAIR_POLICY


PROMPT_VERSIONS = ('v31',)
ORDERED_PREREQUISITE_RULE = (
    "Your goal is to prepare and eat the meal. Use only the public view and "
    "bounded memory. Choose the earliest unfinished recipe direction. First "
    "check whether its ingredient is carried; if missing, find or take it. "
    "Next check required equipment: grilling uses toaster, roasting uses oven, "
    "frying uses stove, slicing and chopping require a carried knife. Take a "
    "visible required tool when needed. If all prerequisites are met, choose "
    "the exact allowed action for that direction. Return JSON with "
    "next_direction, missing_prerequisite, action."
)
FORMAT_NEUTRAL_PREPARE_REVIEW_RULE = (
    "Review the proposed action using only the current public game input and bounded "
    "memory, which may be prose or JSON. The proposed action is 'prepare meal'. "
    "Identify every required recipe ingredient, then identify which items are currently "
    "carried. A recipe-status ingredient entry indicates that an item is required; only "
    "the carried-items inventory indicates possession. If any required ingredient is "
    "not carried, choose an exact allowed action to gather one. Otherwise keep "
    "'prepare meal' when allowed. Return JSON with required_ingredients, carried_items, action."
)
FORMAT_NEUTRAL_UNAVAILABLE_REVIEW_RULE = (
    "The proposed action is not in allowed_actions. Use only the current public game "
    "input and bounded memory, which may be prose or JSON. First identify which recipe "
    "directions are complete from recipe progress or direction status. Then compare "
    "every required recipe ingredient against the currently carried items. A recipe-status "
    "ingredient entry indicates a requirement, not possession. Choose one exact allowed "
    "action for the next unmet prerequisite. If an explicitly required ingredient is "
    "visible and its take action is allowed, choose that action instead of inspecting it. "
    "Return JSON with completed_directions, missing_ingredients, action."
)
FINALIZATION_PRIORITY_RULE = (
    "First decide whether a prepared meal is available from the current public input "
    "and supplied context. If so and 'eat meal' is allowed, choose 'eat meal'. "
    "Successful meal preparation completes the preparation direction; do not prepare "
    "again or regather ingredients consumed in making that meal. Otherwise identify "
    "the earliest unfinished recipe direction and its unmet prerequisites. "
    "Choose exactly one action from current allowed_actions. "
)


def validate_action_output(text: str, allowed_actions: Iterable[str] | None,
                           *, allow_optional_article: bool = False) -> tuple[str | None, str | None]:
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
        if allow_optional_article:
            verb, separator, target = normalized.partition(" ")
            if separator and target.startswith("the "):
                without_article = f"{verb} {target[4:]}"
                if without_article in allowed:
                    return allowed[without_article], None
        return action, "unavailable_action"
    return allowed[normalized], None


def _normalized_text(text: str) -> str:
    return " ".join(text.lower().split())


def build_v31_action_messages(view: AgentView, memory: str, *, full_history: bool) -> tuple[Message, ...]:
    """Build the unchanged v31 primary request, preserving literal context."""
    allowed_for_turn = view.allowed_actions
    context_name = 'visible interaction history' if full_history else 'memory'
    context_header = ("\nVisible interaction history (diagnostic):\n" if full_history
                      else "\nBounded memory:\n")
    instructions = (
        ORDERED_PREREQUISITE_RULE.replace("bounded memory", f"supplied {context_name}")
        + " Read the supplied context for facts regardless of whether it is prose "
        "or JSON; no particular headings or keys are required. Do not assume the "
        "recipe remains available. If information needed for this decision is "
        "missing or uncertain, choose a legal cookbook reread or another normal "
        "information action when useful, accounting for recheck_cost and "
        "budget_remaining. When the needed information is known, use it without "
        "a forced reread. Ingredients must be carried together with their required "
        "preparation complete before preparing the meal. An item put down is no "
        "longer carried. After preparing the meal, choose 'eat meal' when allowed."
    )
    instructions = FINALIZATION_PRIORITY_RULE + instructions
    return (
        Message("system", instructions),
        # Serialize the public view, then append memory literally. Encoding
        # memory as a JSON string again would add escaping beyond its bound.
        Message("user", "Current game input:\n" + json.dumps({
            "observation": view.observation,
            "goal": view.goal,
            "allowed_actions": allowed_for_turn,
            "budget_remaining": view.budget_remaining,
            "recheck_cost": view.recheck_cost,
        }, sort_keys=True) + context_header + memory),
    )


class PromptedActor:
    """Build action requests; the supplied model determines the actual behavior."""

    def __init__(self, *, full_history: bool = False, prompt_version: str = "v31",
                 context_mode: str | None = None) -> None:
        if prompt_version not in PROMPT_VERSIONS:
            raise ValueError(f'prompt_version must be one of {PROMPT_VERSIONS}')
        if context_mode is None:
            context_mode = 'full_history' if full_history else 'bounded_memory'
        if context_mode not in {'bounded_memory', 'full_history'}:
            raise ValueError('unknown actor context mode')
        if full_history and context_mode != 'full_history':
            raise ValueError('full_history=True contradicts context_mode')
        self.context_mode = context_mode
        self.full_history = context_mode == 'full_history'
        self.prompt_version = prompt_version

    @property
    def metadata(self) -> dict:
        prefix = 'full-history' if self.full_history else 's2-action'
        metadata = {
            "implementation": "PromptedActor",
            "prompt_version": f"{prefix}-{self.prompt_version}",
            "context_mode": self.context_mode,
            "max_repairs": 1, "is_fake": False,
            "repeated_observation_guard": "disabled; game action budget is the limit",
            "action_output_policy": "optional_article_exact_match_v1",
            "action_review_policy": "legal_prepare_shared_finalization_v2",
            "action_repair_policy": FINALIZATION_REPAIR_POLICY,
        }
        return metadata

    def choose_action(self, view: AgentView, memory: str, model: Model) -> str:
        # Each turn starts fresh; no conversation or prior action is cached.
        allowed_for_turn = view.allowed_actions
        context_name = 'visible interaction history' if self.full_history else 'memory'
        messages = build_v31_action_messages(view, memory, full_history=self.full_history)
        # Reviews consume inference resources, not game actions. A repair
        # proposing legal preparation can itself invoke a review.
        for attempt in range(2):
            generation = model.generate(messages, purpose='action' if attempt == 0 else 'action_repair')
            proposed, _ = validate_action_output(generation.text, None)
            legal_for_review = validate_action_output(
                generation.text, allowed_for_turn, allow_optional_article=True)[1] is None
            if proposed and _normalized_text(proposed) == 'prepare meal' and legal_for_review:
                review_rule = FORMAT_NEUTRAL_PREPARE_REVIEW_RULE
                review_rule = review_rule.replace('bounded memory', f'supplied {context_name}')
                review_rule = FINALIZATION_PRIORITY_RULE + review_rule
                generation = model.generate((Message('system', review_rule), messages[1]), purpose='action_review')
            action, reason = validate_action_output(generation.text, allowed_for_turn, allow_optional_article=True)
            if reason is None:
                return action
            if attempt == 0:
                if reason == 'unavailable_action':
                    repair_rule = FORMAT_NEUTRAL_UNAVAILABLE_REVIEW_RULE
                    repair_rule = repair_rule.replace('bounded memory', f'supplied {context_name}')
                    repair_rule = (FINALIZATION_PRIORITY_RULE + repair_rule +
                        " The previous unavailable proposal is rejected. Do not repeat it; "
                        "select a different exact action from current allowed_actions.")
                    messages = (Message("system", repair_rule),
                                Message("user", messages[1].content +
                                        "\nPrevious unavailable proposal: " + str(action)))
                    continue
                if reason == 'malformed_json':
                    feedback = 'Your response is not valid JSON. Remove commentary and code fences. '
                elif reason == 'invalid_action_schema':
                    feedback = 'Your JSON must be an object whose action field is a string. '
                feedback += (
                    "Use only the same supplied observation and context. Select an exact current "
                    "allowed action that advances the cooking goal and fits budget_remaining; "
                    "recipe rereads cost recheck_cost and other actions cost 1. "
                )
                feedback += 'Return only {"action": "exact permitted action"}.'
                messages = (*messages, Message('assistant', generation.text), Message('user', feedback))
        # The wrapper charges this invalid attempt without substituting an action.
        return '[INVALID_ACTION_OUTPUT] ' + generation.text
