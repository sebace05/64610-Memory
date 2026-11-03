"""Unbounded visible observation/action archive for capability diagnostics.

This is not one of the three experimental memory strategies. It cannot inspect
privileged simulator state or log files, and never calls the memory writer.
"""

import json

from .components import MemoryContext, MemoryUpdate, Model


class FullHistoryMemory:
    """Retain visible evidence verbatim without compression or truncation."""

    @property
    def metadata(self) -> dict:
        return {"implementation": "FullHistoryMemory", "version": 1,
                "strategy": "full_history", "is_fake": False,
                "diagnostic_only": True, "token_limit_applies": False,
                "contents": "initial_observation_and_all_nonterminal_actions_observations"}

    def empty(self) -> str:
        return "[]"

    def render(self, memory: str) -> str:
        return memory

    def update(self, previous_memory: str, action: str, observation: str,
               context: MemoryContext, model: Model) -> MemoryUpdate:
        records = json.loads(previous_memory)
        records.append({"action": action, "observation": observation})
        return MemoryUpdate(json.dumps(records, ensure_ascii=False),
                            ("full_history_diagnostic_no_compression",))
