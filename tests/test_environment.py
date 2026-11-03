"""Contract and experimental-control checks against the real Java simulator."""

from dataclasses import asdict

import pytest
from textworld_express import TextWorldExpressEnv

from game_memory import CookingWorldConfig, CookingWorldEnvironment


SMALL = CookingWorldConfig(num_locations=1, num_ingredients=2)


def test_one_room_one_ingredient_game_can_finish_through_public_actions():
    # Mechanics fixture only: this script is never supplied to an agent.
    with CookingWorldEnvironment() as env:
        env.reset(0, CookingWorldConfig(num_locations=1, num_ingredients=1))
        for action in ["open fridge", "take chicken wing", "cook chicken wing in toaster",
                       "prepare meal", "eat meal"]:
            assert action in env.view.allowed_actions
            result = env.step(action)
        assert result.success and result.terminated


@pytest.mark.parametrize("appliance,method", [("stove", "fry"), ("oven", "roast")])
def test_legal_wrong_appliance_irreversibly_fails_the_grilling_recipe(appliance, method):
    with CookingWorldEnvironment() as env:
        env.reset(0, CookingWorldConfig(num_locations=1, num_ingredients=1))
        env.step("open fridge")
        env.step("take chicken wing")
        action = f"cook chicken wing in {appliance}"
        assert action in env.view.allowed_actions
        result = env.step(action)
        assert result.valid_action and result.executed
        assert method in result.view.observation
        assert result.failure and result.termination_reason == "terminal_failure"
        assert result.score == 0.25


def test_mechanics_primer_preparation_rules_match_the_real_simulator():
    # Public-action mechanics fixture, not a model policy or model success.
    with CookingWorldEnvironment() as env:
        env.reset(0, CookingWorldConfig(limit_inventory_size=False))
        for action in ["open fridge", "take water", "take knife", "move east", "take flour"]:
            assert action in env.view.allowed_actions
            env.step(action)
        inventory = env.step("inventory").view.observation
        assert all(item in inventory for item in ("water", "flour", "knife"))
        assert "prepare meal" not in env.view.allowed_actions
        env.step("move west")
        assert "prepare meal" in env.view.allowed_actions
        env.step("put water in counter")
        assert "prepare meal" not in env.view.allowed_actions
        env.step("take water")
        assert "prepare meal" in env.view.allowed_actions
        assert not env.step("prepare meal").success
        assert env.step("eat meal").success


@pytest.fixture
def env():
    with CookingWorldEnvironment() as environment:
        yield environment


@pytest.fixture(scope="module")
def solution():
    """Privileged diagnostic only; the actual wrapper never generates solutions."""
    backend = TextWorldExpressEnv()
    try:
        backend.reset(seed=0, gameName="cookingworld", gameFold="train",
                      gameParams=SMALL.game_params(), generateGoldPath=True)
        return backend.getGoldActionSequence()
    finally:
        backend.close()


def test_reset_gives_recipe_once_without_spending_budget(env):
    view = env.reset(0, SMALL)
    assert "Ingredients:" in view.observation and "Directions:" in view.observation
    assert view.budget_remaining == 80
    assert env.budget_spent == env.steps == env.recipe_rechecks == 0
    assert set(asdict(view)) == {
        "observation", "goal", "allowed_actions", "budget_remaining", "recheck_cost"
    }
    assert "Directions:" not in view.goal
    following = env.step("look around")
    assert "Directions:" not in following.view.observation
    assert following.action_cost == 1


def test_reset_restores_game_and_wrapper_counters(env):
    first = env.reset(0, SMALL)
    env.step("take knife")
    env.step("read cookbook")
    second = env.reset(0, SMALL)
    assert first == second
    assert "take knife" in second.allowed_actions
    assert env.steps == env.recipe_rechecks == env.budget_spent == 0


@pytest.mark.parametrize("cost", [2, 5])
@pytest.mark.parametrize("action", ["read cookbook", "examine cookbook"])
def test_both_recipe_accesses_pay_the_treatment_price(cost, action):
    with CookingWorldEnvironment(recheck_cost=cost) as env:
        initial = env.reset(0, SMALL)
        result = env.step(action)
        assert "Directions:" in result.view.observation
        assert result.valid_action and result.executed and result.recipe_recheck
        assert result.action_cost == cost
        assert result.view.budget_remaining == initial.budget_remaining - cost
        assert result.score == result.reward == 0
        assert env.recipe_rechecks == 1


