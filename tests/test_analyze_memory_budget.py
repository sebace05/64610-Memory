"""Synthetic evidence checks: these tests establish no model capability."""
from dataclasses import asdict
from game_memory.contracts import CookingWorldConfig
from game_memory.transformers_model import TransformersConfig
import itertools
import json

import pytest

from game_memory.analyze_memory_budget import analyze, render_report, validate_manifest


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def grid(tmp_path):
    policy = {"is_fake": False, "prompt_version": "p1-memory-v17", "version": 17,
              "update_policy": "syntax_and_size_one_repair_previous_state_v1",
              "semantic_validation": "none", "fallback": "previous_valid_memory",
              "max_repairs": 1, "render_version": "p1-render-v2"}
    manifest = {"schema_version": 1, "protocol_id": "synthetic-only", "stage": "development",
                "source": {"source_digest": "synthetic"}, "actor": {"is_fake": False, "prompt_version": "s2-action-v30"},
                "memory": {s: dict(policy, strategy=s) for s in ("prose", "structured")},
                "model": asdict(TransformersConfig(revision="a" * 40)), "runtime": {"gpu": "synthetic"},
                "game": asdict(CookingWorldConfig(num_locations=1)), "action_budget": 1,
                "strategies": ["prose", "structured"], "memory_token_limits": [256, 64],
                "recheck_costs": [2], "seeds": [0, 1]}
    write(tmp_path / "comparison-manifest.json", manifest)
    for strategy, limit, price in itertools.product(manifest["strategies"], manifest["memory_token_limits"], manifest["recheck_costs"]):
        condition = tmp_path / f"{strategy}-{limit}-{price}"
        config = {"strategy": strategy, "memory_token_limit": limit, "recheck_cost": price,
                  "action_budget": 1, "game": manifest["game"]}
        pilot = {k: manifest[k] for k in ("source", "actor", "model", "runtime", "protocol_id")}
        pilot.update(schema_version=2, episode=config, memory=manifest["memory"][strategy])
        write(condition / "pilot-manifest.json", pilot)
        for seed in manifest["seeds"]:
            success = strategy == "structured" and limit == 256
            components = {"actor": manifest["actor"], "memory": manifest["memory"][strategy],
                          "model": {**manifest["model"], **manifest["runtime"], "is_fake": False, "load_seconds": 2}}
            memory = "" if strategy == "prose" else "{}"
            usage = {p: {"calls": 1, "input_tokens": 10, "output_tokens": 2} for p in ("memory", "action")}
            result = {"episode_id": str(seed), "kind": "development", "config": {**config, "seed": seed},
                      "components": components, "source": manifest["source"], "protocol_id": manifest["protocol_id"], "status": "completed",
                      "success": success, "termination_reason": "success" if success else "budget_exhaustion",
                      "error": None, "score": int(success), "steps": 1, "budget_spent": 1, "recipe_rechecks": 0,
                      "input_tokens": 20, "output_tokens": 4, "usage_by_purpose": usage,
                      "usage_complete": True, "model_elapsed_seconds": .5, "runtime_seconds": 1}
            payload = {"previous_memory": memory, "action": "reset", "observation": "public", "context": {
                "goal": "meal", "budget_remaining": 1, "recheck_cost": price, "memory_token_limit": limit}}
            public = {"observation": "public", "goal": "meal", "allowed_actions": ["look around"],
                      "budget_remaining": 1, "recheck_cost": price}
            events = [{"event": "episode_start", "config": result["config"], "components": components,
                       "source": manifest["source"], "protocol_id": manifest["protocol_id"], "memory_token_limit_applies": True},
                      {"event": "model_request", "step": 0, "purpose": "memory", "messages": [
                          {"content": "writer"}, {"content": json.dumps(payload)}]},
                      {"event": "model_response", "step": 0, "purpose": "memory", "text": memory,
                       "input_tokens": 10, "output_tokens": 2, "elapsed_seconds": .25},
                      {"event": "memory_update", "step": 0, "memory": memory, "memory_tokens": 1,
                       "validation_events": ["memory_accepted"]},
                      {"event": "model_request", "step": 1, "purpose": "action", "messages": [
                          {"content": "actor"}, {"content": "Current game input:\n" + json.dumps(public) + "\nBounded memory:\n" + memory}]},
                      {"event": "model_response", "step": 1, "purpose": "action", "text": '{"action":"look around"}',
                       "input_tokens": 10, "output_tokens": 2, "elapsed_seconds": .25},
                      {"event": "action", "step": 1, "transition": {"action": "look around", "action_cost": 1,
                       "recipe_recheck": False, "valid_action": True, "success": success,
                       "termination_reason": result["termination_reason"]}},
                      {"event": "episode_end", "result": result}]
            write(condition / str(seed) / "result.json", result)
            (condition / str(seed) / "events.jsonl").write_text("".join(json.dumps({**e, "sequence": i}) + "\n" for i, e in enumerate(events)))
    return manifest


def test_complete_grid_counts_losses_and_matched_interaction(tmp_path):
    grid(tmp_path)
    report = analyze(tmp_path)
    assert report["valid"], report["issues"]
    assert report["planned_cells"] == report["observed_cells"] == 8
    assert report["allowance_effects"] == [{"recheck_cost": 2, "high_minus_low": {"prose": 0, "structured": 1},
                                             "interaction_json_minus_prose": 1}]
    assert sum(r["success"] for r in report["episodes"]) == 2
    assert all(r["memory_evidence"]["memory_updates"] == 1 for r in report["episodes"])
    assert len(render_report(report, "csv").splitlines()) == 9
    assert "Allowance effects" in render_report(report, "markdown")
    assert json.loads(render_report(report, "json"))["valid"]


