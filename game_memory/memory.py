"""Production bounded-memory formats using the existing MemoryStrategy contract.

Instances keep no episode state: the serialized string is the only factual state.
See docs/p1-memory.md for syntax, rendering, and repair/fallback policies.
"""

import json
import math
from decimal import Decimal, InvalidOperation

from .components import MemoryContext, MemoryUpdate, Message, Model


PROMPT_VERSION = "p1-memory-v17"
_SHARED_INSTRUCTIONS = """Rewrite the bounded memory for the next task decision.
Use only the previous bounded memory, selected action, new observation, and public
task context supplied in this request. Retain useful supported recipe, inventory,
and progress information; update it from the latest evidence. Do not invent facts.
Choose what to retain, compress, or omit to fit the stated memory-token allowance,
which applies to the complete actor-visible rendering, including formatting.
An empty memory is permitted. There is no other persistent notebook. Return only
the replacement memory in the required format, without commentary or code fences."""


class _InvalidMemory(ValueError):
    """An output-validation failure; its message is a logger-safe reason code."""


def _text(memory: str) -> None:
    if not isinstance(memory, str):
        raise _InvalidMemory("memory_must_be_text")
    try:
        memory.encode("utf-8")
    except UnicodeEncodeError as error:
        raise _InvalidMemory("invalid_unicode") from error


def _unique_object(pairs: list[tuple]) -> dict:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise _InvalidMemory("duplicate_json_key")
        obj[key] = value
    return obj


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise _InvalidMemory("nonfinite_json_number")
    # json.dumps writes a float's shortest round-trippable decimal. Compare
    # mathematical decimal values before accepting it so rendering cannot turn
    # a precise quantity into a different number (including underflow to zero).
    try:
        original = Decimal(text)
    except InvalidOperation as error:
        raise _InvalidMemory("json_number_unrepresentable") from error
    if original != Decimal(str(value)):
        raise _InvalidMemory("json_number_changed")
    return value


def _reject_constant(_text: str) -> None:
    raise _InvalidMemory("nonfinite_json_number")


def _object(memory: str) -> dict:
    """Strict object syntax; no fence stripping, missing-field inference, or repair."""
    _text(memory)
    try:
        obj = json.loads(memory, object_pairs_hook=_unique_object,
                         parse_float=_finite_float, parse_constant=_reject_constant)
    except _InvalidMemory:
        raise
    except (ValueError, RecursionError) as error:
        raise _InvalidMemory("malformed_json") from error
    if not isinstance(obj, dict):
        raise _InvalidMemory("json_object_required")
    return obj


def _serialize(obj: dict) -> str:
    try:
        text = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (ValueError, RecursionError) as error:
        raise _InvalidMemory("malformed_json") from error
    # Escaped lone surrogates can survive json.loads, but cannot be tokenized as
    # ordinary UTF-8 text. Reject them rather than silently replacing characters.
    _text(text)
    return text


def _within_budget(text: str, limit: int, model: Model) -> None:
    count = model.count_tokens(text)
    # A broken counter is an infrastructure error, not an invalid model output.
    if type(count) is not int or count < 0:
        raise ValueError("model tokenizer returned an invalid token count")
    if count > limit:
        raise _InvalidMemory(f"over_budget:{count}>{limit}")


