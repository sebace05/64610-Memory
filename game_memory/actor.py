"""Fresh per-turn action prompts with at most one output-repair attempt."""

import json

from .components import Message, Model
from .contracts import AgentView


class PromptedActor:
    """Build action requests; the supplied model determines the actual behavior."""

    @property
    def metadata(self) -> dict:
        return {"implementation": "PromptedActor", "prompt_version": "s2-action-v1",
                "max_repairs": 1, "is_fake": False}

    def choose_action(self, view: AgentView, memory: str, model: Model) -> str:
        # This list is local to this call. No persistent chat or past observations.
        messages = (
            Message("system", "Choose one permitted game action using only the current "
                    "observation and memory. Recipe rereads consume the stated budget. "
                    'Return only a JSON object of the form {"action": "exact permitted action"}.'),
            # Serialize the public view, then append memory literally. Encoding
            # memory as a JSON string again would add escaping beyond its bound.
            Message("user", "Current game input:\n" + json.dumps({
                "observation": view.observation,
                "goal": view.goal,
                "allowed_actions": view.allowed_actions,
                "budget_remaining": view.budget_remaining,
                "recheck_cost": view.recheck_cost,
            }, sort_keys=True) + "\nBounded memory:\n" + memory),
        )
        # Normalize for matching, but return the engine's canonical command text.
        allowed = {" ".join(a.lower().split()): a for a in view.allowed_actions}
        # Two generations maximum: one original response and one repair.
        # Repairs use inference resources, but are not additional game actions.
        for attempt in range(2):
            generation = model.generate(
                messages, purpose="action" if attempt == 0 else "action_repair"
            )
            try:
                # Parsing JSON alone is insufficient: the action must also be
                # a string matching one of this turn's permitted commands.
                parsed = json.loads(generation.text)
                action = parsed["action"] if isinstance(parsed, dict) else None
            except (json.JSONDecodeError, KeyError):
                action = None
            if isinstance(action, str):
                normalized = " ".join(action.lower().split())
                if normalized in allowed:
                    return allowed[normalized]
            if attempt == 0:
                # Add feedback only within this turn. The next choose_action()
                # call starts over, so this exchange cannot carry hidden memory.
                messages = (*messages, Message("assistant", generation.text),
                            Message("user", "The output was malformed or not a permitted action. "
                                    "Return only the required JSON with one permitted action."))
        # Ensure malformed text cannot accidentally be interpreted as a legal
        # command after repair failed. The wrapper charges this invalid attempt.
        return "[INVALID_ACTION_OUTPUT] " + generation.text
