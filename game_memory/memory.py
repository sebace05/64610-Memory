"""Production bounded-memory formats using the existing MemoryStrategy contract.

Instances keep no episode state: the serialized string is the only factual state.
See docs/p1-memory.md for syntax, rendering, and repair/fallback policies.
"""

import json
import math
import re
from decimal import Decimal, InvalidOperation

from .components import MemoryContext, MemoryUpdate, Message, Model


PROMPT_VERSION = "p1-memory-v16"
_SHARED_INSTRUCTIONS = """Rewrite the bounded memory for the next task decision.
Use only the previous bounded memory, selected action, new observation, and public
task context supplied in this request. Preserve information useful for completing
the goal; revise or remove information as the evidence warrants. Do not invent
facts. Choose what to retain within the stated memory-token allowance, which
applies to the complete actor-visible rendering, including formatting. Return
only the replacement memory in the required format, without commentary or code
fences. At [INITIAL_OBSERVATION], inventory is empty: visible objects are not
carried. Opening or examining a container or object does not take its contents.
Only record an item as carried after a successful 'take X' action and observation
confirm that item was taken, or if previous memory already established it.
Taking a new item adds it without removing earlier carried items; putting one
down removes it. Never mark an item taken from mere visibility or recipe text.
At [INITIAL_OBSERVATION], no recipe preparation is complete. Preserve the
completion state of each recipe direction from previous memory unless the new
action and observation explicitly complete that direction. A 'take', 'open',
'examine', or 'read' action never slices, chops, cooks, or prepares an item.
Only record a direction complete after its matching successful preparation
action and confirming observation. Keep the earliest unfinished direction.
Never infer that an item is missing from inventory merely because it is absent
from the room description. Remove stale location or container claims after a
take/open action. Prioritize recipe, inventory, and progress over room furniture
when space is tight. An empty memory is permitted. There is no other persistent
notebook. When a successful 'prepare meal' action adds the meal to inventory,
the recipe ingredients become the meal: record the meal as carried and mark
'prepare meal' complete."""


def _prose_section(text: str, heading: str) -> str | None:
    normalized = text.replace("\\n", "\n")
    match = re.search(rf"(?im)^\s*{re.escape(heading)}:\s*(.*?)(?=^\s*[A-Z][A-Za-z ]{{2,35}}:|\Z)",
                      normalized, re.S | re.M)
    return " ".join(match.group(1).lower().split()) if match else None


def _carried(text: str) -> set[str] | None:
    section = _prose_section(text, "Carried items")
    if section is None:
        return None
    if section in {"none", "none."}:
        return set()
    return {re.sub(r"\s*\(taken\)$", "", item.strip(" -.,"))
            for item in re.split(r",|\s+-\s+", section) if item.strip(" -.,")}


def _recipe_ingredients(text: str) -> set[str]:
    normalized = text.replace("\\n", "\n")
    match = re.search(r"(?ims)^\s*Ingredients:\s*(.*?)(?=^\s*Directions:|\Z)", normalized)
    if not match:
        return set()
    return {item.strip(" -.,").lower() for item in re.split(r"[,\n]", match.group(1))
            if item.strip(" -.,")}


def _meal_prepared(action: str, observation: str) -> bool:
    return (action == "prepare meal" and
            observation.lower().startswith("adding the meal to your inventory"))


def _expected_carried(previous: str, action: str, observation: str) -> set[str]:
    expected = set(_carried(previous) or ())
    if action.startswith("take ") and observation.lower().startswith("you take "):
        expected.add(action[5:].lower())
    elif action.startswith("put ") and observation.lower().startswith("you put "):
        expected.discard(action[4:].split(" in ")[0].lower())
    elif _meal_prepared(action, observation):
        expected.difference_update(_recipe_ingredients(previous))
        expected.add("meal")
    return expected