def test_recipe_access_cannot_escape_cost_via_case_or_whitespace(env):
    env.reset(0, SMALL)
    result = env.step("  EXAMINE   COOKBOOK  ")
    assert result.action == "examine cookbook"
    assert result.recipe_recheck and result.action_cost == 2


def test_carrying_book_does_not_make_reading_free(env):
    env.reset(0, SMALL)
    assert env.step("take cookbook").action_cost == 1
    inventory = env.step("inventory")
    assert "cookbook" in inventory.view.observation
    assert "Directions:" not in inventory.view.observation
    assert env.step("examine cookbook").action_cost == 2


def test_invalid_action_costs_one_and_does_not_change_world(env):
    env.reset(0, SMALL)
    invalid = env.step("read recipe")  # This is not an engine alias.
    assert not invalid.valid_action and not invalid.executed
    assert not invalid.recipe_recheck and invalid.action_cost == 1
    assert env.recipe_rechecks == 0
    assert "take knife" in invalid.view.allowed_actions
    assert env.step("take knife").view.observation == "You take the knife."


def test_unaffordable_recipe_action_is_not_executed_or_charged():
    with CookingWorldEnvironment(recheck_cost=5, action_budget=3) as env:
        env.reset(0, SMALL)
        result = env.step("examine cookbook")
        assert result.done and result.truncated and not result.terminated
        assert result.termination_reason == "budget_exhaustion"
        assert result.action_cost == 0 and result.view.budget_remaining == 3
        assert not result.executed and not result.recipe_recheck
        assert "Directions:" not in result.view.observation
        assert env.recipe_rechecks == env.budget_spent == 0
        with pytest.raises(RuntimeError, match="finished"):
            env.step("look around")


def test_exact_budget_exhaustion_and_reset():
    with CookingWorldEnvironment(action_budget=1) as env:
        env.reset(0, SMALL)
        result = env.step("look around")
        assert result.executed and result.view.budget_remaining == 0
        assert result.truncated and result.termination_reason == "budget_exhaustion"
        assert not result.success and not result.failure
        assert not result.view.allowed_actions
        assert env.reset(0, SMALL).budget_remaining == 1


def test_required_ingredient_consumption_reports_terminal_failure():
    with CookingWorldEnvironment(action_budget=2) as env:
        env.reset(0, SMALL)
        env.step("take red apple")
        result = env.step("eat red apple")
        assert result.failure and result.terminated and not result.truncated
        assert result.termination_reason == "terminal_failure"
        assert not result.success and result.view.budget_remaining == 0


@pytest.mark.parametrize("cost", [2, 5])
def test_complete_solution_reports_success_even_on_last_budget_unit(cost, solution):
    reads = sum(a in {"read cookbook", "examine cookbook"} for a in solution)
    budget = len(solution) + (cost - 1) * reads
    with CookingWorldEnvironment(recheck_cost=cost, action_budget=budget) as env:
        env.reset(0, SMALL)
        for action in solution:
            result = env.step(action)
        assert result.success and result.terminated and not result.truncated
        assert result.termination_reason == "success" and result.score == 1.0
        assert result.view.budget_remaining == 0


def test_inaccessible_recipe_attempt_is_invalid_not_a_recheck():
    with CookingWorldEnvironment(recheck_cost=5) as env:
        view = env.reset(0)  # Three locations; leave cookbook on the counter.
        move = next(a for a in view.allowed_actions if a.startswith("move "))
        env.step(move)
        result = env.step("read cookbook")
        assert not result.valid_action and not result.executed
        assert result.action_cost == 1 and not result.recipe_recheck


def test_configuration_and_lifecycle_errors_are_explicit(env):
    with pytest.raises(ValueError):
        CookingWorldConfig(num_ingredients=0)
    with pytest.raises(ValueError):
        CookingWorldEnvironment(recheck_cost=1)
    with pytest.raises(RuntimeError, match="reset"):
        env.step("look around")
    with pytest.raises(ValueError):
        env.reset(-1)
    env.close()
    env.close()
    with pytest.raises(RuntimeError, match="closed"):
        env.reset(0)
