"""Pilot settings cannot be rewritten to authorize mixed or duplicate runs."""

from dataclasses import asdict, replace
import json
import os
import subprocess
import sys

import pytest

from game_memory.actor import PromptedActor
from game_memory.pilot import prepare_pilot, run_logged
from game_memory.runner import EpisodeConfig


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setattr("game_memory.pilot.source_metadata", lambda: {"commit": "a" * 40, "worktree_dirty": False})
    return dict(directory=tmp_path, episode=EpisodeConfig(strategy="full_history", action_budget=2),
                actor=PromptedActor(full_history=True, prompt_version="v2"),
                model=None, backend="fake", seeds=[0])


def record_episode(settings, manifest, *, trace=True):
    directory = settings["directory"] / "episode"
    directory.mkdir()
    result = {"config": asdict(settings["episode"]), "components": {"actor": manifest["actor"]},
              "source": manifest["source"]}
    if settings["model"] is not None:
        result["components"]["model"] = manifest["model"] | manifest["runtime"]
    (directory / "result.json").write_text(json.dumps(result))
    if trace:
        (directory / "events.jsonl").write_text('{}\n')


def test_identical_prepare_preserves_manifest_and_allows_a_different_seed(settings):
    manifest = prepare_pilot(**settings)
    path = settings["directory"] / "pilot-manifest.json"
    original, modified = path.read_bytes(), path.stat().st_mtime_ns
    record_episode(settings, manifest)
    assert prepare_pilot(**(settings | {"seeds": [1]})) == manifest
    assert path.read_bytes() == original and path.stat().st_mtime_ns == modified


@pytest.mark.parametrize("change", ["actor", "budget", "price"])
def test_rerunning_prepare_cannot_rewrite_manifest_to_authorize_new_settings(settings, change):
    manifest = prepare_pilot(**settings)
    record_episode(settings, manifest)
    path = settings["directory"] / "pilot-manifest.json"
    original = path.read_bytes()
    updated = settings | {"seeds": [1]}
    if change == "actor":
        updated["actor"] = PromptedActor(full_history=True, prompt_version="v1")
    else:
        updated["episode"] = replace(settings["episode"], **({"action_budget": 80} if change == "budget" else {"recheck_cost": 5}))
    with pytest.raises(ValueError, match="Pilot settings changed"):
        prepare_pilot(**updated)
    assert path.read_bytes() == original


def test_duplicate_seed_is_rejected_without_changing_result(settings):
    record_episode(settings, prepare_pilot(**settings))
    result = settings["directory"] / "episode/result.json"
    original = result.read_bytes()
    with pytest.raises(ValueError, match="already has a result"):
        prepare_pilot(**settings)
    assert result.read_bytes() == original


@pytest.mark.parametrize("partial", [True, False])
def test_partial_or_missing_trace_blocks_launch(settings, partial):
    manifest = prepare_pilot(**settings)
    if partial:
        directory = settings["directory"] / "partial"
        directory.mkdir()
        (directory / "events.jsonl").write_text('{}\n')
    else:
        record_episode(settings, manifest, trace=False)
    with pytest.raises(ValueError, match="Partial episode|has no trace"):
        prepare_pilot(**(settings | {"seeds": [1]}))


def test_existing_result_is_checked_even_if_manifest_was_manually_changed(settings):
    manifest = prepare_pilot(**settings)
    record_episode(settings, manifest)
    result = settings["directory"] / "episode/result.json"
    data = json.loads(result.read_text())
    data["components"]["actor"] = PromptedActor(full_history=True, prompt_version="v1").metadata
    result.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Existing episode settings"):
        prepare_pilot(**(settings | {"seeds": [1]}))


def test_legacy_manifest_and_orphaned_results_are_not_adopted(settings):
    directory = settings["directory"]
    path = directory / "pilot-manifest.json"
    path.write_text('{"actor_prompt":"v1"}')
    with pytest.raises(ValueError, match="older format"):
        prepare_pilot(**settings)
    assert path.read_text() == '{"actor_prompt":"v1"}'
    path.unlink()
    (directory / "orphan").mkdir()
    (directory / "orphan/result.json").write_text('{}')
    with pytest.raises(ValueError, match="no manifest"):
        prepare_pilot(**settings)
    assert not path.exists()