class _BoundedMemory:
    """Shared prompting, validation, one repair, and previous-state fallback."""

    __slots__ = ()
    strategy: str
    format_instructions: str

    @property
    def metadata(self) -> dict:
        return {
            "implementation": type(self).__name__,
            "strategy": self.strategy,
            "version": 17,
            "prompt_version": PROMPT_VERSION,
            "is_fake": False,
            "max_repairs": 1,
            "update_policy": "syntax_and_size_one_repair_previous_state_v1",
            "semantic_validation": "none",
            "fallback": "previous_valid_memory",
            "render_version": "p1-render-v2",
            "json_policy": (None if self.strategy == "prose" else
                            "object_unique_keys_value_preserving_numbers_compact_sorted_utf8_v2"),
        }

    def empty(self) -> str:
        raise NotImplementedError

    def _prepare(self, memory: str) -> tuple[str, str]:
        """Return canonical serialized state and complete actor-visible text."""
        raise NotImplementedError

    def render(self, memory: str) -> str:
        return self._prepare(memory)[1]

    def _messages(self, previous_rendered: str, action: str, observation: str,
                  context: MemoryContext, limit: int) -> tuple[Message, ...]:
        """Primary writer request; versioned subclasses may override (memory-probe-v1)."""
        return (
            Message("system", f"Memory writer {PROMPT_VERSION}\n{_SHARED_INSTRUCTIONS}"
                    f"\n\nRequired format:\n{self.format_instructions}"),
            Message("user", json.dumps({
                "previous_memory": previous_rendered,
                "action": action,
                "observation": observation,
                "context": {
                    "goal": context.goal,
                    "budget_remaining": context.budget_remaining,
                    "recheck_cost": context.recheck_cost,
                    "memory_token_limit": limit,
                },
            }, sort_keys=True, ensure_ascii=False)),
        )

    def update(self, previous_memory: str, action: str, observation: str,
               context: MemoryContext, model: Model) -> MemoryUpdate:
        limit = context.memory_token_limit
        if type(limit) is not int or limit < 1:
            raise ValueError("memory_token_limit must be a positive integer")
        # The caller supplies a valid predecessor (empty() on initialization).
        # Do not conceal an invalid predecessor or an unusably small allowance.
        previous_rendered = self.render(previous_memory)
        _within_budget(previous_rendered, limit, model)
        messages = self._messages(previous_rendered, action, observation, context, limit)
        events = []
        for attempt in range(2):
            purpose = "memory" if attempt == 0 else "memory_repair"
            # Transport/model/tokenizer errors propagate to the runner; they
            # must not masquerade as a valid gameplay memory fallback.
            generation = model.generate(messages, purpose=purpose)
            try:
                state, rendered = self._prepare(generation.text)
                _within_budget(rendered, limit, model)
            except _InvalidMemory as error:
                events.append(f"{purpose}_rejected:{error}")
                if attempt == 0:
                    messages = (*messages, Message("assistant", generation.text),
                                Message("user", f"Candidate rejected: {error}. Rewrite using "
                                        "the same supplied evidence and required format. The "
                                        f"complete rendering must fit {limit} tokens. Return "
                                        "only the replacement memory."))
            else:
                if state != generation.text:
                    events.append(f"{purpose}_json_canonicalized")
                events.append(f"{purpose}_accepted")
                return MemoryUpdate(state, tuple(events))
        events.append("memory_fallback:previous_valid_memory")
        return MemoryUpdate(previous_memory, tuple(events))


class ProseMemory(_BoundedMemory):
    """Natural-language notebook; text (including whitespace) is preserved."""

    __slots__ = ()
    strategy = "prose"
    format_instructions = (
        "Return concise natural-language sentences or bullet notes. "
        "The notebook is rendered verbatim, including whitespace."
    )

    def empty(self) -> str:
        return ""

    def _prepare(self, memory: str) -> tuple[str, str]:
        _text(memory)
        return memory, memory


class StructuredMemory(_BoundedMemory):
    """Model-managed JSON object, without predefined task-specific fields."""

    __slots__ = ()
    strategy = "structured"
    format_instructions = (
        "Return one JSON object. Choose your own keys and nested JSON values; "
        "there are no predefined task fields. Use unique keys and finite numbers; "
        "write exact quantities as strings if decimal-to-float formatting would change them. "
        "Emit compact JSON with sorted keys and literal Unicode. Rendering uses "
        "that canonical form, including all braces, quotes, keys, and punctuation."
    )

    def empty(self) -> str:
        return "{}"

    def _prepare(self, memory: str) -> tuple[str, str]:
        state = _serialize(_object(memory))
        return state, state