@pytest.mark.parametrize("damage", ["missing", "duplicate", "partial", "wrong_model", "wrong_memory", "error", "mislabel"])
def test_invalid_evidence_never_produces_primary_contrast(tmp_path, damage):
    import shutil
    grid(tmp_path)
    directory = tmp_path / "prose-64-2" / "0"
    if damage == "missing":
        shutil.rmtree(directory)
    elif damage == "duplicate":
        shutil.copytree(directory, directory.parent / "duplicate")
    elif damage == "partial":
        (directory / "result.json").unlink()
    else:
        path = directory / "result.json"
        result = json.loads(path.read_text())
        if damage == "wrong_model":
            result["components"]["model"]["gpu"] = "other"
        elif damage == "wrong_memory":
            result["components"]["memory"]["prompt_version"] = "p1-memory-v16"
        elif damage == "error":
            result.update(status="error", success=None, error={"phase": "memory"})
        else:
            result["kind"] = "evaluation"
        write(path, result)
    report = analyze(tmp_path)
    assert not report["valid"] and report["issues"] and not report["allowance_effects"]


@pytest.mark.parametrize("key,value", [("strategies", ["prose"]), ("memory_token_limits", [64, 64]),
                                         ("recheck_costs", [2, 3]), ("seeds", [0, 0]),
                                         ("protocol_id", ""), ("stage", "held_out")])
def test_manifest_validation(tmp_path, key, value):
    manifest = grid(tmp_path)
    manifest[key] = value
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_mixed_memory_policies_rejected(tmp_path):
    manifest = grid(tmp_path)
    manifest["memory"]["prose"]["version"] = 16
    with pytest.raises(ValueError, match="policy mismatch"):
        analyze(tmp_path, manifest)


def test_annotation_examples_count_retention_separately_from_claim_accuracy():
    from pathlib import Path
    from game_memory.analyze_memory_budget import summarize_annotation
    path = Path(__file__).parent / "fixtures/memory_annotations/development-seeds.json"
    fixtures = json.loads(path.read_text())
    summaries = {example["name"]: summarize_annotation(example) for example in fixtures["assessment_examples"]}
    assert summaries["empty"]["retention"] == 0
    assert summaries["empty"]["claim_accuracy"] is None
    assert summaries["correct"]["retention"] == summaries["correct"]["claim_accuracy"] == 1
    assert summaries["contradictory"]["incorrect_claims"] == 1
    assert summaries["ambiguous"]["unknown_facts"] == 1
    assert summaries["ambiguous"]["claim_accuracy"] is None
    for recipe in fixtures["recipes"]:
        facts = {f["id"]: f for f in recipe["facts"]}
        for checkpoint in recipe["checkpoints"]:
            summarize_annotation(checkpoint)
            assert set(checkpoint["required"]) <= facts.keys()
            assert all(e["sequence"] <= checkpoint["memory_sequence"]
                       for f in checkpoint["required"] for e in facts[f]["evidence"])


def test_annotation_quotes_match_preserved_public_evidence():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fixtures = json.loads((Path(__file__).parent / "fixtures/memory_annotations/development-seeds.json").read_text())
    for recipe in fixtures["recipes"]:
        trace = root / recipe["trace"]
        if not trace.exists():
            pytest.skip("preserved reproduction is not distributed with source")
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        assert events[0]["config"]["seed"] == recipe["seed"]
        for fact in recipe["facts"]:
            for evidence in fact["evidence"]:
                event = events[evidence["sequence"]]
                observation = event["view"]["observation"] if event["event"] == "reset" else event["transition"]["view"]["observation"]
                assert evidence["quote"] in observation
        for checkpoint in recipe["checkpoints"]:
            assert events[checkpoint["memory_sequence"]]["event"] == "memory_update"
            for claim in checkpoint["claims"]:
                assert all(sequence <= checkpoint["memory_sequence"] for sequence in claim["evidence_sequences"])


@pytest.mark.parametrize("change", ["protocol", "source", "allowance", "runtime", "old_schema"])
def test_condition_manifest_identity_changes_are_flagged(tmp_path, change):
    grid(tmp_path)
    path = tmp_path / "prose-64-2/pilot-manifest.json"
    pilot = json.loads(path.read_text())
    if change == "protocol":
        pilot["protocol_id"] = "other-study"
    elif change == "source":
        pilot["source"]["source_digest"] = "other-source"
    elif change == "allowance":
        pilot["episode"]["memory_token_limit"] = 32
    elif change == "runtime":
        pilot["runtime"]["gpu"] = "other"
    else:
        pilot["schema_version"] = 1
    write(path, pilot)
    report = analyze(tmp_path)
    assert not report["valid"] and not report["allowance_effects"]
    assert "False" in render_report(report, "csv")


def test_orphan_trace_and_unmanifested_results_are_flagged(tmp_path):
    grid(tmp_path)
    write(tmp_path / "orphan/events.jsonl", {})
    write(tmp_path / "unmanifested/result.json", {})
    report = analyze(tmp_path)
    assert not report["valid"]
    assert {i["error"] for i in report["issues"]} >= {"orphan trace", "unaudited result"}
