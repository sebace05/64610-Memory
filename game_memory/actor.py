"""Fresh per-turn action prompts with at most one output-repair attempt."""

import json
import re
from collections.abc import Iterable

from .components import ACTOR_GUARD_FAILURE_PREFIX, Message, Model
from .contracts import AgentView


PROMPT_VERSIONS = ("v1", "v2", "v2-mechanics", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13", "v14", "v15", "v16", "v17", "v18", "v19", "v20", "v21", "v22", "v23", "v24", "v25", "v26", "v27", "v28", "v29")
REPEATED_OBSERVATION_GUARD_VERSION = "v1"

# Object and book inspections are expected to be stable. Room descriptions and
# inventory can change after ordinary game actions, so they stay outside guard.
_INFORMATION_ACTION_PREFIXES = ("examine ", "read ")
_INFORMATION_STOPWORDS = frozenset({
    "about", "after", "again", "also", "and", "are", "can", "contains", "does",
    "for", "from", "gather", "into", "is", "its", "meal", "that", "the", "there",
    "this", "with", "you",
})

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

ORDERED_RECIPE_RULES = (
    "Recipe directions are ordered prerequisites. Track each listed direction in order, "
    "and complete the earliest unfinished direction before moving to a later one. "
    "For example, if slicing or chopping appears before roasting or grilling, do that "
    "preparation first. After each action, use the new observation and allowed_actions "
    "to confirm what remains. Do not choose 'prepare meal' until every ingredient has "
    "completed all of its listed directions and is carried; choose 'eat meal' only after "
    "'prepare meal' has succeeded and made the meal available."
)

GLOBAL_RECIPE_ORDER_RULE = (
    "The recipe directions form one global ordered list. Complete the first unfinished "
    "line from top to bottom before performing any later line, even if a later ingredient "
    "or action is easier. Do not skip ahead to another ingredient's preparation."
)

MEAL_FINALIZATION_RULE = (
    "After completing every ingredient direction and carrying all required ingredients, "
    "choose 'prepare meal' immediately if it appears in allowed_actions. Never choose "
    "'eat <ingredient>' or another ingredient action at this point. After preparation "
    "succeeds, choose 'eat meal' when allowed; only the prepared meal completes the goal."
)

RECIPE_REREAD_RULE = (
    "If the supplied context already contains the complete ingredient list and every "
    "recipe direction, treat that recipe as known. Do not read or examine the cookbook "
    "again unless evidence shows the recipe is missing or incomplete. Use the budget "
    "for the first unfinished recipe direction instead of repeating a known reread."
)

RECIPE_GOAL_PRECEDENCE_RULE = (
    "The goal's instruction to check the cookbook is already satisfied when the supplied "
    "context contains the initial recipe with all ingredients and directions. That recipe "
    "is authoritative even though the generic goal still mentions the cookbook. Do not "
    "spend budget on read/examine cookbook while that complete recipe is present. Choose "
    "a permitted action for the first unfinished recipe direction or its prerequisite."
)

DIRECT_ACTION_PRIORITY_RULE = (
    "Decision rule for this turn: find the first recipe direction not yet confirmed complete. "
    "If its matching action is in allowed_actions and its required ingredient is carried, "
    "choose that action now. For a cooking direction, match grill to toaster, roast to oven, "
    "and fry to stove. If a required slicing or chopping action is absent, take an available "
    "knife. If a required ingredient is not carried, take it when available or open a closed "
    "container that may hold it. Inspect objects only when their state is needed to identify "
    "a missing prerequisite. Never open an already open container."
)

CONCISE_GAMEPLAY_RULE = (
    "You are playing CookingWorld. Return exactly one JSON object with an action copied "
    "verbatim from allowed_actions. Use only the current public view and bounded memory. "
    "The recipe is already in memory; avoid rereading the cookbook. Complete every recipe "
    "direction, then prepare meal and eat meal. Track carried items and completed steps from "
    "memory. Work on the first unfinished direction: gather its ingredient if needed, then "
    "perform that direction. Grill uses toaster, roast uses oven, fry uses stove; slicing "
    "or chopping may need a carried knife. Open a closed container to find a missing ingredient. "
    "If the exact required action is currently allowed, choose it immediately. Do not eat an "
    "ingredient, inspect a known object again, or open an already open container."
)

GOAL_FIRST_RULE = (
    "Your goal is to prepare and eat the meal described by the recipe. "
    "Use the current observation and bounded memory to decide what remains. "
    "Choose an available action that advances the next unfinished recipe direction; "
    "gather a missing ingredient or tool when necessary. Inspect when you need "
    "information. Return one exact action from allowed_actions as JSON."
)

TWO_PART_DECISION_RULE = (
    "Your goal is to prepare and eat the meal. Use only the current observation "
    "and bounded memory. First identify the earliest unfinished recipe direction. "
    "For CookingWorld, grill uses toaster, roast uses oven, fry uses stove. "
    "Then choose one exact command from allowed_actions that advances that direction. "
    "Return JSON {\"next_direction\":\"...\",\"action\":\"...\"}."
)

REASONED_DECISION_RULE = (
    "Your goal is to prepare and eat the meal. Use only the current observation "
    "and bounded memory. Identify the earliest unfinished recipe direction. "
    "For CookingWorld, grill uses toaster, roast uses oven, fry uses stove. "
    "Choose one exact action from allowed_actions. In one short sentence, explain "
    "how that action advances the direction or obtains information needed for it. "
    "Return JSON {\"next_direction\":\"...\",\"reason\":\"...\",\"action\":\"...\"}."
)

PREREQUISITE_DECISION_RULE = (
    "Your goal is to prepare and eat the meal. Use only the current observation, "
    "allowed_actions, and bounded memory. Identify the first unfinished recipe "
    "direction. Before choosing, check whether you carry its required ingredient "
    "and whether a tool is required. If the ingredient is not carried, choose an "
    "available action to find or take it; if it is carried and the direction "
    "action is available, do that action. CookingWorld: grill=toaster, "
    "roast=oven, fry=stove. Return JSON with next_direction, "
    "missing_prerequisite, and exact action."
)

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

INGREDIENT_STATUS_RULE = (
    ORDERED_PREREQUISITE_RULE + " Before choosing, report whether EACH named recipe "
    "ingredient is carried. Treat 'cook X in toaster' in Recipe progress as completing "
    "'grill X' and 'cook X in oven' as completing 'roast X'. If memory confirms that "
    "the prepared meal is carried, choose 'eat meal' when allowed. Otherwise, for "
    "prepare meal, first gather any ingredient you report as not carried. Return JSON "
    "with ingredient_status, next_direction, missing_prerequisite, action."
)

MEAL_FIRST_INGREDIENT_STATUS_RULE = (
    "If memory confirms the prepared meal is carried, choose 'eat meal' when allowed. "
    "The ingredients have become the meal and do not need gathering again. Otherwise, "
    "report whether EACH named recipe ingredient is carried before choosing; gather "
    "any missing ingredient before 'prepare meal'. " + ORDERED_PREREQUISITE_RULE +
    " Treat 'cook X in toaster' in Recipe progress as completing 'grill X' and "
    "'cook X in oven' as completing 'roast X'. Return JSON with ingredient_status, "
    "next_direction, missing_prerequisite, action."
)

PREPARE_MEAL_REVIEW_RULE = (
    "Review the proposed action using only the supplied current game input and bounded "
    "memory. The proposed action is 'prepare meal'. Check every ingredient under "
    "Ingredients against Carried items. If any required ingredient is absent, choose "
    "an exact allowed action to gather one missing ingredient. Otherwise keep "
    "'prepare meal' if it is allowed. Return only JSON with ingredient_status and action."
)

UNAVAILABLE_ACTION_REVIEW_RULE = (
    "The actor proposed an action that is not in allowed_actions. Re-evaluate the "
    "recipe against Recipe progress: a completed 'cook X in toaster' action means "
    "'grill X' is done. Identify the next unfinished direction, check carried "
    "ingredients, and choose one exact allowed action that advances it. Return JSON "
    "with completed_directions, next_direction, action."
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

TOOL_PREREQUISITE_RULES = (
    "A listed preparation step may require a tool. If the next required preparation "
    "action is absent from allowed_actions, check whether an appropriate tool is visible "
    "and a matching 'take ...' action is allowed; take that tool before retrying the "
    "same recipe step. Examine a tool only when its location or state is unclear. If "
    "examining it returns no new information, do not repeat that examination; choose "
    "the available action that satisfies the missing prerequisite. Never skip the "
    "missing recipe step or eat an ingredient as a substitute for a prepared meal."
)

CLOSED_CONTAINER_RULES = (
    "If a task-relevant item may be inside a visible closed container, use its matching "
    "'open ...' action when allowed. Examining a closed container only confirms that it "
    "is closed. After one such confirmation, do not examine that container again unless "
    "new evidence changes its state; open it or pursue another visible prerequisite."
)

CLOSED_CONTAINER_PRIORITY_RULE = (
    "Action priority: when the current observation or memory says a task-relevant "
    "container is closed and allowed_actions includes its matching 'open ...' action, "
    "choose that open action immediately. Do not examine the same unchanged container "
    "again first. Opening it takes priority over gathering more descriptions."
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


def _normalized_text(text: str) -> str:
    return " ".join(text.lower().split())


def _information_result_is_in_context(action: str, result: str, context: str) -> bool:
    """Check whether context retains the result of a prior information action."""
    action_words = action.split()
    if len(action_words) > 1 and action_words[-1] == "cookbook":
        # A cookbook's presence alone does not mean its recipe is remembered.
        context_lower = context.lower()
        if "ingredients" not in context_lower or "directions" not in context_lower:
            return False

    result_words = {
        word for word in re.findall(r"[a-z0-9]+", result.lower())
        if len(word) > 2 and word not in _INFORMATION_STOPWORDS
    }
    context_words = set(re.findall(r"[a-z0-9]+", context.lower()))
    if not result_words:
        return _normalized_text(result) in _normalized_text(context)
    return len(result_words & context_words) / len(result_words) >= 0.65


class PromptedActor:
    """Build action requests; the supplied model determines the actual behavior."""

    def __init__(self, *, full_history: bool = False, prompt_version: str = "v1") -> None:
        if prompt_version not in PROMPT_VERSIONS:
            raise ValueError(f"prompt_version must be one of {PROMPT_VERSIONS}")
        self.full_history = full_history
        self.prompt_version = prompt_version
        self._pending_action: str | None = None
        self._last_action: str | None = None
        self._information_results: dict[str, set[str]] = {}

    @property
    def metadata(self) -> dict:
        prefix = "full-history" if self.full_history else "s2-action"
        metadata = {"implementation": "PromptedActor",
                "prompt_version": f"{prefix}-{self.prompt_version}",
                "context_mode": "full_history" if self.full_history else "bounded_memory",
                "max_repairs": 1, "is_fake": False,
                "repeated_observation_guard": "disabled; game action budget is the limit"}
        if self.prompt_version in ("v19", "v20", "v21"):
            metadata["immediate_repeat_policy"] = "exclude_previous_action_v1"
        if self.prompt_version in ("v24", "v25", "v26", "v27", "v28", "v29"):
            metadata["action_output_policy"] = "optional_article_exact_match_v1"
        if self.prompt_version in ("v27", "v28"):
            metadata["action_review_policy"] = "qwen_prepare_meal_ingredient_review_v1"
        if self.prompt_version == "v28":
            metadata["action_repair_policy"] = "qwen_unavailable_action_progress_review_v1"
        if self.prompt_version == "v29":
            metadata["action_review_policy"] = "qwen_format_neutral_prepare_review_v1"
            metadata["action_repair_policy"] = "qwen_format_neutral_unavailable_review_v1"
        if self.prompt_version in ("v2-mechanics", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13", "v14", "v15"):
            metadata["requires_unlimited_inventory"] = True
        return metadata

    def reset_episode_state(self) -> None:
        """Clear episode-local inspection evidence before a fresh game."""
        self._pending_action = None
        self._last_action = None
        self._information_results.clear()

    def choose_action(self, view: AgentView, memory: str, model: Model) -> str:
        if self._pending_action and self._is_information_action(self._pending_action):
            results = self._information_results.setdefault(self._pending_action, set())
            results.add(view.observation)
        self._pending_action = None
        allowed_for_turn = view.allowed_actions
        if self.prompt_version in ("v19", "v20", "v21") and self._last_action is not None:
            allowed_for_turn = tuple(action for action in view.allowed_actions
                                     if action != self._last_action)
            if not allowed_for_turn:
                return "[INVALID_ACTION_OUTPUT] no alternative allowed action"

        # This list is local to this call. No persistent chat or past observations.
        context_name = "visible interaction history" if self.full_history else "memory"
        context_header = ("\nVisible interaction history (diagnostic):\n" if self.full_history
                          else "\nBounded memory:\n")
        instructions = ("Choose one permitted game action using only the current "
                    f"observation and {context_name}. Recipe rereads consume the stated budget. "
                    'Return only a JSON object of the form {"action": "exact permitted action"}.')
        if self.prompt_version != "v1":
            instructions = _progress_instructions(context_name)
        if self.prompt_version in ("v2-mechanics", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13", "v14", "v15"):
            instructions = MECHANICS_PRIMER + "\n\n" + instructions
        if self.prompt_version in ("v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13", "v14", "v15"):
            instructions = APPLIANCE_RULES + "\n\n" + instructions
        if self.prompt_version in ("v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13", "v14", "v15"):
            instructions = ORDERED_RECIPE_RULES + "\n\n" + instructions
        if self.prompt_version == "v5":
            instructions = TOOL_PREREQUISITE_RULES + "\n\n" + instructions
        if self.prompt_version in ("v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13", "v14", "v15"):
            instructions = (CLOSED_CONTAINER_RULES + "\n\n" + TOOL_PREREQUISITE_RULES
                            + "\n\n" + instructions)
        if self.prompt_version in ("v8", "v9", "v10", "v11", "v12", "v13", "v14", "v15"):
            instructions = CLOSED_CONTAINER_PRIORITY_RULE + "\n\n" + instructions
        if self.prompt_version in ("v10", "v11", "v12", "v13", "v14", "v15"):
            instructions = GLOBAL_RECIPE_ORDER_RULE + "\n\n" + instructions
        if self.prompt_version in ("v11", "v12", "v13", "v14", "v15"):
            instructions = MEAL_FINALIZATION_RULE + "\n\n" + instructions
        if self.prompt_version in ("v12", "v13", "v14", "v15"):
            instructions = RECIPE_REREAD_RULE + "\n\n" + instructions
        if self.prompt_version in ("v13", "v14", "v15"):
            instructions = RECIPE_GOAL_PRECEDENCE_RULE + "\n\n" + instructions
        if self.prompt_version in ("v14", "v15"):
            instructions = DIRECT_ACTION_PRIORITY_RULE + "\n\n" + instructions
        if self.prompt_version == "v16":
            instructions = CONCISE_GAMEPLAY_RULE
        if self.prompt_version == "v17":
            instructions = GOAL_FIRST_RULE
        if self.prompt_version in ("v18", "v19"):
            instructions = TWO_PART_DECISION_RULE
        if self.prompt_version in ("v20", "v21"):
            instructions = REASONED_DECISION_RULE
        if self.prompt_version == "v22":
            instructions = PREREQUISITE_DECISION_RULE
        if self.prompt_version in ("v23", "v24", "v27", "v28", "v29"):
            instructions = ORDERED_PREREQUISITE_RULE
        if self.prompt_version == "v25":
            instructions = INGREDIENT_STATUS_RULE
        if self.prompt_version == "v26":
            instructions = MEAL_FIRST_INGREDIENT_STATUS_RULE
        messages = (
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
        # Normalize for matching, but return the engine's canonical command text.
        # One original response and at most one repair. V27 may also ask the
        # model to review a proposed meal preparation before validation.
        # These calls use inference resources, but are not game actions.
        for attempt in range(2):
            generation = model.generate(
                messages, purpose="action" if attempt == 0 else "action_repair"
            )
            if self.prompt_version in ("v27", "v28", "v29"):
                proposed, _ = validate_action_output(generation.text, None)
                if proposed and _normalized_text(proposed) == "prepare meal":
                    generation = model.generate(
                        (Message("system", FORMAT_NEUTRAL_PREPARE_REVIEW_RULE
                                 if self.prompt_version == "v29" else PREPARE_MEAL_REVIEW_RULE),
                         messages[1]),
                        purpose="action_review",
                    )
            action, reason = validate_action_output(
                generation.text, allowed_for_turn,
                allow_optional_article=self.prompt_version in ("v24", "v25", "v26", "v27", "v28", "v29"))
            if reason is None and self.prompt_version in ("v20", "v21"):
                explanation = json.loads(generation.text).get("reason")
                if not isinstance(explanation, str) or not explanation.strip():
                    reason = "missing_action_reason"
            if (reason is None and self.prompt_version in ("v15", "v16")
                    and action.startswith("eat ") and action != "eat meal"
                    and "Ingredients:" in memory and "Directions:" in memory):
                reason = "premature_ingredient_eat"
            if reason is None:
                self._accept_action(action)
                self._last_action = action
                return action
            if attempt == 0:
                if self.prompt_version in ("v28", "v29") and reason == "unavailable_action":
                    messages = (Message("system", FORMAT_NEUTRAL_UNAVAILABLE_REVIEW_RULE
                                        if self.prompt_version == "v29" else UNAVAILABLE_ACTION_REVIEW_RULE),
                                Message("user", messages[1].content +
                                        "\nPrevious unavailable proposal: " + str(action)))
                    continue
                # Add feedback only within this turn. The next choose_action()
                # call starts over, so this exchange cannot carry hidden memory.
                if reason == "premature_ingredient_eat":
                    feedback = ("Eating an ingredient before preparing the meal ends the task. "
                                "Choose an exact allowed action that advances the first unfinished "
                                "recipe direction or gathers its required ingredient. Return only "
                                "the required JSON.")
                elif reason == "missing_action_reason":
                    feedback = ("Include a nonempty one-sentence reason explaining how your "
                                "action advances the next direction or obtains needed information. "
                                "Return JSON with next_direction, reason, and an exact allowed action.")
                elif reason == "repeated_information_action":
                    feedback = (
                        f"The action {json.dumps(action)} already returned the same information, "
                        "and that result is present in the supplied context. Do not repeat this "
                        "inspection. Choose another exact allowed action that advances an "
                        "unfinished prerequisite. If the needed information is missing from "
                        "context, a cookbook reread remains allowed. Return only the required JSON."
                    )
                else:
                    feedback = ("The output was malformed or not a permitted action. "
                                "Return only the required JSON with one permitted action.")
                if self.prompt_version != "v1" and reason not in ("repeated_information_action", "premature_ingredient_eat", "missing_action_reason"):
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
                    )
                    feedback += ('Return only JSON with next_direction, reason, and action.'
                                 if self.prompt_version == "v21" else
                                 'Return only {"action": "exact permitted action"}.')
                    if self.prompt_version in ("v5", "v7", "v9", "v10", "v11", "v12", "v13", "v14", "v15") and reason == "unavailable_action":
                        feedback += (
                            " If the unavailable command is a preparation step, check whether its "
                            "required tool can be taken with a current allowed action. Take the "
                            "tool instead of repeating an examination; then continue the earliest "
                            "unfinished recipe direction. Do not choose to eat an ingredient."
                        )
                messages = (*messages, Message("assistant", generation.text), Message("user", feedback))
        # Ensure malformed text cannot accidentally be interpreted as a legal
        # command after repair failed. The wrapper charges this invalid attempt.
        return "[INVALID_ACTION_OUTPUT] " + generation.text

    @staticmethod
    def _is_information_action(action: str) -> bool:
        normalized = " ".join(action.lower().split())
        return normalized.startswith(_INFORMATION_ACTION_PREFIXES)

    def _repeats_known_information(self, action: str, memory: str) -> bool:
        normalized = " ".join(action.lower().split())
        if not self._is_information_action(normalized):
            return False
        return any(_information_result_is_in_context(normalized, result, memory)
                   for result in self._information_results.get(normalized, set()))

    def _accept_action(self, action: str) -> None:
        normalized = " ".join(action.lower().split())
        if self._is_information_action(normalized):
            self._pending_action = normalized
            return

        self._pending_action = None
        verb, _, target = normalized.partition(" ")
        if verb not in {"open", "close", "take", "put", "slice", "chop", "cook"}:
            return
        changed_words = set(re.findall(r"[a-z0-9]+", target))
        for information_action in tuple(self._information_results):
            inspected_target = information_action.partition(" ")[2]
            inspected_words = set(re.findall(r"[a-z0-9]+", inspected_target))
            if changed_words & inspected_words:
                del self._information_results[information_action]
