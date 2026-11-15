"""Versioned actor policy, reason-specific repair, and visible-evidence isolation."""

import pytest

from game_memory.actor import (APPLIANCE_RULES, CLOSED_CONTAINER_PRIORITY_RULE,
                               GLOBAL_RECIPE_ORDER_RULE, MEAL_FINALIZATION_RULE,
                               RECIPE_GOAL_PRECEDENCE_RULE, RECIPE_REREAD_RULE,
                               CLOSED_CONTAINER_RULES, MECHANICS_PRIMER,
                               ORDERED_RECIPE_RULES, TOOL_PREREQUISITE_RULES,
                               PromptedActor, validate_action_output)
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


@pytest.mark.parametrize("full_history", [False, True])
@pytest.mark.parametrize("invalid", ['not json', '{"action":"take flour"}'])
def test_v4_adds_ordered_prerequisite_rules_to_the_same_input_and_repair(full_history, invalid):
    original, candidate = Responses(invalid, '{"action":"inventory"}'), Responses(invalid, '{"action":"inventory"}')
    PromptedActor(full_history=full_history, prompt_version="v3").choose_action(view(), "notes", original)
    actor = PromptedActor(full_history=full_history, prompt_version="v4")
    assert actor.choose_action(view(), "notes", candidate) == "inventory"
    assert len(original.calls) == len(candidate.calls) == 2
    for (before, purpose), (after, candidate_purpose) in zip(original.calls, candidate.calls):
        assert candidate_purpose == purpose
        assert after[0].content == ORDERED_RECIPE_RULES + "\n\n" + before[0].content
        assert after[1:] == before[1:]
    assert actor.metadata["prompt_version"].endswith("-v4")
    assert actor.metadata["requires_unlimited_inventory"] is True
    assert "recipe directions are ordered prerequisites" in ORDERED_RECIPE_RULES.lower()
    for seed_specific in ("chicken wing", "red apple", "toaster", "fridge"):
        assert seed_specific not in ORDERED_RECIPE_RULES.lower()


@pytest.mark.parametrize("full_history", [False, True])
@pytest.mark.parametrize("invalid", ['not json', '{"action":"slice red apple"}'])
def test_v5_adds_general_tool_prerequisite_guidance_and_targeted_repair(full_history, invalid):
    original = Responses(invalid, '{"action":"inventory"}')
    candidate = Responses(invalid, '{"action":"inventory"}')
    PromptedActor(full_history=full_history, prompt_version="v4").choose_action(view(), "notes", original)
    actor = PromptedActor(full_history=full_history, prompt_version="v5")
    assert actor.choose_action(view(), "notes", candidate) == "inventory"
    assert actor.metadata["prompt_version"].endswith("-v5")
    for index, ((before, _), (after, _)) in enumerate(zip(original.calls, candidate.calls)):
        assert after[0].content == TOOL_PREREQUISITE_RULES + "\n\n" + before[0].content
        assert after[1] == before[1]
        if index == 1 and invalid == '{"action":"slice red apple"}':
            assert after[2] == before[2]
            assert after[3].content == before[3].content + (
                " If the unavailable command is a preparation step, check whether its "
                "required tool can be taken with a current allowed action. Take the "
                "tool instead of repeating an examination; then continue the earliest "
                "unfinished recipe direction. Do not choose to eat an ingredient."
            )
        else:
            assert after[2:] == before[2:]
    for seed_specific in ("chicken wing", "red apple", "toaster", "fridge"):
        assert seed_specific not in TOOL_PREREQUISITE_RULES.lower()


@pytest.mark.parametrize("full_history", [False, True])
def test_v6_adds_closed_container_progress_rule_to_v5(full_history):
    original = Responses('{"action":"inventory"}')
    candidate = Responses('{"action":"inventory"}')
    PromptedActor(full_history=full_history, prompt_version="v5").choose_action(view(), "notes", original)
    actor = PromptedActor(full_history=full_history, prompt_version="v6")
    assert actor.choose_action(view(), "notes", candidate) == "inventory"
    assert actor.metadata["prompt_version"].endswith("-v6")
    assert candidate.calls[0][0][0].content == CLOSED_CONTAINER_RULES + "\n\n" + original.calls[0][0][0].content
    assert candidate.calls[0][0][1:] == original.calls[0][0][1:]
    for seed_specific in ("chicken wing", "red apple", "toaster", "fridge"):
        assert seed_specific not in CLOSED_CONTAINER_RULES.lower()


