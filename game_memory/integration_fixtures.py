"""Deliberately fake components for wiring tests, never research baselines."""

import json
from typing import Sequence

from .components import Generation, MemoryContext, MemoryUpdate, Message, Model


class FakeModel:
    """Scripted responses; counts whitespace words, not actual model tokens."""

    def __init__(self, actions: Sequence[str] = ("examine cookbook",)) -> None:
        # Consume a fixed script, then repeat look around until budget exhaustion.
        # This exercises the loop without pretending to solve the task with an LLM.
        self._script = tuple(actions)
        self._actions = iter(self._script)

    @property
    def metadata(self) -> dict:
        return {"implementation": "FakeModel", "is_fake": True,
                "tokenizer": "whitespace_fixture_not_model_tokens",
                "scripted_actions": self._script, "fallback_action": "look around"}

    def count_tokens(self, text: str) -> int:
        # Deliberately cheap placeholder. Real backends must use their tokenizer.
        return len(text.split())

    def score_choices(self, messages: Sequence[Message], *, labels: Sequence[str]) -> Generation:
        labels = tuple(labels)
        if not labels or len(set(labels)) != len(labels):
            raise ValueError("fixture choices must be nonempty and unique")
        n = len(labels)
        return Generation(labels[0], sum(self.count_tokens(m.content) for m in messages), 1, 0.0, {
            "inference_mode": "legal_label_argmax_v1", "generation_called": False,
            "labels": list(labels), "label_token_ids": list(range(n)),
            "candidate_logits": [0.0] * n, "conditional_probabilities": [1.0 / n] * n,
            "selected_label": labels[0], "selected_token_id": 0,
            "selection_rule": "argmax", "tie_break": "first_in_supplied_order",
            "finish_reason": "choice", "decision_token_count": 1,
            "rendered_prompt_sha256": None, "prompt_hash_evidence": "unavailable_fixture",
            "scoring_evidence": "synthetic_fixture", "is_fake": True,
            "token_accounting": "synthetic_fixture_ids_and_whitespace_counts_not_Qwen",
            "latency_scope": "synthetic_fixture_zero_not_measured",
            "peak_cuda_allocated_bytes": None,
        })

    def generate(self, messages: Sequence[Message], *, purpose: str) -> Generation:
        if purpose in {"action", "action_review", "action_repair"}:
            text = json.dumps({"action": next(self._actions, "look around")})
        elif purpose == "memory":
            # Ignore recipe facts and return a tiny last-action placeholder.
            # Different output shapes exercise the shared strategy interface only.
            payload = json.loads(messages[-1].content)
            note = f"Fixture: last action was {payload['action']}"
            if payload["strategy"] == "prose":
                text = note
            elif payload["strategy"] == "structured":
                text = json.dumps({"last_action": payload["action"]}, sort_keys=True)
        else:
            raise ValueError(f"unsupported fake-model purpose: {purpose}")
        # Counts are synthetic and latency is a placeholder zero. The is_fake
        # metadata labels this component; these numbers cannot estimate LLM cost.
        return Generation(text, sum(self.count_tokens(m.content) for m in messages),
                          self.count_tokens(text), 0.0)


class FakeMemory:
    """Exercises interfaces/rendering only; does not retain useful recipe facts."""

    def __init__(self, strategy: str = "prose") -> None:
        if strategy not in {"prose", "structured"}:
            raise ValueError("unknown strategy")
        self.strategy = strategy

    @property
    def metadata(self) -> dict:
        return {"implementation": "FakeMemory", "version": 1,
                "strategy": self.strategy, "is_fake": True}

    def empty(self) -> str:
        return "" if self.strategy == "prose" else "{}"

    def render(self, memory: str) -> str:
        # Fixture state is already the full actor-visible string; no extra facts.
        return memory

    def update(self, previous_memory: str, action: str, observation: str,
               context: MemoryContext, model: Model) -> MemoryUpdate:
        # Use the supplied logged model just as a real strategy would. This
        # verifies that writing calls contribute to usage and appear in traces.
        messages = (
            Message("system", "Integration fixture: return a placeholder memory update."),
            Message("user", json.dumps({
                "strategy": self.strategy, "previous_memory": previous_memory,
                "action": action, "observation": observation,
                "context": {"goal": context.goal, "budget_remaining": context.budget_remaining,
                            "recheck_cost": context.recheck_cost,
                            "memory_token_limit": context.memory_token_limit},
            }, sort_keys=True)),
        )
        generated = model.generate(messages, purpose="memory")
        return MemoryUpdate(generated.text, ("fake_memory_not_a_research_strategy",))
