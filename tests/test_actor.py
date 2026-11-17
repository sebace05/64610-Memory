"""Versioned actor policy, reason-specific repair, and visible-evidence isolation."""

import pytest

from game_memory.actor import PromptedActor, validate_action_output
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


def test_unknown_prompt_version_is_rejected():
    with pytest.raises(ValueError, match="prompt_version"):
        PromptedActor(prompt_version="unknown")


RECIPE_OBSERVATION = (
    "Gather all following ingredients and follow the directions to prepare this tasty meal.\n\n"
    "Ingredients:\n chicken wing\n red apple\n\nDirections:\n grill the chicken wing\n"
    "slice the red apple\n roast the red apple\n prepare meal"
)
RECIPE_MEMORY = (
    "Ingredients chicken wing red apple. Directions grill the chicken wing, "
    "slice the red apple, roast the red apple, prepare meal."
)


@pytest.mark.parametrize("full_history", [False, True])
def test_repeated_legal_inspection_is_executed_without_repair(full_history):
    actor = PromptedActor(full_history=full_history, prompt_version="v31")
    view = AgentView(RECIPE_OBSERVATION, "Prepare and eat the meal.",
                     ("examine cookbook", "open fridge"), 9, 2)
    for _ in range(3):
        model = Responses('{"action":"examine cookbook"}')
        assert actor.choose_action(view, RECIPE_MEMORY, model) == "examine cookbook"
        assert [purpose for _, purpose in model.calls] == ["action"]
    assert actor.metadata["repeated_observation_guard"].startswith("disabled")


def test_v31_only_canonicalizes_optional_article_to_exact_allowed_action():
    from game_memory.actor import validate_action_output

    allowed = ("slice red apple", "slice green apple", "examine cookbook")
    raw = '{"action":"slice the red apple"}'
    assert validate_action_output(raw, allowed) == ("slice the red apple", "unavailable_action")
    assert validate_action_output(raw, allowed, allow_optional_article=True) == ("slice red apple", None)
    assert validate_action_output('{"action":"slice the blue apple"}', allowed,
                                  allow_optional_article=True)[1] == "unavailable_action"
    actor = PromptedActor(prompt_version="v31")
    view = AgentView("You carry the apple and knife.", "Prepare the meal.", allowed, 10, 2)
    model = Responses('{"next_direction":"slice the red apple",'
                      '"missing_prerequisite":null,"action":"slice the red apple"}')
    assert actor.choose_action(view, "Carried items: red apple, knife", model) == "slice red apple"
    assert actor.metadata["action_output_policy"] == "optional_article_exact_match_v1"


def test_state_change_invalidates_stale_inspection_result():
    actor = PromptedActor(prompt_version="v31")
    goal = "Prepare and eat the meal."
    allowed = ("examine fridge", "open fridge")
    actor.choose_action(AgentView("The fridge is closed.", goal, allowed, 10, 2),
                        "The fridge is closed.", Responses('{"action":"examine fridge"}'))
    actor.choose_action(AgentView("a fridge that is closed", goal, allowed, 9, 2),
                        "The fridge is closed.", Responses('{"action":"open fridge"}'))

    changed = Responses('{"action":"examine fridge"}')
    assert actor.choose_action(AgentView("The fridge is open and contains chicken.", goal,
                                         allowed, 8, 2),
                               "The fridge was closed; now it is open and contains chicken.",
                               changed) == "examine fridge"
    assert len(changed.calls) == 1


@pytest.mark.parametrize("memory", ["", "Remember the meal.", '{"notes":"meal"}'])
def test_v31_keeps_legal_rereads_and_repeated_information_actions(memory):
    actor = PromptedActor(prompt_version="v31")
    for _ in range(3):
        model = Responses('{"action":"examine cookbook"}')
        assert actor.choose_action(view(), memory, model) == "examine cookbook"
        assert len(model.calls) == 1
        assert '"examine cookbook"' in model.calls[0][0][1].content


def test_v31_policy_is_format_neutral_and_does_not_force_recovery():
    prompts = []
    for memory in ("The apple is carried; roast it.", '{"arbitrary":["apple carried","roast"]}'):
        model = Responses('{"action":"inventory"}')
        assert PromptedActor(prompt_version="v31").choose_action(view(), memory, model) == "inventory"
        prompts.append(model.calls[0][0][0].content)
        assert model.calls[0][0][1].content.endswith(memory)
    assert prompts[0] == prompts[1]
    assert "missing or uncertain" in prompts[0]
    assert "without a forced reread" in prompts[0]
    assert "no particular headings or keys" in prompts[0]
    assert "grilling uses toaster" in prompts[0]


