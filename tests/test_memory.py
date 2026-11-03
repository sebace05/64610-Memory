"""P1 format/update tests with controlled counters, not Qwen tokenization."""

from dataclasses import replace
import json

import pytest

from game_memory.components import Generation, MemoryContext
from game_memory.memory import HybridMemory, ProseMemory, StructuredMemory
from game_memory.runner import _LoggedModel


STRATEGIES = (ProseMemory, StructuredMemory, HybridMemory)
CONTEXT = MemoryContext("Prepare the meal.", 80, 2, 256)
ACTION = "[INITIAL_OBSERVATION]"
OBSERVATION = "Recipe: dice and grill the cheese."
NOTE = "Dice and grill cheese."


class ScriptedModel:
    """Every generation must consume an explicit response from the test."""

    def __init__(self, outputs, counter=len):
        self.outputs = iter(outputs)
        self.counter = counter
        self.calls = []
        self.counted = []

    @property
    def metadata(self):
        return {"implementation": "ScriptedModel", "is_fake": True,
                "tokenizer": "controlled_test_counter_not_qwen"}

    def count_tokens(self, text):
        self.counted.append(text)
        return self.counter(text)

    def generate(self, messages, *, purpose):
        self.calls.append((tuple(messages), purpose))
        text = next(self.outputs)  # An unexpected third call fails the test.
        if isinstance(text, Exception):
            raise text
        return Generation(text, sum(len(m.content) for m in messages), len(text), 0.25)


def state_with_note(memory, note=NOTE):
    if isinstance(memory, ProseMemory):
        return note
    obj = {"note": note}
    if isinstance(memory, HybridMemory):
        obj = {"prose": note, "structured": {}}
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sized_candidate(memory, size):
    """Create a candidate whose complete rendering has exactly size characters."""
    overhead = len(memory.render(state_with_note(memory, "")))
    return state_with_note(memory, "x" * (size - overhead))


def update(memory, outputs, *, previous=None, context=CONTEXT, counter=len):
    model = ScriptedModel(outputs, counter)
    result = memory.update(memory.empty() if previous is None else previous,
                           ACTION, OBSERVATION, context, model)
    return result, model


@pytest.mark.parametrize("factory,state,rendered", [
    (ProseMemory, "", ""),
    (StructuredMemory, "{}", "{}"),
    (HybridMemory, '{"prose":"","structured":{}}', "Prose:\n\nStructured JSON:\n{}"),
])
def test_empty_states_are_deterministic_and_have_no_task_information(factory, state, rendered):
    memory = factory()
    assert memory.empty() == state == memory.empty()
    assert memory.render(state) == rendered == memory.render(state)
    metadata = memory.metadata
    assert metadata["strategy"] in {"prose", "structured", "hybrid"}
    assert metadata["is_fake"] is False and metadata["max_repairs"] == 1
    assert metadata["prompt_version"] and metadata["render_version"]
    json.dumps(metadata)


@pytest.mark.parametrize("factory", STRATEGIES)
def test_all_three_process_same_fixture_under_shared_256_allowance(factory):
    memory = factory()
    state = state_with_note(memory)
    result, model = update(memory, [state])
    assert result.memory == state
    assert result.events == ("memory_accepted",)
    assert NOTE in memory.render(result.memory)
    assert len(memory.render(result.memory)) <= 256
    assert [purpose for _, purpose in model.calls] == ["memory"]
    messages = model.calls[0][0]
    payload = json.loads(messages[1].content)
    assert payload == {
        "previous_memory": memory.render(memory.empty()),
        "action": ACTION,
        "observation": OBSERVATION,
        "context": {"goal": CONTEXT.goal, "budget_remaining": 80,
                    "recheck_cost": 2, "memory_token_limit": 256},
    }
    assert model.counted[-1] == memory.render(result.memory)


def test_writer_substantive_instructions_and_evidence_match_across_formats():
    instructions = []
    evidence = []
    for factory in STRATEGIES:
        memory = factory()
        _, model = update(memory, [state_with_note(memory)])
        messages = model.calls[0][0]
        instructions.append(messages[0].content.split("\n\nRequired format:\n")[0])
        payload = json.loads(messages[1].content)
        payload.pop("previous_memory")  # Only representation differs.
        evidence.append(payload)
    assert instructions[0] == instructions[1] == instructions[2]
    assert evidence[0] == evidence[1] == evidence[2]


