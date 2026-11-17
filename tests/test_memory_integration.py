"""Real simulator and runner, production memory, scripted fake inference."""

import json

import pytest

from game_memory.actor import PromptedActor
from game_memory.components import Generation
from game_memory.environment import CookingWorldEnvironment
from game_memory.integration_fixtures import FakeModel
from game_memory.memory import ProseMemory, StructuredMemory
from game_memory.runner import EpisodeConfig, run_episode


class ScriptedWriterModel(FakeModel):
    """Exercise real strategy prompts while keeping inference deterministic."""

    def __init__(self, candidate, initial_memory_output=None):
        super().__init__(actions=("examine cookbook",))
        self.candidate = candidate
        self.initial_memory_output = initial_memory_output
        self.memory_calls = 0
        self.repair_calls = 0

    @property
    def metadata(self):
        return {**super().metadata, "tokenizer": "character_fixture_not_model_tokens"}

    def count_tokens(self, text):
        return len(text)

    def generate(self, messages, *, purpose):
        if purpose == "memory":
            # Force a repair on initialization, then a failed repair and
            # previous-state fallback after the first game action.
            if self.memory_calls == 0 and self.initial_memory_output is not None:
                text = self.initial_memory_output
            else:
                text = self.candidate if self.memory_calls >= 2 else "x" * 257
            self.memory_calls += 1
        elif purpose == "memory_repair":
            text = self.candidate if self.repair_calls == 0 else "x" * 257
            self.repair_calls += 1
        else:
            return super().generate(messages, purpose=purpose)
        return Generation(text, sum(self.count_tokens(m.content) for m in messages),
                          self.count_tokens(text), 0.01)


@pytest.mark.parametrize("memory,candidate", [
    (ProseMemory(), "Need flour and water."),
    (StructuredMemory(), '{"note":"Need flour and water."}'),
])
@pytest.mark.parametrize("price", [2, 5])
def test_production_memory_runs_through_real_runner_and_simulator(
    tmp_path, memory, candidate, price,
):
    config = EpisodeConfig(strategy=memory.strategy, recheck_cost=price,
                           action_budget=6, memory_token_limit=256)
    model = ScriptedWriterModel(candidate)
    with CookingWorldEnvironment(recheck_cost=price, action_budget=6) as environment:
        result = run_episode(config, environment, PromptedActor(), memory, model,
                             output_dir=tmp_path)

    directory = tmp_path / result["episode_id"]
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    assert json.loads((directory / "result.json").read_text()) == result
    assert result["kind"] == "integration_fixture"
    assert result["status"] == "completed" and result["termination_reason"] == "budget_exhaustion"
    assert result["recipe_rechecks"] == 1 and result["budget_spent"] == 6
    assert result["steps"] == (5 if price == 2 else 2)

    rendered = memory.render(candidate)
    updates = [event for event in events if event["event"] == "memory_update"]
    assert len(updates) == result["steps"]
    assert all(event["memory"] == rendered for event in updates)
    assert all(event["memory_tokens"] == len(rendered) <= 256 for event in updates)
    initial_reason = ("over_budget:257>256" if isinstance(memory, ProseMemory)
                      else "malformed_json")
    assert updates[0]["validation_events"] == [
        f"memory_rejected:{initial_reason}", "memory_repair_accepted"]
    assert updates[1]["validation_events"][-1] == "memory_fallback:previous_valid_memory"

    actor_requests = [event for event in events if event["event"] == "model_request"
                      and event["purpose"] == "action"]
    assert len(actor_requests) == result["steps"]
    assert all(request["messages"][1]["content"].endswith(
        "\nBounded memory:\n" + rendered) for request in actor_requests)

    replies = [event for event in events if event["event"] == "model_response"]
    assert result["input_tokens"] == sum(reply["input_tokens"] for reply in replies)
    assert result["output_tokens"] == sum(reply["output_tokens"] for reply in replies)
    assert result["usage_by_purpose"]["memory"]["calls"] == result["steps"]
    assert result["usage_by_purpose"]["memory_repair"]["calls"] == 2
    assert result["usage_complete"]