@pytest.mark.parametrize("full_history", [False, True])
def test_v31_review_and_repair_use_only_supplied_evidence(full_history):
    actor = PromptedActor(prompt_version="v31", full_history=full_history)
    current = AgentView("CURRENT_PUBLIC", "Prepare the meal.",
                        ("prepare meal", "inventory", "examine cookbook"), 10, 2)
    # A prior turn must not supply evidence to either review or repair.
    actor.choose_action(view("OLD_SECRET"), "OLD_MEMORY",
                        Responses('{"action":"examine cookbook"}'))
    model = Responses('{"action":"take unavailable item"}',
                      '{"action":"prepare meal"}', '{"action":"inventory"}')
    assert actor.choose_action(current, "SUPPLIED_CONTEXT", model) == "inventory"
    assert [purpose for _, purpose in model.calls] == ["action", "action_repair", "action_review"]
    primary, repair, review = [messages for messages, _ in model.calls]
    assert repair[1].content == primary[1].content + "\nPrevious unavailable proposal: take unavailable item"
    assert review[1] == repair[1]
    for messages, _ in model.calls:
        assert len(messages) == 2
        content = "\n".join(message.content for message in messages)
        assert "CURRENT_PUBLIC" in content and "SUPPLIED_CONTEXT" in content
        assert "OLD_SECRET" not in content and "OLD_MEMORY" not in content
        assert ("visible interaction history" in messages[0].content) == full_history


def test_v31_prior_turns_cannot_change_requests_even_after_repair():
    used = PromptedActor(prompt_version="v31")
    used.choose_action(view("OLD_FACT"), "OLD_NOTES",
                       Responses('{"action":"examine cookbook"}'))
    used.choose_action(view("OLD_RECIPE"), "OLD_INVENTORY",
                       Responses('bad', '{"action":"inventory"}'))
    used_model, fresh_model = Responses('{"action":"inventory"}'), Responses('{"action":"inventory"}')
    assert used.choose_action(view(), "ONLY_MEMORY", used_model) == "inventory"
    assert PromptedActor(prompt_version="v31").choose_action(view(), "ONLY_MEMORY", fresh_model) == "inventory"
    assert used_model.calls == fresh_model.calls


@pytest.mark.parametrize("invalid", ['bad', '{"action":false}', '{"action":"unavailable"}'])
def test_v31_failed_repair_never_substitutes_a_useful_action(invalid):
    model = Responses(invalid, invalid)
    result = PromptedActor(prompt_version="v31").choose_action(view(), "notes", model)
    assert result == "[INVALID_ACTION_OUTPUT] " + invalid
    assert [purpose for _, purpose in model.calls] == ["action", "action_repair"]


def test_v31_diagnostic_and_bounded_instructions_differ_only_in_context_label():
    runs = []
    for full_history in (False, True):
        model = Responses('{"action":"unavailable"}', '{"action":"prepare meal"}',
                          '{"action":"inventory"}')
        PromptedActor(prompt_version="v31", full_history=full_history).choose_action(view(), "context", model)
        runs.append(model.calls)
    for (bounded, purpose), (history, history_purpose) in zip(*runs):
        assert purpose == history_purpose
        assert bounded[0].content.replace("supplied memory", "CONTEXT") == history[0].content.replace(
            "supplied visible interaction history", "CONTEXT")
        assert bounded[1].content.replace("Bounded memory:", "CONTEXT:") == history[1].content.replace(
            "Visible interaction history (diagnostic):", "CONTEXT:")


def test_v31_keeps_model_approved_prepare_meal():
    current = AgentView("Ready to prepare.", "Prepare and eat the meal.",
                        ("prepare meal", "inventory"), 10, 2)
    model = Responses('{"action":"prepare meal"}', '{"action":"prepare meal"}')
    assert PromptedActor(prompt_version="v31").choose_action(current, "notes", model) == "prepare meal"
    assert [purpose for _, purpose in model.calls] == ["action", "action_review"]
    assert model.calls[0][0][1] == model.calls[1][0][1]