def test_model_and_hardware_changes_are_rejected_before_weights_load(settings, monkeypatch):
    from game_memory.transformers_model import TransformersConfig
    model = TransformersConfig(revision="b" * 40, device="cpu", dtype="float32")
    monkeypatch.setattr("game_memory.transformers_model.runtime_metadata", lambda config: {"gpu": "first"})
    settings = settings | {"model": model, "backend": "transformers"}
    manifest = prepare_pilot(**settings)
    record_episode(settings, manifest)
    monkeypatch.setattr("game_memory.transformers_model.runtime_metadata", lambda config: {"gpu": "different"})
    with pytest.raises(ValueError, match="Pilot settings changed"):
        prepare_pilot(**(settings | {"seeds": [1]}))


def test_launch_failure_saves_both_streams_and_exit_status(tmp_path):
    log = tmp_path / "launch.log"
    command = [sys.executable, "-c", "import sys; print('load started', flush=True); print('load failed', file=sys.stderr); sys.exit(7)"]
    with pytest.raises(subprocess.CalledProcessError) as failure:
        run_logged(command, log, dict(os.environ))
    assert failure.value.returncode == 7
    assert json.loads(log.read_text().splitlines()[0])["command"] == command
    assert "load started" in log.read_text() and "load failed" in log.read_text()
    assert "Exit status: 7" in log.read_text()


def test_failed_spawn_is_logged_and_existing_logs_are_preserved(tmp_path):
    log = tmp_path / "launch.log"
    with pytest.raises(FileNotFoundError):
        run_logged([str(tmp_path / "missing-program")], log, dict(os.environ))
    original = log.read_bytes()
    assert b"FileNotFoundError" in original
    with pytest.raises(FileExistsError):
        run_logged([sys.executable, "-c", "print('overwrite')"], log, dict(os.environ))
    assert log.read_bytes() == original


def test_cli_prepare_and_launch_guard_work_together(tmp_path):
    command = [sys.executable, "-m", "game_memory.pilot", "--output-dir", str(tmp_path),
               "--backend", "fake", "--strategy", "full_history", "--actor-prompt", "v2",
               "--action-budget", "2"]
    prepared = subprocess.run(command + ["--prepare-only"], capture_output=True, text=True)
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    path = tmp_path / "pilot-manifest.json"
    original = path.read_bytes()
    assert not list(tmp_path.glob("*/events.jsonl"))
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result_path = next(tmp_path.glob("*/result.json"))
    original_result = result_path.read_bytes()
    changed = command.copy()
    changed[changed.index("--actor-prompt") + 1] = "v1"
    rejected = subprocess.run(changed + ["--prepare-only", "--seeds", "1"], capture_output=True, text=True)
    assert rejected.returncode == 2
    assert "Pilot settings changed" in rejected.stdout
    assert path.read_bytes() == original and result_path.read_bytes() == original_result
    assert len(list(tmp_path.glob("launch-*.log"))) == 3


def test_model_initialization_failure_has_a_log_before_an_episode_exists(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    missing_model = tmp_path / "uncached-model"
    completed = subprocess.run([
        sys.executable, "-m", "game_memory.pilot", "--output-dir", str(tmp_path / "pilot"),
        "--backend", "transformers", "--strategy", "full_history", "--device", "cpu",
        "--dtype", "float32", "--model-id", str(missing_model), "--model-revision", "b" * 40,
        "--local-files-only",
    ], capture_output=True, text=True)
    assert completed.returncode == 1
    pilot = tmp_path / "pilot"
    assert (pilot / "pilot-manifest.json").exists()
    assert not list(pilot.glob("*/events.jsonl"))
    log = next(pilot.glob("launch-*.log")).read_text()
    assert "uncached-model" in log and "Exit status: 1" in log


@pytest.mark.parametrize("child_status,expected", [(7, 7), (-9, 137)])
def test_pilot_cli_preserves_failure_status(tmp_path, monkeypatch, child_status, expected):
    from game_memory.pilot import main

    def fail(*args):
        raise subprocess.CalledProcessError(child_status, ["child"])

    monkeypatch.setattr("game_memory.pilot.run_logged", fail)
    monkeypatch.setattr("sys.argv", ["pilot", "--output-dir", str(tmp_path)])
    assert main() == expected