def test_prose_preserves_content_and_whitespace_verbatim():
    text = '  Remember “café”.\nUse "quoted" notes.\n'
    memory = ProseMemory()
    result, model = update(memory, [text], previous="Old notebook.")
    assert result.memory == memory.render(text) == text
    assert json.loads(model.calls[0][0][1].content)["previous_memory"] == "Old notebook."


def test_empty_prose_is_a_valid_deliberate_update():
    result, model = update(ProseMemory(), [""], previous=NOTE)
    assert result.memory == "" and result.events == ("memory_accepted",)
    assert len(model.calls) == 1


def test_json_parses_nested_general_values_and_logs_canonical_formatting():
    raw = ' { "z": [1, true, null, {"b": 2, "a": 1}], "a": "café" }\n'
    expected = '{"a":"café","z":[1,true,null,{"a":1,"b":2}]}'
    memory = StructuredMemory()
    result, model = update(memory, [raw])
    assert result.memory == expected
    assert json.loads(result.memory) == json.loads(raw)
    assert result.events == ("memory_json_canonicalized", "memory_accepted")
    assert memory.render(raw) == memory.render(expected) == expected
    assert memory.render(memory.render(raw)) == expected
    assert model.counted[-1] == expected


def test_json_whitespace_inside_values_is_preserved_and_counted():
    raw = '{ "note": "  keep spaces\\n" }'
    expected = '{"note":"  keep spaces\\n"}'
    result, model = update(StructuredMemory(), [raw])
    assert result.memory == expected
    assert model.counted[-1] == expected


@pytest.mark.parametrize("factory", (StructuredMemory, HybridMemory))
@pytest.mark.parametrize("number", (
    "9007199254740993.0", "1e-400", "0.10000000000000001",
))
def test_numeric_value_change_requests_repair_instead_of_corrupting_fact(factory, number):
    memory = factory()
    raw = f'{{"quantity":{number}}}'
    if isinstance(memory, HybridMemory):
        raw = f'{{"prose":"","structured":{raw}}}'
    replacement = state_with_note(memory, f"Quantity {number}.")
    result, model = update(memory, [raw, replacement])
    assert result.memory == replacement
    assert number in memory.render(result.memory)
    assert result.events == ("memory_rejected:json_number_changed",
                             "memory_repair_accepted")
    assert [purpose for _, purpose in model.calls] == ["memory", "memory_repair"]


@pytest.mark.parametrize("factory", (StructuredMemory, HybridMemory))
def test_equivalent_decimal_formatting_remains_valid(factory):
    memory = factory()
    raw = '{"quantity":1.2300}'
    if isinstance(memory, HybridMemory):
        raw = '{"prose":"","structured":{"quantity":1.2300}}'
    result, _ = update(memory, [raw])
    assert "1.23" in memory.render(result.memory)
    assert "1.2300" not in memory.render(result.memory)


@pytest.mark.parametrize("factory", (StructuredMemory, HybridMemory))
def test_unrepresentable_json_number_accepts_valid_repair(factory):
    memory = factory()
    extreme = '{"n":1e-9999999999999999999}'
    if isinstance(memory, HybridMemory):
        extreme = '{"prose":"","structured":{"n":1e-9999999999999999999}}'
    replacement = state_with_note(memory, "Retain exact quantity as text")

    result, model = update(memory, [extreme, replacement])

    assert result.memory == replacement
    assert result.events == ("memory_rejected:json_number_unrepresentable",
                             "memory_repair_accepted")
    assert [purpose for _, purpose in model.calls] == ["memory", "memory_repair"]