def _validate_prose_facts(previous: str, candidate: str, action: str, observation: str) -> None:
    prior_items = _carried(previous)
    candidate_items = _carried(candidate)
    prior_progress = _prose_section(previous, "Recipe progress")
    candidate_progress = _prose_section(candidate, "Recipe progress")
    # Older free-form test fixtures have no factual sections. A real writer
    # establishes both at reset; subsequent updates must retain them.
    if prior_items is None and prior_progress is None and action != "[INITIAL_OBSERVATION]":
        return
    if (action == "[INITIAL_OBSERVATION]" and candidate_items is None
            and candidate_progress is None):
        return
    recipe_source = observation if action == "[INITIAL_OBSERVATION]" else previous
    if "ingredients:" in recipe_source.lower() and "directions:" in recipe_source.lower():
        if "ingredients:" not in candidate.lower() or "directions:" not in candidate.lower():
            raise _InvalidMemory("recipe_dropped")
    if candidate_items is None or candidate_progress is None:
        raise _InvalidMemory("missing_carried_or_progress_section")
    if action == "[INITIAL_OBSERVATION]":
        if candidate_items or "none" not in candidate_progress:
            raise _InvalidMemory("initial_facts_not_empty")
        return
    if prior_items is None or prior_progress is None:
        raise _InvalidMemory("previous_facts_missing")
    expected = _expected_carried(previous, action, observation)
    if candidate_items != expected:
        raise _InvalidMemory("carried_items_disagree_with_action")
    if not action.startswith(("slice ", "chop ", "cook ", "prepare meal")):
        if candidate_progress != prior_progress:
            raise _InvalidMemory("recipe_progress_disagrees_with_action")
    elif prior_progress != "none complete" and prior_progress not in candidate_progress:
        raise _InvalidMemory("recipe_progress_dropped")
    if action.startswith(("examine ", "read ")):
        words = {w for w in re.findall(r"[a-z0-9]+", observation.lower()) if len(w) > 2}
        retained = set(re.findall(r"[a-z0-9]+", candidate.lower()))
        if words and len(words & retained) / len(words) < 0.85:
            raise _InvalidMemory("new_observation_dropped")


def _public_prose_fallback(previous: str, action: str, observation: str,
                           limit: int, model: Model) -> str | None:
    """Keep confirmed public facts when both writer generations fail."""
    base = previous.replace("\\n", "\n")
    # Writer output may place the recipe after these lines. Remove only the
    # superseded evidence lines, never the rest of the notebook.
    base = re.sub(r"(?im)^Latest (?:action|observation):[^\n]*(?:\n|$)", "", base).rstrip()
    carried = _carried(base)
    if carried is None or _prose_section(base, "Recipe progress") is None:
        return None
    expected = _expected_carried(base, action, observation)
    base = re.sub(r"(?im)^Carried items:.*$",
                  "Carried items: " + (", ".join(sorted(expected)) if expected else "none"),
                  base, count=1)
    if (action.startswith(("slice ", "chop ", "cook "))
            and observation.lower().startswith("you ")) or _meal_prepared(action, observation):
        prior = _prose_section(base, "Recipe progress") or "none complete"
        completed = action if prior == "none complete" else prior + ", " + action
        base = re.sub(r"(?im)^Recipe progress:.*$", "Recipe progress: " + completed,
                      base, count=1)
    if _meal_prepared(action, observation):
        base += "\nMeal prepared and carried; all listed preparation directions are complete."
    candidate = f"{base}\nLatest action: {action}\nLatest observation: {observation}"
    if model.count_tokens(candidate) > limit:
        recipe_start = base.find("Initial recipe")
        if recipe_start < 0:
            recipe_start = base.find("Ingredients:")
        if recipe_start < 0:
            return None
        candidate = f"{base[recipe_start:]}\nLatest action: {action}\nLatest observation: {observation}"
    return candidate if model.count_tokens(candidate) <= limit else None


def _structured_meal_state(previous: str, action: str, observation: str) -> dict | None:
    """Update only fields the writer already chose, using confirmed public evidence."""
    if not _meal_prepared(action, observation):
        return None
    state = _object(previous)
    inventory_key = _structured_inventory_key(state)
    if inventory_key is None:
        return None
    carried = state[inventory_key]
    recipe_status = state.get("recipe_status", state.get("recipe_progress"))
    ingredients = recipe_status.get("ingredients") if isinstance(recipe_status, dict) else None
    required = set(ingredients) if isinstance(ingredients, dict) else set()
    state[inventory_key] = sorted((set(carried) - required) | {"meal"})
    directions = recipe_status.get("directions") if isinstance(recipe_status, dict) else None
    if isinstance(directions, dict) and "prepare meal" in directions:
        directions["prepare meal"] = True
    return state


