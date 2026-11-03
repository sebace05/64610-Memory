"""Versioned actor policy, reason-specific repair, and visible-evidence isolation."""

import pytest

from game_memory.actor import APPLIANCE_RULES, MECHANICS_PRIMER, PromptedActor, validate_action_output
from game_memory.components import Generation
from game_memory.contracts import AgentView


class Responses:
    def __init__(self, *texts):
        self.texts = iter(texts)
        self.calls = []

    def generate(self, messages, *, purpose):
        self.calls.append((tuple(messages), purpose))
        return Generation(next(self.texts), 0, 0, 0.0)


def view(observation="Current room.", budget=10):
    return AgentView(observation, "Prepare and eat the meal.",
                     ("move east", "examine cookbook", "inventory"), budget, 2)


@pytest.mark.parametrize("text,expected", [
    ('{"action":" MOVE   EAST "}', ("move east", None)),
    ('{"action":"take flour"}', ("take flour", "unavailable_action")),
    ('```json\n{"action":"move east"}\n```', (None, "malformed_json")),
    ('{"action":3}', (None, "invalid_action_schema")),
    ('{}', (None, "invalid_action_schema")),
    ('[]', (None, "invalid_action_schema")),
])
def test_output_classification_distinguishes_syntax_schema_and_availability(text, expected):
    assert validate_action_output(text, view().allowed_actions) == expected


def test_v1_preserves_original_system_and_generic_repair_text():
    model = Responses("malformed", '{"action":"move east"}')
    assert PromptedActor().choose_action(view(), "notes", model) == "move east"
    assert model.calls[0][0][0].content == (
        "Choose one permitted game action using only the current observation and memory. "
        "Recipe rereads consume the stated budget. "
        'Return only a JSON object of the form {"action": "exact permitted action"}.'
    )
    assert model.calls[1][0][-1].content == (
        "The output was malformed or not a permitted action. "
        "Return only the required JSON with one permitted action."
    )
    assert PromptedActor().metadata["prompt_version"] == "s2-action-v1"
    assert PromptedActor(full_history=True).metadata["prompt_version"] == "full-history-v1"


@pytest.mark.parametrize("text,reason", [
    ("not json", "not valid JSON"),
    ('{"action": false}', "action field is a string"),
    ('{"action":"take flour"}', "not in the current allowed_actions"),
])
def test_v2_repairs_use_the_actual_failure_reason_and_same_evidence(text, reason):
    model = Responses(text, '{"action":"move east"}')
    actor = PromptedActor(prompt_version="v2")
    assert actor.choose_action(view(), "visible notes", model) == "move east"
    original, repaired = (messages for messages, _ in model.calls)
    assert repaired[:2] == original
    assert repaired[2].content == text
    assert reason in repaired[-1].content
    assert [purpose for _, purpose in model.calls] == ["action", "action_repair"]
    assert actor.metadata["prompt_version"] == "s2-action-v2"


def test_v2_generic_mechanics_do_not_encode_the_development_seed_solution():
    model = Responses('{"action":"move east"}')
    PromptedActor(prompt_version="v2").choose_action(view(), "notes", model)
    instructions = model.calls[0][0][0].content
    assert "an item you put down is no longer carried" in instructions.lower()
    assert "budget_remaining" in instructions and "recheck_cost" in instructions
    assert "missing or uncertain" in instructions
    for seed_specific in ("flour", "water", "pantry", "east"):
        assert seed_specific not in instructions.lower()


def test_v2_instructions_match_across_context_modes_except_the_context_label():
    bounded, history = Responses('{"action":"inventory"}'), Responses('{"action":"inventory"}')
    PromptedActor(prompt_version="v2").choose_action(view(), "notes", bounded)
    PromptedActor(prompt_version="v2", full_history=True).choose_action(view(), "history", history)
    assert bounded.calls[0][0][0].content.replace("supplied memory", "supplied CONTEXT") == (
        history.calls[0][0][0].content.replace("supplied visible interaction history", "supplied CONTEXT"))


def test_v2_actor_keeps_no_previous_turns_or_hidden_plan():
    actor = PromptedActor(prompt_version="v2")
    first, second = Responses('{"action":"inventory"}'), Responses('{"action":"inventory"}')
    actor.choose_action(view("OLD_OBSERVATION"), "OLD_MEMORY", first)
    actor.choose_action(view("NEW_OBSERVATION"), "NEW_MEMORY", second)
    messages = second.calls[0][0]
    assert len(messages) == 2
    assert "OLD_OBSERVATION" not in messages[1].content
    assert "OLD_MEMORY" not in messages[1].content


def test_v2_does_not_replace_repeated_or_unaffordable_model_actions():
    actor = PromptedActor(prompt_version="v2")
    model = Responses(*(['{"action":"examine cookbook"}'] * 2))
    assert actor.choose_action(view(budget=3), "recipe", model) == "examine cookbook"
    assert actor.choose_action(view(budget=1), "recipe", model) == "examine cookbook"
    # The environment remains responsible for affordability and termination.
    assert len(model.calls) == 2


def test_v2_stops_after_one_failed_repair_without_substituting_a_command():
    model = Responses('{"action":"take flour"}', '{"action":"take flour"}')
    result = PromptedActor(prompt_version="v2").choose_action(view(), "notes", model)
    assert result == '[INVALID_ACTION_OUTPUT] {"action":"take flour"}'
    assert len(model.calls) == 2


def test_unknown_prompt_version_is_rejected():
    with pytest.raises(ValueError, match="prompt_version"):
        PromptedActor(prompt_version="unknown")


@pytest.mark.parametrize("full_history", [False, True])
def test_mechanics_candidate_only_prepends_rules_and_retains_v2_repair(full_history):
    original, candidate = Responses('not json', '{"action":"inventory"}'), Responses('not json', '{"action":"inventory"}')
    PromptedActor(full_history=full_history, prompt_version="v2").choose_action(view(), "notes", original)
    actor = PromptedActor(full_history=full_history, prompt_version="v2-mechanics")
    actor.choose_action(view(), "notes", candidate)
    for (before, purpose), (after, candidate_purpose) in zip(original.calls, candidate.calls):
        assert purpose == candidate_purpose
        assert after[0].content == MECHANICS_PRIMER + "\n\n" + before[0].content
        assert after[1:] == before[1:]
    assert actor.metadata["requires_unlimited_inventory"] is True
    for seed_specific in ("flour", "water", "pantry", "east", "west"):
        assert seed_specific not in MECHANICS_PRIMER.lower()


@pytest.mark.parametrize("full_history", [False, True])
@pytest.mark.parametrize("invalid", ['not json', '{"action":"take flour"}'])
def test_v3_only_adds_appliance_rules_to_the_same_input_and_repair(full_history, invalid):
    original, candidate = Responses(invalid, '{"action":"inventory"}'), Responses(invalid, '{"action":"inventory"}')
    PromptedActor(full_history=full_history, prompt_version="v2-mechanics").choose_action(view(), "notes", original)
    actor = PromptedActor(full_history=full_history, prompt_version="v3")
    assert actor.choose_action(view(), "notes", candidate) == "inventory"
    assert len(original.calls) == len(candidate.calls) == 2
    for (before, purpose), (after, candidate_purpose) in zip(original.calls, candidate.calls):
        assert candidate_purpose == purpose
        assert after[0].content == APPLIANCE_RULES + "\n\n" + before[0].content
        assert after[1:] == before[1:]
    assert actor.metadata["requires_unlimited_inventory"] is True
    for seed_specific in ("chicken", "wing", "fridge", "east", "west"):
        assert seed_specific not in APPLIANCE_RULES.lower()