@pytest.mark.parametrize("full_history", [False, True])
def test_v7_retains_v6_rules_and_tool_repair_for_unavailable_preparation(full_history):
    original = Responses('{"action":"slice red apple"}', '{"action":"examine knife"}')
    candidate = Responses('{"action":"slice red apple"}', '{"action":"take knife"}')
    current = AgentView("Current room.", "Prepare and eat the meal.",
                        ("move east", "examine cookbook", "examine knife", "inventory", "take knife"), 10, 2)
    PromptedActor(full_history=full_history, prompt_version="v6").choose_action(current, "notes", original)
    actor = PromptedActor(full_history=full_history, prompt_version="v7")
    assert actor.choose_action(current, "notes", candidate) == "take knife"
    assert candidate.calls[0][0][0].content == original.calls[0][0][0].content
    assert candidate.calls[0][0][1:] == original.calls[0][0][1:]
    assert candidate.calls[1][0][0].content == original.calls[1][0][0].content
    assert candidate.calls[1][0][1:3] == original.calls[1][0][1:3]
    assert "Take the tool instead of repeating an examination" in candidate.calls[1][0][-1].content
    assert candidate.calls[1][0][-1].content.startswith(original.calls[1][0][-1].content)


@pytest.mark.parametrize("full_history", [False, True])
def test_v8_prioritizes_opening_relevant_closed_containers(full_history):
    original = Responses('{"action":"inventory"}')
    candidate = Responses('{"action":"inventory"}')
    PromptedActor(full_history=full_history, prompt_version="v7").choose_action(view(), "notes", original)
    actor = PromptedActor(full_history=full_history, prompt_version="v8")
    assert actor.choose_action(view(), "notes", candidate) == "inventory"
    assert candidate.calls[0][0][0].content == (
        CLOSED_CONTAINER_PRIORITY_RULE + "\n\n" + original.calls[0][0][0].content)
    assert candidate.calls[0][0][1:] == original.calls[0][0][1:]
    assert actor.metadata["prompt_version"].endswith("-v8")
    for specific in ("fridge", "chicken wing", "red apple", "toaster"):
        assert specific not in CLOSED_CONTAINER_PRIORITY_RULE.lower()


@pytest.mark.parametrize("full_history", [False, True])
def test_v9_combines_v8_priority_with_v7_targeted_tool_repair(full_history):
    candidate = Responses('{"action":"slice red apple"}', '{"action":"take knife"}')
    actor = PromptedActor(full_history=full_history, prompt_version="v9")
    current = AgentView("Current room.", "Prepare and eat the meal.",
                        ("examine cookbook", "examine knife", "take knife"), 10, 2)
    assert actor.choose_action(current, "notes", candidate) == "take knife"
    assert candidate.calls[0][0][0].content.startswith(CLOSED_CONTAINER_PRIORITY_RULE)
    assert candidate.calls[1][0][0].content == candidate.calls[0][0][0].content
    assert candidate.calls[1][0][1].content == candidate.calls[0][0][1].content
    assert "Take the tool instead of repeating an examination" in candidate.calls[1][0][-1].content
    assert actor.metadata["prompt_version"].endswith("-v9")


@pytest.mark.parametrize("full_history", [False, True])
def test_v10_explicitly_prioritizes_first_unfinished_global_recipe_direction(full_history):
    model = Responses('{"action":"inventory"}')
    actor = PromptedActor(full_history=full_history, prompt_version="v10")
    assert actor.choose_action(view(), "notes", model) == "inventory"
    assert model.calls[0][0][0].content.startswith(GLOBAL_RECIPE_ORDER_RULE)
    assert "Do not skip ahead to another ingredient's preparation" in GLOBAL_RECIPE_ORDER_RULE


