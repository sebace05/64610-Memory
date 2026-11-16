"""Hand-calculated log fixtures independently check checkpoint accounting."""

from copy import deepcopy
import json

import pytest

from game_memory.summarize_diagnostics import summarize


def example():
    # Synthetic records only, never real model evidence. Ten input tokens,
    # three output tokens, one one-unit action, zero successful rereads.
    components = {"actor": {"is_fake": False}, "memory": {"is_fake": False},
                  "model": {"is_fake": False, "revision": "a" * 40}}
    config = {"strategy": "full_history", "seed": 7, "action_budget": 1, "recheck_cost": 2}
    result = {"episode_id": "synthetic", "kind": "full_history_diagnostic", "config": config,
              "components": components, "status": "completed", "success": False, "error": None,
              "termination_reason": "budget_exhaustion", "steps": 1, "budget_spent": 1,
              "recipe_rechecks": 0, "input_tokens": 10, "output_tokens": 3,
              "model_elapsed_seconds": 0.25, "runtime_seconds": 1.0, "usage_complete": True,
              "usage_by_purpose": {"action": {"calls": 1, "input_tokens": 10, "output_tokens": 3}}}
    events = [
        {"event": "episode_start", "config": config, "components": components,
         "memory_token_limit_applies": False},
        {"event": "model_request", "step": 1, "purpose": "action"},
        {"event": "model_response", "step": 1, "purpose": "action", "input_tokens": 10,
         "output_tokens": 3, "elapsed_seconds": 0.25, "metadata": {"finish_reason": "length"}},
        {"event": "action", "step": 1, "transition": {"action_cost": 1, "recipe_recheck": False,
         "valid_action": True, "termination_reason": "budget_exhaustion", "success": False}},
        {"event": "episode_end", "result": result},
    ]
    return result, events


def save(root, result, events, name="episode"):
    directory = root / name
    directory.mkdir()
    (directory / "result.json").write_text(json.dumps(result))
    (directory / "events.jsonl").write_text("".join(json.dumps({**e, "sequence": i}) + "\n"
                                                    for i, e in enumerate(events)))


def test_hand_calculated_unsuccessful_game_passes_technical_checkpoint(tmp_path):
    save(tmp_path, *example())
    report = summarize(tmp_path)
    assert report["logging_checks_passed"] and report["infrastructure_checks_passed"]
    assert report["real_completed"] == 1 and report["real_successes"] == 0
    assert report["episodes"][0]["output_limit_hits"] == 1
    assert report["episodes"][0]["invalid_actions"] == 0


@pytest.mark.parametrize("field,value", [("input_tokens", 11), ("budget_spent", 2),
                                         ("recipe_rechecks", 1), ("model_elapsed_seconds", 2)])
def test_consistent_but_incorrect_result_totals_are_rejected(tmp_path, field, value):
    result, events = example()
    result[field] = value  # Also changes episode_end; the oracle is the event ledger.
    save(tmp_path, result, events)
    report = summarize(tmp_path)
    assert not report["logging_checks_passed"]
    assert "total disagrees" in report["issues"][0]["error"]


def test_fixtures_cannot_establish_real_model_capability(tmp_path):
    result, events = example()
    result["components"]["model"]["is_fake"] = True
    result["kind"] = "integration_fixture"
    save(tmp_path, result, events)
    assert not summarize(tmp_path)["logging_checks_passed"]
    report = summarize(tmp_path, include_fixtures=True)
    assert report["logging_checks_passed"] and report["fixture_episodes"] == 1
    assert not report["real_model_capability_tested"]


def test_partial_runs_and_duplicate_seeds_are_not_silently_ignored(tmp_path):
    result, events = example()
    save(tmp_path, result, events)
    save(tmp_path, deepcopy(result), deepcopy(events), "duplicate")
    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "events.jsonl").write_text('{}\n')
    report = summarize(tmp_path)
    assert not report["logging_checks_passed"]
    assert report["pending"] == ["partial"]
    assert any("duplicate game seed" in e["error"] for e in report["issues"])