@pytest.mark.parametrize("failure_purpose,outputs", [
    ("action", ()),
    ("action_review", ('{"action":"prepare meal"}',)),
    ("action_repair", ('{"action":"unavailable"}',)),
])
def test_v31_model_errors_propagate_without_action_substitution(failure_purpose, outputs):
    class FailingModel(Responses):
        def generate(self, messages, *, purpose):
            if purpose == failure_purpose:
                raise RuntimeError("inference failed")
            return super().generate(messages, purpose=purpose)

    with pytest.raises(RuntimeError, match="inference failed"):
        PromptedActor(prompt_version="v31").choose_action(
            AgentView("Current room.", "Prepare and eat the meal.",
                      ("prepare meal", "inventory"), 10, 2), "notes", FailingModel(*outputs))


@pytest.mark.parametrize('full_history', [False, True])
def test_v31_unavailable_prepare_skips_review_and_repairs_to_model_choice(full_history):
    current = AgentView('Adding the meal to your inventory.', 'Prepare and eat.',
                        ('eat meal', 'inventory'), 71, 2)
    model = Responses('{"action":"prepare meal"}', '{"action":"eat meal"}')
    actor = PromptedActor(prompt_version='v31', full_history=full_history)
    assert actor.choose_action(current, 'SUPPLIED', model) == 'eat meal'
    assert [purpose for _, purpose in model.calls] == ['action', 'action_repair']


def test_v31_does_not_force_eating_or_rescue_failed_repair():
    current = AgentView('Adding the meal to your inventory.', 'Prepare and eat.',
                        ('eat meal', 'inventory'), 71, 2)
    actor = PromptedActor(prompt_version='v31')
    assert actor.choose_action(current, '', Responses('{"action":"inventory"}')) == 'inventory'
    result = actor.choose_action(current, '', Responses('{"action":"prepare meal"}',
                                                       '{"action":"prepare meal"}'))
    assert result.startswith('[INVALID_ACTION_OUTPUT]')


def test_v31_legal_prepare_is_still_reviewed_and_review_output_validated():
    current = AgentView('You take salt.', 'Prepare and eat.', ('prepare meal', 'inventory'), 72, 2)
    model = Responses('{"action":"prepare meal"}', '{"action":"eat meal"}',
                      '{"action":"inventory"}')
    assert PromptedActor(prompt_version='v31').choose_action(current, '', model) == 'inventory'
    assert [purpose for _, purpose in model.calls] == ['action', 'action_review', 'action_repair']


def test_v31_primary_instruction_matches_pre_iteration_snapshot():
    import hashlib
    import json
    from pathlib import Path

    expected = json.loads((Path(__file__).parent / "fixtures/actor-v31-primary-hashes.json").read_text())
    for full_history in (False, True):
        model = Responses('{"action":"inventory"}')
        PromptedActor(prompt_version="v31", full_history=full_history).choose_action(view(), "MEMORY", model)
        assert hashlib.sha256(model.calls[0][0][0].content.encode()).hexdigest() == expected[str(full_history)]


from dataclasses import asdict
import json
from pathlib import Path

_PARITY = json.loads((Path(__file__).parent / "fixtures/v31-core-parity.json").read_text())


@pytest.mark.parametrize("case", _PARITY["cases"], ids=lambda c: c["context_mode"] + "-" + c["name"])
def test_precleanup_v31_exact_calls_actions_metadata_and_turn_isolation(case):
    actor = PromptedActor(context_mode=case["context_mode"])
    for turn in case["turns"]:
        model = Responses(*turn["responses"])
        values = dict(turn["view"])
        values["allowed_actions"] = tuple(values["allowed_actions"])
        assert actor.choose_action(AgentView(**values), turn["memory"], model) == turn["expected_action"]
        calls = [{"purpose": purpose, "messages": [asdict(m) for m in messages]}
                 for messages, purpose in model.calls]
        assert calls == turn["expected_calls"]
        assert actor.metadata == turn["expected_metadata"]
        assert list(model.texts) == []


@pytest.mark.parametrize("policy", ["v1", "v2-mechanics", *[f"v{i}" for i in range(2, 31)], "v32"])
def test_retired_policies_are_rejected(policy):
    with pytest.raises(ValueError, match="prompt_version"):
        PromptedActor(prompt_version=policy)


@pytest.mark.parametrize("mode", ["history_window", "hybrid", "unknown"])
def test_unsupported_context_is_rejected(mode):
    with pytest.raises(ValueError, match="context mode"):
        PromptedActor(context_mode=mode)


def test_contradictory_context_arguments_are_rejected():
    with pytest.raises(ValueError, match="contradicts"):
        PromptedActor(full_history=True, context_mode="bounded_memory")