@pytest.mark.parametrize("full_history", [False, True])
def test_v11_prioritizes_preparing_the_completed_meal(full_history):
    model = Responses('{"action":"prepare meal"}')
    actor = PromptedActor(full_history=full_history, prompt_version="v11")
    current = AgentView("Both ingredients are prepared and carried.", "Prepare and eat the meal.",
                        ("prepare meal", "eat salt"), 5, 2)
    assert actor.choose_action(current, "notes", model) == "prepare meal"
    assert model.calls[0][0][0].content.startswith(MEAL_FINALIZATION_RULE)
    assert "Never choose 'eat <ingredient>'" in MEAL_FINALIZATION_RULE


@pytest.mark.parametrize("full_history", [False, True])
def test_v12_avoids_rereading_a_complete_supplied_recipe(full_history):
    model = Responses('{"action":"open fridge"}')
    actor = PromptedActor(full_history=full_history, prompt_version="v12")
    current = AgentView("Recipe is complete in memory.", "Prepare and eat the meal.",
                        ("open fridge", "examine cookbook"), 10, 2)
    assert actor.choose_action(current, "complete recipe", model) == "open fridge"
    assert model.calls[0][0][0].content.startswith(RECIPE_REREAD_RULE)


@pytest.mark.parametrize("full_history", [False, True])
def test_v13_resolves_generic_cookbook_goal_against_present_recipe(full_history):
    model = Responses('{"action":"open fridge"}')
    actor = PromptedActor(full_history=full_history, prompt_version="v13")
    current = AgentView("Complete recipe is present.", "Check the cookbook.",
                        ("open fridge", "examine cookbook"), 10, 2)
    assert actor.choose_action(current, "complete recipe", model) == "open fridge"
    assert model.calls[0][0][0].content.startswith(RECIPE_GOAL_PRECEDENCE_RULE)


def test_v15_repairs_premature_ingredient_eating():
    actor = PromptedActor(prompt_version="v15")
    view = AgentView("You roast the apple.", "Prepare and eat the meal.",
                     ("eat red apple", "open fridge"), 10, 2)
    model = Responses('{"action":"eat red apple"}', '{"action":"open fridge"}')
    assert actor.choose_action(view, "Ingredients: red apple, chicken wing\nDirections: grill wing; prepare meal", model) == "open fridge"
    assert "ends the task" in model.calls[1][0][-1].content


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
    actor = PromptedActor(full_history=full_history, prompt_version="v11")
    view = AgentView(RECIPE_OBSERVATION, "Prepare and eat the meal.",
                     ("examine cookbook", "open fridge"), 9, 2)
    for _ in range(3):
        model = Responses('{"action":"examine cookbook"}')
        assert actor.choose_action(view, RECIPE_MEMORY, model) == "examine cookbook"
        assert [purpose for _, purpose in model.calls] == ["action"]
    actor.reset_episode_state()
    assert actor.metadata["repeated_observation_guard"].startswith("disabled")


def test_v17_goal_first_prompt_keeps_model_choice():
    actor = PromptedActor(prompt_version="v17")
    view = AgentView("a knife", "Prepare and eat the meal.",
                     ("examine cookbook", "cook chicken wing in toaster"), 66, 2)
    model = Responses('{"action":"examine cookbook"}')
    assert actor.choose_action(view, "Directions: grill chicken wing", model) == "examine cookbook"
    assert model.calls[0][0][0].content.startswith("Your goal is to prepare and eat the meal")
    assert len(model.calls) == 1


def test_v18_two_part_response_executes_only_legal_model_action():
    actor = PromptedActor(prompt_version="v18")
    view = AgentView("You carry the chicken wing.", "Prepare and eat the meal.",
                     ("cook chicken wing in toaster", "examine cookbook"), 66, 2)
    model = Responses('{"next_direction":"grill the chicken wing",'
                      '"action":"cook chicken wing in toaster"}')
    assert actor.choose_action(view, "Directions: grill the chicken wing", model) == "cook chicken wing in toaster"
    assert actor.metadata["prompt_version"] == "s2-action-v18"
    assert model.calls[0][0][0].content.startswith("Your goal is to prepare and eat the meal")