@pytest.mark.parametrize("factory", (StructuredMemory, HybridMemory))
def test_unrepresentable_json_number_then_bad_repair_retains_exact_previous(factory):
    memory = factory()
    extreme = '{"n":1e-9999999999999999999}'
    if isinstance(memory, HybridMemory):
        extreme = '{"prose":"","structured":{"n":1e-9999999999999999999}}'
    previous = state_with_note(memory, "Keep this earlier fact")

    result, model = update(memory, [extreme, "malformed repair"], previous=previous)

    assert result.memory == previous
    assert result.events == ("memory_rejected:json_number_unrepresentable",
                             "memory_repair_rejected:malformed_json",
                             "memory_fallback:previous_valid_memory")
    assert len(model.calls) == 2


@pytest.mark.parametrize("factory", (StructuredMemory, HybridMemory))
def test_unrepresentable_json_number_initialization_falls_back_to_empty(factory):
    memory = factory()
    extreme = '{"n":1e-9999999999999999999}'
    if isinstance(memory, HybridMemory):
        extreme = '{"prose":"","structured":{"n":1e-9999999999999999999}}'

    result, model = update(memory, [extreme, "malformed repair"])

    assert result.memory == memory.empty()
    assert result.events == ("memory_rejected:json_number_unrepresentable",
                             "memory_repair_rejected:malformed_json",
                             "memory_fallback:previous_valid_memory")
    assert len(model.calls) == 2


def test_hybrid_render_is_deterministic_and_preserves_duplicate_facts():
    raw = ' {"structured": {"z": 2, "a": "Same fact."}, "prose": "Same fact."} '
    expected = 'Prose:\nSame fact.\nStructured JSON:\n{"a":"Same fact.","z":2}'
    memory = HybridMemory()
    result, model = update(memory, [raw])
    assert memory.render(result.memory) == expected == memory.render(raw)
    assert json.loads(result.memory) == json.loads(raw)
    assert expected.count("Same fact.") == 2
    assert model.counted[-1] == expected
    assert result.events == ("memory_json_canonicalized", "memory_accepted")


@pytest.mark.parametrize("factory", STRATEGIES)
def test_exactly_256_counted_tokens_is_accepted(factory):
    memory = factory()
    candidate = sized_candidate(memory, 256)
    result, model = update(memory, [candidate])
    assert result.memory == candidate
    assert len(memory.render(result.memory)) == 256
    assert len(model.calls) == 1


@pytest.mark.parametrize("factory", STRATEGIES)
def test_one_counted_token_over_budget_is_rejected_without_truncation(factory):
    memory = factory()
    candidate = sized_candidate(memory, 257)
    result, model = update(memory, [candidate, candidate])
    assert result.memory == memory.empty()
    assert result.events == ("memory_rejected:over_budget:257>256",
                             "memory_repair_rejected:over_budget:257>256",
                             "memory_fallback:previous_valid_memory")
    assert memory.render(candidate) in model.counted
    assert [purpose for _, purpose in model.calls] == ["memory", "memory_repair"]


def test_json_punctuation_and_keys_count_not_just_values():
    memory = StructuredMemory()
    candidate = '{"long_key":"x"}'
    # The value alone fits, but the complete canonical JSON does not.
    result, model = update(memory, [candidate, candidate],
                           context=replace(CONTEXT, memory_token_limit=len(candidate) - 1))
    assert result.memory == memory.empty()
    assert candidate in model.counted
    assert result.events[0].startswith("memory_rejected:over_budget:")


def test_hybrid_uses_one_combined_allowance_including_labels_and_separators():
    memory = HybridMemory()
    candidate = json.dumps({"prose": "x" * 130, "structured": {"note": "y" * 130}})
    prose = json.loads(candidate)["prose"]
    structured = json.dumps(json.loads(candidate)["structured"], separators=(",", ":"))
    assert len(prose) <= 256 and len(structured) <= 256
    rendered = f"Prose:\n{prose}\nStructured JSON:\n{structured}"
    assert len(rendered) > 256
    result, model = update(memory, [candidate, candidate])
    assert result.memory == memory.empty()
    assert rendered in model.counted
    # Labels alone also matter when both content portions otherwise fit.
    result, _ = update(memory, [candidate, candidate], context=replace(
        CONTEXT, memory_token_limit=len(prose) + len(structured)))
    assert result.events[0].startswith("memory_rejected:over_budget:")