@pytest.mark.parametrize("memory,candidate", [
    (ProseMemory(), "SECOND_EPISODE"),
    (StructuredMemory(), '{"note":"SECOND_EPISODE"}'),
])
def test_same_strategy_object_starts_each_runner_episode_empty(tmp_path, memory, candidate):
    config = EpisodeConfig(strategy=memory.strategy, action_budget=1)
    first_model = ScriptedWriterModel(candidate.replace("SECOND_EPISODE", "FIRST_EPISODE"))
    second_model = ScriptedWriterModel(candidate)

    for model in (first_model, second_model):
        with CookingWorldEnvironment(action_budget=1) as environment:
            result = run_episode(config, environment, PromptedActor(), memory, model,
                                 output_dir=tmp_path)
        assert result["status"] == "completed"

    events = [json.loads(line) for line in (
        tmp_path / result["episode_id"] / "events.jsonl").read_text().splitlines()]
    writer_request = next(event for event in events if event["event"] == "model_request"
                          and event["purpose"] == "memory")
    writer_input = json.loads(writer_request["messages"][1]["content"])
    assert writer_input["previous_memory"] == memory.render(memory.empty())
    assert "FIRST_EPISODE" not in json.dumps(writer_request)
    actor_request = next(event for event in events if event["event"] == "model_request"
                         and event["purpose"] == "action")
    assert "SECOND_EPISODE" in actor_request["messages"][1]["content"]
    assert "FIRST_EPISODE" not in actor_request["messages"][1]["content"]


@pytest.mark.parametrize("memory,extreme,candidate", [
    (StructuredMemory(), '{"n":1e-9999999999999999999}',
     '{"note":"repaired"}'),
])
def test_unrepresentable_number_is_logged_as_memory_rejection(
    tmp_path, memory, extreme, candidate,
):
    config = EpisodeConfig(strategy=memory.strategy, action_budget=1)
    model = ScriptedWriterModel(candidate, initial_memory_output=extreme)
    with CookingWorldEnvironment(action_budget=1) as environment:
        result = run_episode(config, environment, PromptedActor(), memory, model,
                             output_dir=tmp_path)

    events = [json.loads(line) for line in (
        tmp_path / result["episode_id"] / "events.jsonl").read_text().splitlines()]
    assert result["status"] == "completed"
    assert result["error"] is None
    assert not any(event["event"] == "episode_error" for event in events)
    update = next(event for event in events if event["event"] == "memory_update")
    assert update["validation_events"] == [
        "memory_rejected:json_number_unrepresentable", "memory_repair_accepted"]
    assert update["memory"] == memory.render(candidate)
    assert result["usage_by_purpose"]["memory_repair"]["calls"] == 1


@pytest.mark.parametrize("memory", [ProseMemory(), StructuredMemory()])
@pytest.mark.parametrize("failed", [False, True])
def test_initial_empty_or_failed_writer_remains_empty_with_all_attempts_logged(
    tmp_path, memory, failed,
):
    class EmptyOrRejectedWriter(FakeModel):
        def count_tokens(self, text):
            return len(text)

        def generate(self, messages, *, purpose):
            if purpose in {"memory", "memory_repair"}:
                text = "x" * 257 if failed else memory.empty()
                return Generation(text, sum(len(m.content) for m in messages), len(text),
                                  0.01, {"finish_reason": "length" if failed else "stop"})
            return super().generate(messages, purpose=purpose)

    config = EpisodeConfig(strategy=memory.strategy, action_budget=1)
    model = EmptyOrRejectedWriter(actions=("examine cookbook",))
    with CookingWorldEnvironment(action_budget=1) as environment:
        result = run_episode(config, environment, PromptedActor(), memory, model,
                             output_dir=tmp_path)
    events = [json.loads(line) for line in (
        tmp_path / result["episode_id"] / "events.jsonl").read_text().splitlines()]
    assert result["status"] == "completed"
    updates = [e for e in events if e["event"] == "memory_update"]
    assert len(updates) == 1  # Initialization only: no write after terminal action.
    assert updates[0]["memory"] == memory.render(memory.empty())
    assert updates[0]["validation_events"][-1] == (
        "memory_fallback:previous_valid_memory" if failed else "memory_accepted")
    requests = [e for e in events if e["event"] == "model_request"]
    actor = next(e for e in requests if e["purpose"] == "action")
    assert actor["messages"][1]["content"].endswith(
        "\nBounded memory:\n" + memory.render(memory.empty()))
    responses = [e for e in events if e["event"] == "model_response"]
    assert result["input_tokens"] == sum(e["input_tokens"] for e in responses)
    assert result["output_tokens"] == sum(e["output_tokens"] for e in responses)
    assert result["usage_complete"]
    assert result["usage_by_purpose"]["memory"]["calls"] == 1
    if failed:
        assert result["usage_by_purpose"]["memory_repair"]["calls"] == 1
        writer_responses = [e for e in responses
                            if e["purpose"] in {"memory", "memory_repair"}]
        assert len(writer_responses) == 2
        assert all(e["output_tokens"] == 257 for e in writer_responses)
        assert all(e["metadata"]["finish_reason"] == "length" for e in writer_responses)
    else:
        assert "memory_repair" not in result["usage_by_purpose"]
