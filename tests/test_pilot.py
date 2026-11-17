"""Pilot settings cannot be rewritten to authorize mixed or duplicate runs."""

from dataclasses import asdict, replace
import json
import os
import subprocess
import sys

import pytest

from game_memory.actor import PromptedActor
from game_memory.pilot import prepare_pilot
from game_memory.runner import EpisodeConfig


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setattr("game_memory.pilot.source_metadata", lambda: {"commit": "a" * 40, "worktree_dirty": False})
    return dict(directory=tmp_path, episode=EpisodeConfig(strategy="full_history", action_budget=2),
                actor=PromptedActor(full_history=True, prompt_version="v31"),
                model=None, backend="fake", seeds=[0],
                memory_metadata={"name": "full_history", "version": 1}, protocol_id="fixture-v1")


def record_episode(settings, manifest, *, trace=True):
    directory = settings["directory"] / "episode"
    directory.mkdir()
    result = {"config": asdict(settings["episode"]), "components": {"actor": manifest["actor"], "memory": manifest["memory"]},
              "protocol_id": manifest["protocol_id"],
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
        updated["actor"] = PromptedActor()
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
    data["components"]["actor"] = PromptedActor().metadata
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


def test_cli_prepare_and_launch_guard_work_together(tmp_path):
    command = [sys.executable, "-m", "game_memory.run_episode", "--output-dir", str(tmp_path),
               "--backend", "fake", "--strategy", "full_history", "--actor-prompt", "v31",
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
    changed[changed.index("--action-budget") + 1] = "3"
    rejected = subprocess.run(changed + ["--prepare-only", "--seeds", "1"], capture_output=True, text=True)
    assert rejected.returncode == 2
    assert "Pilot settings changed" in rejected.stderr
    assert path.read_bytes() == original and result_path.read_bytes() == original_result


def test_model_initialization_failure_has_a_log_before_an_episode_exists(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    missing_model = tmp_path / "uncached-model"
    completed = subprocess.run([
        sys.executable, "-m", "game_memory.run_episode", "--output-dir", str(tmp_path / "pilot"),
        "--backend", "transformers", "--actor-prompt", "v31", "--strategy", "full_history", "--device", "cpu",
        "--dtype", "float32", "--model-id", str(missing_model), "--model-revision", "b" * 40,
        "--local-files-only", "--protocol-id", "software-fixture",
    ], capture_output=True, text=True)
    assert completed.returncode == 1
    pilot = tmp_path / "pilot"
    assert (pilot / "pilot-manifest.json").exists()
    assert not list(pilot.glob("*/events.jsonl"))
    assert "uncached-model" in completed.stderr


@pytest.mark.parametrize("change", ["memory", "protocol", "allowance", "source"])
def test_new_identity_changes_preserve_existing_manifest(settings, monkeypatch, change):
    prepare_pilot(**settings)
    path = settings["directory"] / "pilot-manifest.json"
    original = path.read_bytes()
    updated = settings | {"seeds": [1]}
    if change == "memory":
        updated["memory_metadata"] = {"name": "full_history", "version": 2}
    elif change == "protocol":
        updated["protocol_id"] = "different-v1"
    elif change == "allowance":
        updated["episode"] = replace(settings["episode"], memory_token_limit=64)
    else:
        monkeypatch.setattr("game_memory.pilot.source_metadata", lambda: {
            "commit": "a" * 40, "worktree_dirty": False, "source_digest": "changed"})
    with pytest.raises(ValueError, match="Pilot settings changed"):
        prepare_pilot(**updated)
    assert path.read_bytes() == original


@pytest.mark.parametrize("field", ["memory", "protocol_id", "source"])
def test_result_identity_mismatch_blocks_new_seed(settings, field):
    manifest = prepare_pilot(**settings)
    record_episode(settings, manifest)
    path = settings["directory"] / "episode/result.json"
    result = json.loads(path.read_text())
    if field == "memory":
        result["components"][field] = {"wrong": True}
    else:
        result[field] = "wrong"
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="Existing episode settings"):
        prepare_pilot(**(settings | {"seeds": [1]}))


@pytest.mark.parametrize("protocol", ["", "  ", None])
def test_empty_protocol_rejected_without_artifacts(settings, protocol):
    with pytest.raises(ValueError, match="protocol_id"):
        prepare_pilot(**(settings | {"protocol_id": protocol}))
    assert not (settings["directory"] / "pilot-manifest.json").exists()


def test_real_prepare_records_memory_without_constructing_model(tmp_path, monkeypatch):
    # The launcher applies Java options; keep this test from changing later tests.
    monkeypatch.setattr(os, "environ", os.environ.copy())
    from game_memory.memory import StructuredMemory
    from game_memory.run_episode import main

    def forbidden(*args, **kwargs):
        pytest.fail("prepare-only allocated model weights")

    monkeypatch.setattr("game_memory.transformers_model.TransformersModel", forbidden)
    monkeypatch.setattr("game_memory.transformers_model.runtime_metadata", lambda config: {"gpu": None})
    assert main(["--prepare-only", "--backend", "transformers",
                 "--strategy", "structured", "--actor-prompt", "v31", "--model-revision", "b" * 40,
                 "--protocol-id", "synthetic-preflight-v1", "--output-dir", str(tmp_path)]) == 0
    manifest = json.loads((tmp_path / "pilot-manifest.json").read_text())
    assert manifest["schema_version"] == 2
    assert manifest["memory"] == StructuredMemory().metadata
    assert manifest["actor"]["prompt_version"] == "s2-action-v31"
    assert manifest["protocol_id"] == "synthetic-preflight-v1"
    assert len(manifest["source"]["source_digest"]) == 64
    assert not list(tmp_path.glob("*/events.jsonl"))


def test_existing_result_model_identity_is_independently_checked(settings, monkeypatch):
    from game_memory.transformers_model import TransformersConfig
    monkeypatch.setattr("game_memory.transformers_model.runtime_metadata", lambda config: {"gpu": "fixture"})
    settings = settings | {"model": TransformersConfig(revision="b" * 40), "backend": "transformers"}
    record_episode(settings, prepare_pilot(**settings))
    path = settings["directory"] / "episode/result.json"
    result = json.loads(path.read_text())
    result["components"]["model"]["revision"] = "c" * 40
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="Existing model settings"):
        prepare_pilot(**(settings | {"seeds": [1]}))




@pytest.mark.parametrize("option,value", [
    ("--strategy", "hybrid"), ("--strategy", "history_window"),
    ("--actor-prompt", "v1"), ("--actor-prompt", "v32"),
])
def test_retired_cli_choices_fail_before_environment_or_model(tmp_path, monkeypatch, option, value):
    from game_memory.run_episode import main
    def forbidden(*args, **kwargs):
        pytest.fail("retired choice initialized a component")
    monkeypatch.setattr("game_memory.run_episode.CookingWorldEnvironment", forbidden)
    monkeypatch.setattr("game_memory.transformers_model.TransformersModel", forbidden)
    with pytest.raises(SystemExit) as error:
        main([option, value, "--output-dir", str(tmp_path)])
    assert error.value.code == 2
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("missing", ["output", "protocol", "blank_protocol"])
def test_real_cli_requires_explicit_destination_and_identity(tmp_path, monkeypatch, capsys, missing):
    from game_memory.run_episode import main
    def forbidden(*args, **kwargs):
        pytest.fail("invalid invocation initialized a component")
    monkeypatch.setattr("game_memory.run_episode.CookingWorldEnvironment", forbidden)
    monkeypatch.setattr("game_memory.transformers_model.TransformersModel", forbidden)
    args = ["--backend", "transformers", "--model-revision", "b" * 40]
    if missing != "output":
        args += ["--output-dir", str(tmp_path)]
    if missing != "protocol":
        args += ["--protocol-id", " " if missing == "blank_protocol" else "software-fixture"]
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert ("--output-dir" if missing == "output" else "--protocol-id") in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("strategy", ["full_history", "prose", "structured"])
def test_fixture_preparation_is_mandatory_and_does_not_change_jvm_environment(tmp_path, monkeypatch, strategy):
    from game_memory.run_episode import main
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "fixture unchanged")
    def forbidden(*args, **kwargs):
        pytest.fail("prepare-only initialized simulator or model")
    monkeypatch.setattr("game_memory.run_episode.CookingWorldEnvironment", forbidden)
    monkeypatch.setattr("game_memory.transformers_model.TransformersModel", forbidden)
    assert main(["--strategy", strategy, "--prepare-only", "--output-dir", str(tmp_path)]) == 0
    manifest = json.loads((tmp_path / "pilot-manifest.json").read_text())
    assert manifest["actor"]["prompt_version"].endswith("-v31")
    assert manifest["memory"]["strategy"] == strategy
    assert os.environ["JAVA_TOOL_OPTIONS"] == "fixture unchanged"
    assert not list(tmp_path.glob("*/events.jsonl"))


