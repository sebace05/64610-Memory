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
    # Supply complete public evidence: the auditor must verify inputs rather
    # than treating a hand-calculated minimal ledger as verified model input.
    from game_memory.actor import PromptedActor
    from game_memory.diagnostics import FullHistoryMemory
    from game_memory.contracts import AgentView
    from dataclasses import asdict
    from game_memory.components import Generation
    components["actor"] = PromptedActor(full_history=True).metadata
    components["memory"] = FullHistoryMemory().metadata
    public = asdict(AgentView("Room café", "Prepare meal", ("inventory",), 1, 2))
    memory = json.dumps([{"action": "[INITIAL_OBSERVATION]", "observation": public["observation"]}], ensure_ascii=False)
    class Capture:
        def generate(self, messages, *, purpose):
            self.messages = [asdict(m) for m in messages]
            return Generation('{"action":"inventory"}', 10, 3, 0.25)
    capture = Capture()
    PromptedActor(full_history=True).choose_action(AgentView(**public), memory, capture)
    events[1]["messages"] = capture.messages
    events[2]["text"] = '{"action":"inventory"}'
    events[3].update(memory_before_action=memory)
    events[3]["transition"].update(action="inventory", executed=True, terminated=False,
                                   truncated=True, failure=False,
                                   view=public | {"observation": "Carried items: none", "budget_remaining": 0, "allowed_actions": []})
    events[1:1] = [{"event": "reset", "view": public},
                   {"event": "memory_update", "step": 0, "action": "[INITIAL_OBSERVATION]",
                    "previous_memory": "[]", "memory": memory, "memory_tokens": 10,
                    "validation_events": ["full_history_diagnostic_no_compression"]}]
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
    events[4] = {"event": "model_error", "step": 1, "purpose": "action"}
    events.pop(5)
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


@pytest.mark.parametrize("policy", ["v31"])
@pytest.mark.parametrize("corruption", ["fabricated", "stale_memory"])
def test_v31_bounded_unavailable_repair_keeps_strict_proposal_provenance(tmp_path, policy, corruption):
    from game_memory.actor import PromptedActor
    from game_memory.environment import CookingWorldEnvironment
    from game_memory.integration_fixtures import FakeModel
    from game_memory.memory import ProseMemory
    from game_memory.runner import EpisodeConfig, run_episode

    from game_memory.components import Generation

    class Model(FakeModel):
        def generate(self, messages, *, purpose):
            if purpose == 'memory':
                text = 'Fixture notebook.'
                return Generation(text, sum(self.count_tokens(m.content) for m in messages),
                                  self.count_tokens(text), 0.0)
            return super().generate(messages, purpose=purpose)

    model = Model(actions=('take unavailable item', 'examine cookbook'))
    with CookingWorldEnvironment(action_budget=2) as environment:
        result = run_episode(EpisodeConfig(strategy='prose', action_budget=2, memory_token_limit=512),
                             environment, PromptedActor(prompt_version=policy), ProseMemory(),
                             model, output_dir=tmp_path)
    report = summarize(tmp_path, include_fixtures=True)
    assert report['logging_checks_passed'] and report['fixture_episodes'] == 1, report
    trace = tmp_path / result['episode_id'] / 'events.jsonl'
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    repair = next(e for e in events if e['event']=='model_request' and e['purpose']=='action_repair')
    if corruption == "fabricated":
        repair['messages'][1]['content'] = repair['messages'][1]['content'].replace(
            'Previous unavailable proposal: take unavailable item',
            'Previous unavailable proposal: fabricated proposal')
        expected = 'proposal was not recorded'
    else:
        repair['messages'][1]['content'] = repair['messages'][1]['content'].replace(
            'Fixture notebook.', 'Stale notebook.')
        expected = 'latest bounded memory'
    trace.write_text(''.join(json.dumps(e)+'\n' for e in events))
    rejected = summarize(tmp_path, include_fixtures=True)
    assert not rejected['logging_checks_passed']
    assert expected in rejected['issues'][0]['error']


@pytest.mark.parametrize("corruption,expected", [
    ("cost", "action cost"), ("remaining", "remaining budget"),
    ("history", "actual public records"), ("actor_view", "public view"),
    ("hidden_actor_field", "unexpected fields"), ("sequence", "broken event sequence"),
])
def test_independent_public_evidence_and_budget_checks(tmp_path, corruption, expected):
    result, events = example()
    if corruption == "cost":
        # Keep summary and trace totals internally consistent; price is the oracle.
        result["budget_spent"] = events[5]["transition"]["action_cost"] = 0
    elif corruption == "remaining":
        events[5]["transition"]["view"]["budget_remaining"] = 1
    elif corruption == "history":
        events[2]["memory"] = '[{"action":"invented","observation":"secret"}]'
    elif corruption == "actor_view":
        events[3]["messages"][1]["content"] = events[3]["messages"][1]["content"].replace('Room caf', 'Hidden caf', 1)
    elif corruption == "hidden_actor_field":
        user = events[3]["messages"][1]
        user["content"] = user["content"].replace('"goal":', '"score": 1, "goal":', 1)
    save(tmp_path, result, events)
    if corruption == "sequence":
        trace = tmp_path / "episode/events.jsonl"
        data = [json.loads(line) for line in trace.read_text().splitlines()]
        data[2]["sequence"] = 999
        trace.write_text(''.join(json.dumps(e)+'\n' for e in data))
    report = summarize(tmp_path)
    assert not report["logging_checks_passed"]
    assert expected in report["issues"][0]["error"]


