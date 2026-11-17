"""Opt-in, stateless full-history legal-action interface, without semantic rescue."""

import json

from .actor import build_v31_action_messages
from .components import ChoiceModel, Message
from .contracts import AgentView

LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
FOOTER = "\nLegal action options (legal-choice-v1):\n"


class LegalChoiceActor:
    @property
    def metadata(self) -> dict:
        return {
            "implementation": "LegalChoiceActor",
            "prompt_version": "full-history-legal-choice-v1",
            "context_mode": "full_history",
            "action_output_policy": "legal_label_argmax_v1",
            "max_repairs": 0, "action_review_policy": "none",
            "action_repair_policy": "none",
            "legality_guaranteed_by_interface": True, "is_fake": False,
        }

    def choose_action(self, view: AgentView, memory: str, model: ChoiceModel) -> str:
        actions = view.allowed_actions
        if not actions or len(actions) > len(LABELS):
            raise ValueError("legal-choice-v1 requires 1 to 52 actions")
        if any(not isinstance(a, str) or not a for a in actions):
            raise ValueError("legal actions must be nonempty strings")
        if len(set(actions)) != len(actions):
            raise ValueError("duplicate legal actions")
        labels = tuple(LABELS[:len(actions)])
        system, user = build_v31_action_messages(view, memory, full_history=True)
        old = "Return JSON with next_direction, missing_prerequisite, action."
        if system.content.count(old) != 1:
            raise ValueError("expected exactly one v31 output instruction")
        options = [{"label": label, "action": action} for label, action in zip(labels, actions)]
        messages = (
            Message(system.role, system.content.replace(old,
                "Return only the label of one listed legal action option, with no other text.")),
            Message(user.role, user.content + FOOTER + json.dumps(
                options, ensure_ascii=False, sort_keys=True)),
        )
        result = model.score_choices(messages, labels=labels)
        if result.text not in labels:
            raise ValueError("scorer returned an unexpected exact label")
        return actions[labels.index(result.text)]
