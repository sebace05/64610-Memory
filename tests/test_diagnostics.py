"""Diagnostic history must be explicit, unbounded, isolated, and fixture-aware."""

import json

import pytest

from game_memory.actor import PromptedActor
from game_memory.components import MemoryContext
from game_memory.diagnostics import FullHistoryMemory
from game_memory.environment import CookingWorldEnvironment
from game_memory.integration_fixtures import FakeModel
from game_memory.runner import EpisodeConfig, run_episode


def test_archive_preserves_exact_evidence_and_does_not_reuse_episode_state():
    archive = FullHistoryMemory()
    context = MemoryContext("goal", 80, 2, 1)
    first = archive.update(archive.empty(), "[INITIAL_OBSERVATION]", "unique recipe ☃", context, None)
    second = archive.update(first.memory, "look around", "new observation", context, None)
    assert json.loads(second.memory) == [
        {"action": "[INITIAL_OBSERVATION]", "observation": "unique recipe ☃"},
        {"action": "look around", "observation": "new observation"},
    ]
    assert archive.empty() == "[]"


def test_full_history_keeps_recipe_after_later_observations_without_writer_calls(tmp_path):
    config = EpisodeConfig(strategy="full_history", action_budget=2, memory_token_limit=1)
    with CookingWorldEnvironment(action_budget=2) as env:
        result = run_episode(config, env, PromptedActor(full_history=True), FullHistoryMemory(),
                             FakeModel(actions=("look around",)), output_dir=tmp_path)
    events = [json.loads(line) for line in
              (tmp_path / result["episode_id"] / "events.jsonl").read_text().splitlines()]
    assert result["status"] == "completed", result.get("error")
    assert result["kind"] == "integration_fixture"
    assert not events[0]["memory_token_limit_applies"]
    requests = [e for e in events if e["event"] == "model_request"]
    assert len(requests) == 2 and all(e["purpose"] == "action" for e in requests)
    last_prompt = requests[-1]["messages"][1]["content"]
    assert "Visible interaction history (diagnostic)" in last_prompt
    assert "Directions:" in last_prompt
    assert "Bounded memory:" not in last_prompt
    assert any(e["memory_tokens"] > 1 for e in events if e["event"] == "memory_update")


def test_diagnostic_actor_must_match_configuration(tmp_path):
    with CookingWorldEnvironment(action_budget=1) as env:
        with pytest.raises(ValueError, match="context mode"):
            run_episode(EpisodeConfig(strategy="full_history", action_budget=1), env,
                        PromptedActor(), FullHistoryMemory(), FakeModel(), output_dir=tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("arguments,expected", [
    (["--backend", "transformers"], "requires --strategy full_history"),
    (["--backend", "transformers", "--strategy", "full_history"], "--model-revision is required"),
    (["--backend", "transformers", "--strategy", "full_history", "--model-revision", "main"],
     "immutable 40-character"),
    (["--seeds", "0", "0"], "duplicate game seeds"),
    (["--seed", "-1"], "invalid seed"),
])
def test_cli_rejects_invalid_experiments_before_loading_weights(monkeypatch, capsys, arguments, expected):
    from game_memory.run_episode import main
    monkeypatch.setattr("sys.argv", ["run_episode", *arguments])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert expected in capsys.readouterr().err


def test_cli_passes_explicit_prompt_version_and_labels_the_result(tmp_path, monkeypatch):
    from game_memory.run_episode import main
    monkeypatch.setattr("sys.argv", ["run_episode", "--backend", "fake", "--strategy", "full_history",
                                    "--actor-prompt", "v2", "--action-budget", "2",
                                    "--output-dir", str(tmp_path)])
    assert main() == 0
    result = json.loads(next(tmp_path.glob("*/result.json")).read_text())
    assert result["components"]["actor"]["prompt_version"] == "full-history-v2"
    assert result["kind"] == "integration_fixture"