def test_mixed_protocols_are_rejected_even_when_all_other_settings_match(tmp_path):
    first, events = example()
    first["protocol_id"] = events[0]["protocol_id"] = "first"
    save(tmp_path, first, events)
    second, events = example()
    second["config"]["seed"] = 8
    second["protocol_id"] = events[0]["protocol_id"] = "second"
    save(tmp_path, second, events, "second")
    report = summarize(tmp_path)
    assert not report["logging_checks_passed"]
    assert any("mixed configurations" in issue["error"] for issue in report["issues"])


def test_report_cli_is_read_only_and_contains_turn_rows(tmp_path, monkeypatch, capsys):
    from game_memory.summarize_diagnostics import main
    save(tmp_path, *example())
    before = {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    monkeypatch.setattr("sys.argv", ["summarize_diagnostics", str(tmp_path)])
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["episodes"][0]["turns"][0]["action"] == "inventory"
    assert {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize("failure_purpose", ["memory", "memory_repair", "action", "action_review", "action_repair"])
def test_partial_inference_failures_remain_auditable_errors(tmp_path, failure_purpose):
    from game_memory.actor import PromptedActor
    from game_memory.components import Generation
    from game_memory.environment import CookingWorldEnvironment
    from game_memory.integration_fixtures import FakeModel
    from game_memory.memory import StructuredMemory
    from game_memory.runner import EpisodeConfig, run_episode
    class Failing(FakeModel):
        def generate(self, messages, *, purpose):
            if purpose == failure_purpose:
                raise TimeoutError("scripted transport failure")
            if purpose == "memory":
                text = "malformed" if failure_purpose == "memory_repair" else '{}'
            elif purpose == "action":
                if failure_purpose == "action_review":
                    payload = json.loads(messages[1].content.split('\nBounded memory:\n')[0].removeprefix('Current game input:\n'))
                    # This is a software fixture; use a legal current action to
                    # trigger the retained review only when actually available.
                    assert "prepare meal" in payload["allowed_actions"]
                    text = '{"action":"prepare meal"}'
                else:
                    text = 'malformed'
            else:
                return super().generate(messages, purpose=purpose)
            return Generation(text, 10, 2, 0.25)
    # A tiny explicit public environment fixture isolates transport handling and
    # needs no engine or hidden state. Only reset occurs before these failures.
    from game_memory.contracts import AgentView
    class PublicEnvironment:
        recheck_cost, action_budget = 2, 1
        steps = recipe_rechecks = budget_spent = 0
        metadata = {"fixture": True}
        def reset(self, seed, game):
            return AgentView("Public recipe", "Prepare meal", ("prepare meal", "inventory"), 1, 2)
    result = run_episode(EpisodeConfig(strategy="structured", action_budget=1), PublicEnvironment(),
                         PromptedActor(), StructuredMemory(), Failing(), output_dir=tmp_path)
    assert result["status"] == "error" and result["termination_reason"] == "infrastructure_error"
    assert result["usage_complete"] is False and result["success"] is None
    report = summarize(tmp_path, include_fixtures=True)
    assert report["logging_checks_passed"], report["issues"]
    calls = report["episodes"][0]["generation_by_purpose"][failure_purpose]
    assert calls["failed_calls"] == 1
    assert report["episodes"][0]["errors"]

    if failure_purpose == "memory":
        trace = next(tmp_path.glob("*/events.jsonl"))
        original = trace.read_bytes()
        events = [json.loads(line) for line in original.decode().splitlines()]
        request = next(e for e in events if e["event"] == "model_request")
        payload = json.loads(request["messages"][1]["content"])
        payload["hidden_history"] = "must not reach writer"
        request["messages"][1]["content"] = json.dumps(payload)
        trace.write_text(''.join(json.dumps(e)+'\n' for e in events))
        rejected = summarize(tmp_path, include_fixtures=True)
        assert not rejected["logging_checks_passed"]
        assert "unexpected fields" in rejected["issues"][0]["error"]
        # A schema-valid request without any public evidence is also unverified.
        events = [e for e in events if e["event"] != "reset"]
        request["messages"][1]["content"] = json.dumps({k: v for k, v in payload.items() if k != "hidden_history"})
        for sequence, event in enumerate(events):
            event["sequence"] = sequence
        trace.write_text(''.join(json.dumps(e)+'\n' for e in events))
        rejected = summarize(tmp_path, include_fixtures=True)
        assert not rejected["logging_checks_passed"]
        assert "no preceding public view" in rejected["issues"][0]["error"]