def test_v19_excludes_only_the_immediately_previous_action():
    actor = PromptedActor(prompt_version="v19")
    view = AgentView("a toaster", "Prepare the meal.",
                     ("examine toaster", "open fridge"), 10, 2)
    assert actor.choose_action(view, "notes", Responses('{"action":"examine toaster"}')) == "examine toaster"
    repair = Responses('{"action":"examine toaster"}', '{"action":"open fridge"}')
    assert actor.choose_action(view, "notes", repair) == "open fridge"
    assert '"allowed_actions": ["open fridge"]' in repair.calls[0][0][-1].content
    assert [purpose for _, purpose in repair.calls] == ["action", "action_repair"]
    again = Responses('{"action":"examine toaster"}')
    assert actor.choose_action(view, "notes", again) == "examine toaster"
    assert actor.metadata["immediate_repeat_policy"] == "exclude_previous_action_v1"
    actor.reset_episode_state()
    assert actor.choose_action(view, "notes", Responses('{"action":"examine toaster"}')) == "examine toaster"


def test_v20_requires_reason_and_keeps_one_step_exclusion():
    actor = PromptedActor(prompt_version="v20")
    view = AgentView("a toaster", "Prepare the meal.",
                     ("examine toaster", "open fridge"), 10, 2)
    repair = Responses('{"next_direction":"grill chicken","action":"examine toaster"}',
                       '{"next_direction":"grill chicken","reason":"Check the toaster.",'
                       '"action":"examine toaster"}')
    assert actor.choose_action(view, "notes", repair) == "examine toaster"
    assert [purpose for _, purpose in repair.calls] == ["action", "action_repair"]
    next_turn = Responses('{"next_direction":"grill chicken",'
                          '"reason":"Find the ingredient.","action":"open fridge"}')
    assert actor.choose_action(view, "notes", next_turn) == "open fridge"
    assert '"allowed_actions": ["open fridge"]' in next_turn.calls[0][0][-1].content


def test_v21_repair_requests_reason_after_excluded_action():
    actor = PromptedActor(prompt_version="v21")
    view = AgentView("a toaster", "Prepare the meal.",
                     ("examine toaster", "open fridge"), 10, 2)
    first = Responses('{"next_direction":"grill chicken",'
                      '"reason":"Inspect the appliance.","action":"examine toaster"}')
    assert actor.choose_action(view, "notes", first) == "examine toaster"
    repair = Responses('{"next_direction":"grill chicken",'
                       '"reason":"Inspect the appliance.","action":"examine toaster"}',
                       '{"next_direction":"grill chicken",'
                       '"reason":"Find the chicken.","action":"open fridge"}')
    assert actor.choose_action(view, "notes", repair) == "open fridge"
    assert '"allowed_actions": ["open fridge"]' in repair.calls[0][0][-1].content
    assert "next_direction, reason, and action" in repair.calls[1][0][-1].content


@pytest.mark.parametrize("prompt_version", ["v22", "v23", "v24", "v25", "v26", "v27", "v28", "v29"])
def test_prerequisite_prompt_does_not_block_repeated_legal_actions(prompt_version):
    actor = PromptedActor(prompt_version=prompt_version)
    view = AgentView("a toaster", "Prepare the meal.",
                     ("examine toaster", "open fridge"), 10, 2)
    output = ('{"next_direction":"grill chicken wing",'
              '"missing_prerequisite":"chicken wing","action":"examine toaster"}')
    for _ in range(2):
        model = Responses(output)
        assert actor.choose_action(view, "Carried items: none", model) == "examine toaster"
        assert '"allowed_actions": ["examine toaster", "open fridge"]' in model.calls[0][0][-1].content
    assert "immediate_repeat_policy" not in actor.metadata


def test_v24_only_canonicalizes_optional_article_to_exact_allowed_action():
    from game_memory.actor import validate_action_output

    allowed = ("slice red apple", "slice green apple", "examine cookbook")
    raw = '{"action":"slice the red apple"}'
    assert validate_action_output(raw, allowed) == ("slice the red apple", "unavailable_action")
    assert validate_action_output(raw, allowed, allow_optional_article=True) == ("slice red apple", None)
    assert validate_action_output('{"action":"slice the blue apple"}', allowed,
                                  allow_optional_article=True)[1] == "unavailable_action"
    actor = PromptedActor(prompt_version="v24")
    view = AgentView("You carry the apple and knife.", "Prepare the meal.", allowed, 10, 2)
    model = Responses('{"next_direction":"slice the red apple",'
                      '"missing_prerequisite":null,"action":"slice the red apple"}')
    assert actor.choose_action(view, "Carried items: red apple, knife", model) == "slice red apple"
    assert actor.metadata["action_output_policy"] == "optional_article_exact_match_v1"