def test_json_heavy_hybrid_uses_exact_combined_boundary():
    memory = HybridMemory()
    def candidate(size):
        base = '{"prose":"","structured":{"note":""}}'
        overhead = len(memory.render(base))
        return json.dumps({"prose": "", "structured": {"note": "x" * (size - overhead)}},
                          separators=(",", ":"))
    exact = candidate(256)
    oversized = candidate(257)
    assert len(memory.render(exact)) == 256
    assert len(memory.render(oversized)) == 257
    accepted, _ = update(memory, [exact])
    rejected, _ = update(memory, [oversized, oversized])
    assert accepted.memory == exact
    assert rejected.memory == memory.empty()


@pytest.mark.parametrize("raw,reason", [
    ("", "malformed_json"),
    ('```json\n{}\n```', "malformed_json"),
    ('{"note":', "malformed_json"),
    ('{"note":1,}', "malformed_json"),
    ('{} {}', "malformed_json"),
    ('Explanation: {"note":"fact"}', "malformed_json"),
    ('{"note":"fact"} explanation', "malformed_json"),
    ('[]', "json_object_required"),
    ('null', "json_object_required"),
    ('"not an object"', "json_object_required"),
    ('{"x":1,"x":2}', "duplicate_json_key"),
    ('{"a":[{"x":1,"x":2}]}', "duplicate_json_key"),
    ('{"x":NaN}', "nonfinite_json_number"),
    ('{"x":Infinity}', "nonfinite_json_number"),
    ('{"x":-Infinity}', "nonfinite_json_number"),
    ('{"x":1e400}', "nonfinite_json_number"),
    ('{"x":"\\ud800"}', "invalid_unicode"),
])
def test_structured_rejects_invalid_syntax_without_semantic_repair(raw, reason):
    result, model = update(StructuredMemory(), [raw, "{}"])
    assert result.memory == "{}"
    assert result.events == (f"memory_rejected:{reason}", "memory_repair_accepted")
    assert len(model.calls) == 2


def test_json_strings_preserve_escaped_quotes_braces_and_unicode_keys():
    memory = StructuredMemory()
    raw = '{"\\u03c0":"quote \\" and {braces}","emoji":"\\ud83d\\ude00"}'
    result, _ = update(memory, [raw])
    parsed = json.loads(result.memory)
    assert parsed == {"π": 'quote " and {braces}', "emoji": "😀"}
    assert result.memory == memory.render(raw)


@pytest.mark.parametrize("factory,raw", [
    (ProseMemory, "\ud800"),
    (HybridMemory, '{"prose":"\\ud800","structured":{}}'),
])
def test_unpaired_unicode_in_prose_content_requests_repair(factory, raw):
    memory = factory()
    replacement = memory.empty()
    result, _ = update(memory, [raw, replacement])
    assert result.memory == replacement
    assert result.events == ("memory_rejected:invalid_unicode", "memory_repair_accepted")


def test_very_long_single_value_is_checked_as_complete_json():
    memory = StructuredMemory()
    raw = json.dumps({"note": "x" * 100_000})
    result, model = update(memory, [raw, "{}"])
    assert result.memory == "{}"
    assert result.events[0].startswith("memory_rejected:over_budget:")
    assert memory.render(raw) in model.counted


@pytest.mark.parametrize("raw", [
    '{}',
    '{"prose":""}',
    '{"prose":"","structured":{},"hidden_fact":"secret"}',
    '{"prose":{},"structured":{}}',
    '{"prose":"","structured":[]}',
    '{"prose":"","structured":null}',
    '{"prose":"a","prose":"b","structured":{}}',
    '{"prose":"","structured":{"x":NaN}}',
])
def test_hybrid_rejects_invalid_envelopes_including_unrendered_extra_fields(raw):
    memory = HybridMemory()
    result, model = update(memory, [raw, memory.empty()])
    assert result.memory == memory.empty()
    assert result.events[0].startswith("memory_rejected:")
    assert result.events[-1] == "memory_repair_accepted"
    assert len(model.calls) == 2


