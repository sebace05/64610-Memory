"""Runner integration, prompt isolation, usage accounting, and error semantics."""

import json
from pathlib import Path

import pytest

from game_memory import CookingWorldConfig, CookingWorldEnvironment
from game_memory.actor import PromptedActor
from game_memory.components import Generation, MemoryUpdate
from game_memory.integration_fixtures import FakeMemory, FakeModel
from game_memory.runner import EpisodeConfig, run_episode


def execute(tmp_path, config=None, model=None, memory=None):
    config = config or EpisodeConfig(action_budget=6)
    with CookingWorldEnvironment(recheck_cost=config.recheck_cost,
                                  action_budget=config.action_budget) as env:
        result = run_episode(config, env, PromptedActor(), memory or FakeMemory(config.strategy),
                             model or FakeModel(), output_dir=tmp_path)
    directory = tmp_path / result["episode_id"]
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    assert json.loads((directory / "result.json").read_text()) == result
    assert [e["sequence"] for e in events] == list(range(len(events)))
    assert events[-1]["event"] == "episode_end"
    return result, events


@pytest.mark.parametrize("strategy", ["prose", "structured", "hybrid"])
@pytest.mark.parametrize("price", [2, 5])
def test_real_game_runs_with_interchangeable_fixture_components(tmp_path, strategy, price):
    config = EpisodeConfig(strategy=strategy, recheck_cost=price, action_budget=6)
    result, events = execute(tmp_path, config)
    assert result["kind"] == "integration_fixture"
    assert result["status"] == "completed" and result["error"] is None
    assert result["termination_reason"] == "budget_exhaustion"
    assert result["success"] is False and result["failure"] is False
    assert result["recipe_rechecks"] == 1 and result["budget_spent"] == 6
    expected_steps = 5 if price == 2 else 2
    assert result["steps"] == expected_steps
    # One initialization write plus one per nonterminal action.
    assert result["usage_by_purpose"]["action"]["calls"] == expected_steps
    assert result["usage_by_purpose"]["memory"]["calls"] == expected_steps
    replies = [e for e in events if e["event"] == "model_response"]
    assert result["input_tokens"] == sum(e["input_tokens"] for e in replies)
    assert result["output_tokens"] == sum(e["output_tokens"] for e in replies)
    assert result["usage_complete"]
    assert len([e for e in events if e["event"] == "memory_update_skipped"]) == 1


def test_actor_cannot_see_dropped_initial_recipe_or_previous_chat(tmp_path):
    _, events = execute(tmp_path, EpisodeConfig(action_budget=2),
                        model=FakeModel(actions=("look around",)))
    requests = [e for e in events if e["event"] == "model_request" and e["purpose"] == "action"]
    assert len(requests) == 2
    assert "Directions:" in requests[0]["messages"][1]["content"]
    assert "Directions:" not in requests[1]["messages"][1]["content"]
    for request in requests:
        assert [m["role"] for m in request["messages"]] == ["system", "user"]
        payload = request["messages"][1]["content"].split("\nBounded memory:\n")[0]
        data = json.loads(payload.removeprefix("Current game input:\n"))
        assert set(data) == {"observation", "goal", "allowed_actions", "budget_remaining", "recheck_cost"}


class RepairModel(FakeModel):
    def __init__(self, repair_succeeds=True):
        super().__init__()
        self.repair_succeeds = repair_succeeds

    def generate(self, messages, *, purpose):
        if purpose == "action":
            return Generation("malformed response", 10, 2, 0.1)
        if purpose == "action_repair":
            text = '{"action":"look around"}' if self.repair_succeeds else "still malformed"
            return Generation(text, 20, 3, 0.2)
        return super().generate(messages, purpose=purpose)


def test_action_repair_is_logged_and_counted(tmp_path):
    result, events = execute(tmp_path, EpisodeConfig(action_budget=1), model=RepairModel())
    assert result["status"] == "completed"
    assert result["usage_by_purpose"]["action_repair"]["calls"] == 1
    assert result["usage_by_purpose"]["action_repair"]["input_tokens"] == 20
    replies = [e for e in events if e["event"] == "model_response"]
    assert result["output_tokens"] == sum(e["output_tokens"] for e in replies)
    repair = next(e for e in events if e["event"] == "model_request" and e["purpose"] == "action_repair")
    assert len(repair["messages"]) == 4
    action = next(e for e in events if e["event"] == "action")
    assert action["transition"]["action"] == "look around"