def test_v25_requests_ingredient_status_without_changing_legal_actions():
    actor = PromptedActor(prompt_version="v25")
    current = AgentView("A kitchen", "Prepare and eat the meal",
                        ("take salt", "prepare meal"), 10, 2)
    model = Responses('{"ingredient_status":{"salt":false},"action":"take salt"}')
    assert actor.choose_action(current, "Ingredients: salt\nCarried items: none", model) == "take salt"
    assert "EACH named recipe ingredient" in model.calls[0][0][0].content
    assert '"allowed_actions": ["take salt", "prepare meal"]' in model.calls[0][0][1].content


def test_v27_model_reviews_prepare_meal_against_same_public_evidence():
    actor = PromptedActor(prompt_version="v27")
    current = AgentView("You grill the chicken wing.", "Prepare and eat the meal",
                        ("take salt", "examine toaster"), 10, 2)
    memory = "Ingredients:\n chicken wing\n salt\nCarried items: chicken wing"
    model = Responses('{"action":"prepare meal"}',
                      '{"ingredient_status":{"salt":"absent"},"action":"take salt"}')
    assert actor.choose_action(current, memory, model) == "take salt"
    assert [purpose for _, purpose in model.calls] == ["action", "action_review"]
    assert model.calls[1][0][1] == model.calls[0][0][1]
    assert '"allowed_actions": ["take salt", "examine toaster"]' in model.calls[1][0][1].content


def test_v27_keeps_valid_prepare_meal_after_model_review():
    actor = PromptedActor(prompt_version="v27")
    current = AgentView("You roast the apple.", "Prepare and eat the meal",
                        ("prepare meal", "take salt"), 10, 2)
    model = Responses('{"action":"prepare meal"}',
                      '{"ingredient_status":{"apple":"present"},"action":"prepare meal"}')
    assert actor.choose_action(current, "Ingredients:\n apple\nCarried items: apple", model) == "prepare meal"
    assert [purpose for _, purpose in model.calls] == ["action", "action_review"]


def test_v28_rechecks_progress_after_unavailable_action_then_reviews_meal():
    actor = PromptedActor(prompt_version="v28")
    current = AgentView("You take the salt.", "Prepare and eat the meal",
                        ("prepare meal", "examine toaster"), 10, 2)
    memory = "Ingredients:\n chicken wing\n salt\nDirections:\n grill the chicken wing\n prepare meal\nCarried items: chicken wing, salt\nRecipe progress: cook chicken wing in toaster"
    model = Responses('{"action":"grill the chicken wing"}',
                      '{"completed_directions":["grill the chicken wing"],"action":"prepare meal"}',
                      '{"ingredient_status":{"salt":"present"},"action":"prepare meal"}')
    assert actor.choose_action(current, memory, model) == "prepare meal"
    assert [purpose for _, purpose in model.calls] == ["action", "action_repair", "action_review"]
    assert "Previous unavailable proposal: grill the chicken wing" in model.calls[1][0][1].content
    assert memory in model.calls[1][0][1].content


def test_v29_reviews_structured_memory_without_scripted_action():
    actor = PromptedActor(prompt_version="v29")
    current = AgentView("You grill the chicken wing.", "Prepare and eat the meal",
                        ("take salt", "inventory", "examine cookbook"), 10, 2)
    memory = ('{"carried_items":["chicken wing"],'
              '"recipe_status":{"ingredients":{"chicken wing":true,"salt":true},'
              '"directions":{"grill the chicken wing":true,"prepare meal":false}}}')
    model = Responses('{"action":"grill the chicken wing"}',
                      '{"completed_directions":["grill the chicken wing"],'
                      '"missing_ingredients":["salt"],"action":"take salt"}')
    assert actor.choose_action(current, memory, model) == "take salt"
    assert [purpose for _, purpose in model.calls] == ["action", "action_repair"]
    assert '"allowed_actions": ["take salt", "inventory", "examine cookbook"]' in model.calls[1][0][1].content
    assert memory in model.calls[1][0][1].content


def test_state_change_invalidates_stale_inspection_result():
    actor = PromptedActor(prompt_version="v13")
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