def test_infrastructure_errors_are_separate_from_game_losses(tmp_path):
    result, events = example()
    result.update(status="error", success=None, error={"phase": "action_generation"},
                  termination_reason="infrastructure_error", steps=0, budget_spent=0,
                  input_tokens=0, output_tokens=0, model_elapsed_seconds=0,
                  usage_complete=False, usage_by_purpose={})
    events[2] = {"event": "model_error", "step": 1, "purpose": "action"}
    events.pop(3)
    save(tmp_path, result, events)
    report = summarize(tmp_path)
    assert report["logging_checks_passed"]
    assert report["real_infrastructure_errors"] == 1 and report["real_completed"] == 0
    assert not report["infrastructure_checks_passed"]
    usage = report["episodes"][0]["generation_by_purpose"]["action"]
    assert usage["calls"] == usage["failed_calls"] == 1
    assert usage["returned_calls"] == 0
    assert report["episodes"][0]["usage_complete"] is False


def test_memory_provenance_sizes_and_empty_writes():
    from game_memory.summarize_diagnostics import memory_metrics
    events = [
        {"event": "model_response", "sequence": 1, "step": 0, "purpose": "memory",
         "text": "bad json", "output_tokens": 3},
        {"event": "model_response", "sequence": 2, "step": 0, "purpose": "memory_repair",
         "text": "{}", "output_tokens": 2},
        {"event": "memory_update", "sequence": 3, "step": 0, "memory": "{}", "memory_tokens": 1,
         "validation_events": ["memory_rejected:malformed_json", "memory_repair_accepted"]},
        {"event": "model_response", "sequence": 4, "step": 1, "purpose": "memory", "output_tokens": 99},
        {"event": "model_response", "sequence": 5, "step": 1, "purpose": "memory_repair", "output_tokens": 20},
        {"event": "memory_update", "sequence": 6, "step": 1, "memory": "{}", "memory_tokens": 1,
         "validation_events": ["memory_rejected:over_budget:70>64", "memory_repair_rejected:malformed_json",
                               "memory_fallback:previous_valid_memory"]},
    ]
    metrics = memory_metrics(events, "structured", 64)
    assert metrics["memory_updates"] == 2
    assert (metrics["primary_accepted"], metrics["repaired_accepted"], metrics["previous_state_fallback"]) == (0, 1, 1)
    assert metrics["accepted_empty"] == 1
    assert metrics["syntax_rejections"] == 2 and metrics["over_budget_rejections"] == 1
    assert [c["rendered_tokens"] for c in metrics["candidates"]] == [None, 1, 70, None]
    assert metrics["candidates"][0]["raw_output_tokens"] == 3


def test_legacy_unknown_and_prose_emptiness_are_not_normalized():
    from game_memory.summarize_diagnostics import memory_metrics
    events = [{"event": "memory_update", "memory": text, "memory_tokens": 1,
               "validation_events": labels} for text, labels in [
                   ("", ["memory_accepted"]), (" ", ["memory_accepted"]),
                   ("", ["memory_fallback:public_evidence"]), ("{}", [])]]
    metrics = memory_metrics(events, "prose", 64)
    assert metrics["accepted_empty"] == 1 and metrics["outcome_unknown"] == 2
    assert metrics["updates"][1]["accepted_empty"] is False
    assert metrics["format_checks"][3]["format_adherence"] is False


def test_preserved_reproduction_backward_reading():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "artifacts/reproduction-v29-v16-20261115/prose-p2"
    if not root.exists():
        pytest.skip("preserved reproduction is not distributed with source")
    report = summarize(root)
    assert report["logging_checks_passed"]
    assert sum(e["memory_evidence"]["outcome_unknown"] for e in report["episodes"]) == 15
    assert all(e["launcher_exit_status"] is None for e in report["episodes"])