@pytest.mark.parametrize("factory", STRATEGIES)
def test_overflow_repair_uses_same_evidence_and_accepts_valid_replacement(factory):
    memory = factory()
    previous = state_with_note(memory, "Previous fact.")
    rejected = sized_candidate(memory, 257)
    repaired = state_with_note(memory)
    result, model = update(memory, [rejected, repaired], previous=previous)
    assert result.memory == repaired
    assert result.events == ("memory_rejected:over_budget:257>256", "memory_repair_accepted")
    original, repair = (call[0] for call in model.calls)
    assert repair[:2] == original
    assert [m.role for m in repair] == ["system", "user", "assistant", "user"]
    assert repair[2].content == rejected
    assert "257>256" in repair[3].content


@pytest.mark.parametrize("factory", STRATEGIES)
def test_failed_repair_retains_exact_previous_valid_state_with_only_two_calls(factory):
    memory = factory()
    previous = state_with_note(memory, "Previously retained fact.")
    rejected = sized_candidate(memory, 257)
    result, model = update(memory, [rejected, rejected], previous=previous)
    assert result.memory == previous
    assert result.events[-1] == "memory_fallback:previous_valid_memory"
    assert len(model.calls) == 2


@pytest.mark.parametrize("factory", (StructuredMemory, HybridMemory))
def test_failed_malformed_initialization_falls_back_to_valid_empty_state(factory):
    memory = factory()
    result, model = update(memory, ["malformed", "still malformed"])
    assert result.memory == memory.empty()
    assert memory.render(result.memory) == memory.render(memory.empty())
    assert result.events[-1] == "memory_fallback:previous_valid_memory"
    assert len(model.calls) == 2


@pytest.mark.parametrize("factory", (StructuredMemory, HybridMemory))
def test_malformed_repair_retains_exact_nonempty_previous_state(factory):
    memory = factory()
    previous = state_with_note(memory, "Retained fact")
    result, model = update(memory, ["malformed", "still malformed"], previous=previous)
    assert result.memory == previous
    assert result.events == ("memory_rejected:malformed_json",
                             "memory_repair_rejected:malformed_json",
                             "memory_fallback:previous_valid_memory")
    assert len(model.calls) == 2


@pytest.mark.parametrize("factory", STRATEGIES)
def test_deleted_and_rejected_facts_do_not_enter_later_writer_prompts(factory):
    memory = factory()
    previous = state_with_note(memory, "DELETE_THIS_FACT")
    deleted = state_with_note(memory, "Current fact")
    first, _ = update(memory, [deleted], previous=previous)
    assert "DELETE_THIS_FACT" not in memory.render(first.memory)
    oversized = state_with_note(memory, "REJECTED_FACT" * 30)
    second, _ = update(memory, [oversized, oversized], previous=first.memory)
    assert second.memory == first.memory
    third, model = update(memory, [deleted], previous=second.memory)
    assert third.memory == deleted
    prompt = model.calls[0][0][1].content
    assert "DELETE_THIS_FACT" not in prompt
    assert "REJECTED_FACT" not in prompt
    assert json.loads(prompt)["previous_memory"] == memory.render(deleted)


@pytest.mark.parametrize("factory", STRATEGIES)
def test_reused_strategy_starts_new_episode_from_empty_state(factory):
    memory = factory()
    first, _ = update(memory, [state_with_note(memory, "EPISODE_ONE_ONLY")])
    assert "EPISODE_ONE_ONLY" in memory.render(first.memory)
    second, model = update(memory, [state_with_note(memory, "Second episode")],
                           previous=memory.empty())
    assert "Second episode" in memory.render(second.memory)
    assert "EPISODE_ONE_ONLY" not in model.calls[0][0][1].content


@pytest.mark.parametrize("factory", STRATEGIES)
def test_strategy_keeps_no_factual_python_state(factory):
    memory = factory()
    state = state_with_note(memory)
    result, model = update(memory, [state])
    assert not hasattr(memory, "__dict__")
    with pytest.raises(AttributeError):
        memory.hidden_fact = "Must not persist"
    assert memory.render(result.memory) == factory().render(result.memory)
    # Only the rendered predecessor, never a hidden envelope, enters the writer.
    _, next_model = update(memory, [memory.empty()], previous=result.memory)
    payload = json.loads(next_model.calls[0][0][1].content)
    assert payload["previous_memory"] == memory.render(result.memory)