def test_failed_repairs_consume_budget_without_substituting_actions(tmp_path):
    result, events = execute(tmp_path, EpisodeConfig(action_budget=2),
                             model=RepairModel(repair_succeeds=False))
    assert result["status"] == "completed" and result["success"] is False
    assert result["steps"] == result["budget_spent"] == 2
    actions = [e["transition"] for e in events if e["event"] == "action"]
    assert all(not a["valid_action"] and not a["executed"] for a in actions)
    assert result["usage_by_purpose"]["action_repair"]["calls"] == 2


class BrokenModel(FakeModel):
    def generate(self, messages, *, purpose):
        if purpose == "action":
            raise TimeoutError("fixture model timeout")
        return super().generate(messages, purpose=purpose)


def test_model_error_is_not_counted_as_a_game_failure(tmp_path):
    result, events = execute(tmp_path, model=BrokenModel())
    assert result["status"] == "error"
    assert result["success"] is None and result["failure"] is None
    assert result["steps"] == result["budget_spent"] == 0
    assert not result["usage_complete"]
    assert result["error"]["phase"] == "action_generation"
    assert any(e["event"] == "model_error" for e in events)


class FixedMemory(FakeMemory):
    def __init__(self, text):
        super().__init__()
        self.text = text

    def update(self, *args):
        return MemoryUpdate(self.text)


def test_memory_overflow_stops_before_oversized_memory_reaches_actor(tmp_path):
    result, events = execute(tmp_path, memory=FixedMemory("word " * 257))
    assert result["status"] == "error" and result["success"] is None
    assert result["error"]["phase"] == "initial_memory"
    assert not any(e["event"] == "model_request" and e["purpose"] == "action" for e in events)


class CharacterCountingModel(FakeModel):
    def count_tokens(self, text):
        return len(text)


def test_exact_rendered_memory_is_counted_and_embedded_without_json_escaping(tmp_path):
    state = '{"fact":"quoted value"}'
    config = EpisodeConfig(action_budget=1, memory_token_limit=len(state))
    result, events = execute(tmp_path, config, model=CharacterCountingModel(actions=("look around",)),
                             memory=FixedMemory(state))
    assert result["status"] == "completed"
    update = next(e for e in events if e["event"] == "memory_update")
    assert update["memory_tokens"] == len(state)
    request = next(e for e in events if e["event"] == "model_request" and e["purpose"] == "action")
    assert request["messages"][1]["content"].endswith("\nBounded memory:\n" + state)


def test_scripted_success_is_completed_but_remains_an_integration_fixture(tmp_path):
    path = Path(__file__).resolve().parents[1] / "artifacts/s1/seed-0-cheap.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    actions = [r["action"] for r in records if r["event"] == "step"]
    result, _ = execute(tmp_path, EpisodeConfig(action_budget=17), model=FakeModel(actions=actions))
    assert result["kind"] == "integration_fixture" and result["status"] == "completed"
    assert result["success"] is True and result["score"] == 1.0
    assert result["termination_reason"] == "success"


def test_terminal_game_failure_is_completed_not_infrastructure_error(tmp_path):
    config = EpisodeConfig(action_budget=2, game=CookingWorldConfig(num_locations=1))
    result, _ = execute(tmp_path, config, model=FakeModel(actions=("take red apple", "eat red apple")))
    assert result["status"] == "completed" and result["error"] is None
    assert result["failure"] is True and result["success"] is False
    assert result["termination_reason"] == "terminal_failure"


def test_each_invocation_creates_separate_artifacts(tmp_path):
    config = EpisodeConfig(action_budget=1)
    first, _ = execute(tmp_path, config, model=FakeModel(actions=("look around",)))
    second, _ = execute(tmp_path, config, model=FakeModel(actions=("look around",)))
    assert first["episode_id"] != second["episode_id"]
    assert len(list(tmp_path.glob("*/result.json"))) == 2


def test_mismatched_components_are_rejected_before_starting_game(tmp_path):
    config = EpisodeConfig(action_budget=6)
    with CookingWorldEnvironment(recheck_cost=5, action_budget=6) as env:
        with pytest.raises(ValueError, match="configuration"):
            run_episode(config, env, PromptedActor(), FakeMemory(), FakeModel(), output_dir=tmp_path)
    with CookingWorldEnvironment(action_budget=6) as env:
        with pytest.raises(ValueError, match="strategy"):
            run_episode(config, env, PromptedActor(), FakeMemory("hybrid"), FakeModel(), output_dir=tmp_path)
    assert not list(tmp_path.iterdir())