def _structured_inventory_key(state: dict) -> str | None:
    for key in ("carried_items", "inventory"):
        value = state.get(key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return key
    return None


def _validate_structured_facts(previous: str, candidate: str,
                               action: str, observation: str) -> None:
    expected = _structured_meal_state(previous, action, observation)
    if expected is None:
        return
    actual = _object(candidate)
    expected_key = _structured_inventory_key(expected)
    actual_key = _structured_inventory_key(actual)
    # Order is irrelevant for an inventory list, but every carried tool remains.
    if (actual_key is None or
            set(actual[actual_key]) != set(expected[expected_key])):
        raise _InvalidMemory("structured_meal_inventory_stale")
    actual_status = actual.get("recipe_status", actual.get("recipe_progress"))
    actual_directions = (actual_status.get("directions")
                         if isinstance(actual_status, dict) else None)
    if isinstance(actual_directions, dict) and actual_directions.get("prepare meal") is False:
        raise _InvalidMemory("structured_meal_progress_stale")
    if actual.get("meal_prepared") is False:
        raise _InvalidMemory("structured_meal_progress_stale")


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
            "version": 16,
            "prompt_version": PROMPT_VERSION,
            "is_fake": False,
            "max_repairs": 1,
            "fallback": ("public_evidence_then_previous_valid_memory"
                         if self.strategy in {"prose", "structured"} else
                         "previous_valid_memory"),
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

    def update(self, previous_memory: str, action: str, observation: str,
               context: MemoryContext, model: Model) -> MemoryUpdate:
        limit = context.memory_token_limit
        if type(limit) is not int or limit < 1:
            raise ValueError("memory_token_limit must be a positive integer")
        # The caller supplies a valid predecessor (empty() on initialization).
        # Do not conceal an invalid predecessor or an unusably small allowance.
        previous_rendered = self.render(previous_memory)
        _within_budget(previous_rendered, limit, model)
        messages = (
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
        events = []
        for attempt in range(2):
            purpose = "memory" if attempt == 0 else "memory_repair"
            # Transport/model/tokenizer errors propagate to the runner; they
            # must not masquerade as a valid gameplay memory fallback.
            generation = model.generate(messages, purpose=purpose)
            try:
                state, rendered = self._prepare(generation.text)
                _within_budget(rendered, limit, model)
                if self.strategy == "prose":
                    _validate_prose_facts(previous_memory, state, action, observation)
                elif self.strategy == "structured":
                    _validate_structured_facts(previous_memory, state, action, observation)
            except _InvalidMemory as error:
                events.append(f"{purpose}_rejected:{error}")
                if attempt == 0:
                    fact_hint = ""
                    if self.strategy == "prose" and str(error) == "carried_items_disagree_with_action":
                        expected = _expected_carried(previous_memory, action, observation)
                        fact_hint = (" Set 'Carried items:' to exactly "
                                     + (", ".join(sorted(expected)) if expected else "none")
                                     + ". This action cannot remove previously carried items.")
                    elif self.strategy == "prose" and str(error) == "recipe_progress_disagrees_with_action":
                        fact_hint = (" Keep 'Recipe progress:' exactly "
                                     + str(_prose_section(previous_memory, "Recipe progress"))
                                     + "; this action did not prepare an ingredient.")
                    elif self.strategy == "prose" and str(error) == "recipe_progress_dropped":
                        fact_hint = (" Keep all earlier completed steps from 'Recipe progress:' "
                                     + str(_prose_section(previous_memory, "Recipe progress"))
                                     + " and append this newly completed step.")
                    elif self.strategy == "prose" and str(error) == "recipe_dropped":
                        fact_hint = (" Preserve the complete Ingredients and Directions "
                                     "from the previous memory or initial observation.")
                    elif self.strategy == "prose" and str(error) == "new_observation_dropped":
                        fact_hint = (" Preserve this new public observation: "
                                     + observation + ".")
                    elif self.strategy == "structured" and str(error).startswith("structured_meal_"):
                        fact_hint = (" The successful prepare meal action added the meal to "
                                     "inventory. Replace the recipe ingredients in carried_items "
                                     "with meal and mark the prepare meal direction complete.")
                    messages = (*messages, Message("assistant", generation.text),
                                Message("user", f"Candidate rejected: {error}. Rewrite using "
                                        "the same supplied evidence and required format. The "
                                        f"complete rendering must fit {limit} tokens.{fact_hint} Return "
                                        "only the replacement memory."))
            else:
                if state != generation.text:
                    events.append(f"{purpose}_json_canonicalized")
                events.append(f"{purpose}_accepted")
                return MemoryUpdate(state, tuple(events))
        if (self.strategy == "prose" and action == "[INITIAL_OBSERVATION]"
                and not previous_memory and "Ingredients:" in observation
                and "Directions:" in observation):
            recipe_start = observation.index("Initial recipe") if "Initial recipe" in observation else observation.index("Ingredients:")
            initial = (observation[recipe_start:].rstrip() + "\nCarried items: none\n"
                       "Recipe progress: none complete")
            _within_budget(initial, limit, model)
            events.append("memory_fallback:initial_public_observation")
            return MemoryUpdate(initial, tuple(events))
        if self.strategy == "prose":
            public = _public_prose_fallback(previous_memory, action, observation, limit, model)
            if public is not None:
                events.append("memory_fallback:public_evidence")
                return MemoryUpdate(public, tuple(events))
        if self.strategy == "structured":
            public_state = _structured_meal_state(previous_memory, action, observation)
            if public_state is not None:
                # Once meal preparation is confirmed, the old recipe and room
                # objects are no longer needed to represent the current state.
                inventory_key = _structured_inventory_key(public_state)
                compact = {inventory_key: public_state[inventory_key],
                           "meal_prepared": True}
                if isinstance(public_state.get("location"), str):
                    compact["location"] = public_state["location"]
                public = _serialize(compact)
                try:
                    _within_budget(public, limit, model)
                except _InvalidMemory:
                    pass
                else:
                    events.append("memory_fallback:public_evidence")
                    return MemoryUpdate(public, tuple(events))
        events.append("memory_fallback:previous_valid_memory")
        return MemoryUpdate(previous_memory, tuple(events))


class ProseMemory(_BoundedMemory):
    """Natural-language notebook; text (including whitespace) is preserved."""

    __slots__ = ()
    strategy = "prose"
    format_instructions = (
        "Return only the updated natural-language notebook text. Include exact "
        "lines 'Carried items: none' or 'Carried items: item, item' and "
        "'Recipe progress: none complete' or a concise completed-step list. "
        "It is rendered verbatim, including whitespace."
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


class HybridMemory(_BoundedMemory):
    """Two stores in a syntax-only envelope; all facts are rendered and counted."""

    __slots__ = ()
    strategy = "hybrid"
    format_instructions = (
        'Return one JSON object with exactly two keys: "prose" (a notebook string) '
        'and "structured" (an object with your own keys and nested JSON values). '
        "Use unique keys, finite numbers, compact JSON, sorted keys, and literal "
        "Unicode. Both stores may be empty. The actor-visible rendering is exactly "
        "Prose:\n<prose content>\nStructured JSON:\n<compact sorted structured object>. "
        "The two stores share ONE total allowance, including both labels and all "
        "newlines and JSON formatting. Allocate the allowance between stores yourself. "
        "Write exact quantities as strings if decimal-to-float formatting would change them."
    )

    def empty(self) -> str:
        return '{"prose":"","structured":{}}'

    def _prepare(self, memory: str) -> tuple[str, str]:
        obj = _object(memory)
        if (set(obj) != {"prose", "structured"}
                or not isinstance(obj["prose"], str)
                or not isinstance(obj["structured"], dict)):
            raise _InvalidMemory("invalid_hybrid_shape")
        state = _serialize(obj)
        rendered = f"Prose:\n{obj['prose']}\nStructured JSON:\n{_serialize(obj['structured'])}"
        return state, rendered