def test_memory_and_repair_usage_are_visible_to_existing_logged_model():
    records = []
    model = ScriptedModel(["malformed", '{"note":"fixed"}'])
    logged = _LoggedModel(model, lambda event, **data: records.append({"event": event, **data}),
                          lambda: 0)
    memory = StructuredMemory()
    result = memory.update(memory.empty(), ACTION, OBSERVATION, CONTEXT, logged)
    assert result.memory == '{"note":"fixed"}'
    assert logged.by_purpose["memory"]["calls"] == 1
    assert logged.by_purpose["memory_repair"]["calls"] == 1
    responses = [r for r in records if r["event"] == "model_response"]
    assert logged.input_tokens == sum(r["input_tokens"] for r in responses)
    assert logged.output_tokens == sum(r["output_tokens"] for r in responses)
    assert logged.elapsed_seconds == 0.5
    assert [r["purpose"] for r in records if r["event"] == "model_request"] == [
        "memory", "memory_repair"]


@pytest.mark.parametrize("factory", STRATEGIES)
def test_supplied_counter_controls_acceptance_rather_than_builtin_length(factory):
    memory = factory()
    candidate = sized_candidate(memory, 100)
    result, _ = update(memory, [candidate], counter=lambda text: len(text) * 2)
    assert result.memory == candidate
    result, _ = update(memory, [candidate, candidate], counter=lambda text: len(text) * 3)
    assert result.memory == memory.empty()
    assert result.events[0] == "memory_rejected:over_budget:300>256"


@pytest.mark.parametrize("factory", STRATEGIES)
def test_model_errors_propagate_instead_of_becoming_memory_fallbacks(factory):
    memory = factory()
    model = ScriptedModel([TimeoutError("backend timeout")])
    with pytest.raises(TimeoutError, match="backend timeout"):
        memory.update(memory.empty(), ACTION, OBSERVATION, CONTEXT, model)
    assert len(model.calls) == 1


def test_counter_errors_propagate_even_during_candidate_validation():
    def counter(text):
        if text == NOTE:
            raise RuntimeError("tokenizer unavailable")
        return len(text)
    memory = ProseMemory()
    model = ScriptedModel([NOTE], counter)
    with pytest.raises(RuntimeError, match="tokenizer unavailable"):
        memory.update(memory.empty(), ACTION, OBSERVATION, CONTEXT, model)
    assert len(model.calls) == 1


@pytest.mark.parametrize("count", [-1, True, 1.5])
def test_invalid_counter_results_are_contract_errors(count):
    with pytest.raises(ValueError, match="invalid token count"):
        update(ProseMemory(), [NOTE], counter=lambda _: count)


@pytest.mark.parametrize("factory", STRATEGIES)
def test_oversized_predecessor_is_a_contract_error_before_generation(factory):
    memory = factory()
    model = ScriptedModel([])
    with pytest.raises(ValueError, match="over_budget"):
        memory.update(sized_candidate(memory, 257), ACTION, OBSERVATION, CONTEXT, model)
    assert not model.calls


def test_allowance_too_small_for_empty_representation_is_explicit():
    model = ScriptedModel([])
    memory = HybridMemory()
    with pytest.raises(ValueError, match="over_budget"):
        memory.update(memory.empty(), ACTION, OBSERVATION,
                      replace(CONTEXT, memory_token_limit=1), model)
    assert not model.calls


def test_invalid_predecessor_is_not_silently_replaced_with_empty_state():
    model = ScriptedModel([])
    with pytest.raises(ValueError, match="malformed_json"):
        StructuredMemory().update("invalid previous state", ACTION, OBSERVATION, CONTEXT, model)
    assert not model.calls


def test_model_error_during_repair_propagates_instead_of_falling_back():
    memory = StructuredMemory()
    model = ScriptedModel(["malformed", TimeoutError("repair timeout")])
    with pytest.raises(TimeoutError, match="repair timeout"):
        memory.update(memory.empty(), ACTION, OBSERVATION, CONTEXT, model)
    assert [purpose for _, purpose in model.calls] == ["memory", "memory_repair"]