@pytest.mark.parametrize("failure_seed,expected", [(None, [0, 1, 2]), (1, [0, 1])])
def test_canonical_cli_loads_once_uses_fresh_memory_and_stops_only_on_infrastructure_error(
    tmp_path, monkeypatch, failure_seed, expected,
):
    from game_memory.run_episode import main
    loads, episodes, memories = [], [], []
    def load(config):
        loads.append(config)
        return object()
    def episode(config, environment, actor, memory, model, **kwargs):
        episodes.append(config.seed)
        memories.append(memory)
        assert actor.metadata["prompt_version"] == "full-history-v31"
        assert memory.empty() == "[]"
        assert model is shared_model[0]
        failed = config.seed == failure_seed
        return {"kind": "integration_fixture", "status": "error" if failed else "completed",
                "termination_reason": "infrastructure_error" if failed else "budget_exhaustion",
                "steps": 0, "budget_spent": 0, "recipe_rechecks": 0,
                "episode_id": str(config.seed), "error": "scripted failure" if failed else None}
    shared_model = []
    def capture_load(config):
        value = load(config)
        shared_model.append(value)
        return value
    monkeypatch.setattr("game_memory.transformers_model.TransformersModel", capture_load)
    monkeypatch.setattr("game_memory.transformers_model.runtime_metadata", lambda config: {"fixture": True})
    monkeypatch.setattr("game_memory.pilot.runtime_environment", lambda: {})
    monkeypatch.setattr("game_memory.run_episode.run_episode", episode)
    status = main(["--backend", "transformers", "--strategy", "full_history",
                   "--model-revision", "b" * 40, "--output-dir", str(tmp_path),
                   "--protocol-id", "software-fixture", "--seeds", "0", "1", "2"])
    assert status == (0 if failure_seed is None else 1)
    assert episodes == expected and len(loads) == 1
    assert len({id(memory) for memory in memories}) == len(memories)
    assert (tmp_path / "pilot-manifest.json").exists()


@pytest.mark.parametrize('strategy', ['prose', 'structured'])
def test_legal_choice_rejects_bounded_before_startup(tmp_path, monkeypatch, strategy):
    from game_memory.run_episode import main
    def forbidden(*args, **kwargs):
        pytest.fail('unsupported policy started component')
    monkeypatch.setattr('game_memory.run_episode.CookingWorldEnvironment', forbidden)
    monkeypatch.setattr('game_memory.transformers_model.TransformersModel', forbidden)
    with pytest.raises(SystemExit) as error:
        main(['--actor-prompt', 'legal-choice-v1', '--strategy', strategy, '--output-dir', str(tmp_path)])
    assert error.value.code == 2 and not list(tmp_path.iterdir())


def test_legal_choice_requires_pinned_model_before_runtime(tmp_path, monkeypatch):
    from game_memory.run_episode import main
    def forbidden(*args, **kwargs):
        pytest.fail('wrong checkpoint reached runtime')
    monkeypatch.setattr('game_memory.transformers_model.runtime_metadata', forbidden)
    with pytest.raises(SystemExit) as error:
        main(['--backend', 'transformers', '--actor-prompt', 'legal-choice-v1', '--strategy', 'full_history',
              '--model-revision', 'b'*40, '--protocol-id', 'fixture', '--output-dir', str(tmp_path)])
    assert error.value.code == 2


def test_legal_choice_manifest_identity_and_default_preserved(tmp_path, monkeypatch):
    from game_memory.run_episode import main
    def forbidden(*args, **kwargs):
        pytest.fail('prepare-only started component')
    monkeypatch.setattr('game_memory.run_episode.CookingWorldEnvironment', forbidden)
    args = ['--strategy', 'full_history', '--prepare-only', '--output-dir', str(tmp_path)]
    assert main(args) == 0
    assert json.loads((tmp_path/'pilot-manifest.json').read_text())['actor']['prompt_version'] == 'full-history-v31'
    with pytest.raises(SystemExit) as error:
        main(args + ['--actor-prompt', 'legal-choice-v1'])
    assert error.value.code == 2
    fresh = tmp_path/'choice'
    assert main(['--strategy', 'full_history', '--prepare-only', '--output-dir', str(fresh),
                 '--actor-prompt', 'legal-choice-v1']) == 0
    actor = json.loads((fresh/'pilot-manifest.json').read_text())['actor']
    assert actor['implementation'] == 'LegalChoiceActor'
    assert actor['legality_guaranteed_by_interface'] is True
