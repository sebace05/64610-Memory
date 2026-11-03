"""Independent hand-calculated trace metrics, plus read-only CLI behavior."""

import csv
import json

import pytest

from game_memory.inspect_episode import analyze_events, main


def sample():
    allowed = ["take water", "put water in counter", "move east", "examine cookbook"]
    events = [{"event": "episode_start", "episode_id": "synthetic", "kind": "integration_fixture",
               "components": {"actor": {"prompt_version": "full-history-v2"}}},
              {"event": "reset", "view": {"allowed_actions": allowed}}]
    # Cost: 1 + 1 + 2 + 2 + 2 + 0 = 8, leaving one of nine units.
    turns = [
        ('{"action":"take water"}', None, "take water", 1, 0.25, 'You take water.\n"Quoted"'),
        ('{"action":"put water in counter"}', None, "put water in counter", 1, 0.25, "You put water down."),
        ('{"action":"take flour"}', '{"action":"examine cookbook"}', "examine cookbook", 2, 0.25, "Recipe."),
        ('not json', '{"action":"examine cookbook"}', "examine cookbook", 2, 0.25, "Recipe."),
        ('{"action":3}', '{"action":"examine cookbook"}', "examine cookbook", 2, 0.25, "Recipe."),
        ('{"action":"examine cookbook"}', None, "examine cookbook", 0, 0.25, "Insufficient budget."),
    ]
    budget = 9
    for step, (first, repair, action, cost, score, observation) in enumerate(turns, 1):
        for purpose, text in (("action", first), ("action_repair", repair)):
            if text is not None:
                events.extend([
                    {"event": "model_request", "step": step, "purpose": purpose,
                     "messages": [{"role": "user", "content": "Visible evidence only."}]},
                    {"event": "model_response", "step": step, "purpose": purpose, "text": text},
                ])
        budget -= cost
        events.append({"event": "action", "step": step, "transition": {
            "action": action, "valid_action": True, "executed": cost > 0,
            "action_cost": cost, "recipe_recheck": action == "examine cookbook" and cost > 0,
            "score": score, "view": {"allowed_actions": allowed, "budget_remaining": budget,
                                      "observation": observation},
        }})
    return events


def test_classification_and_behavior_match_hand_calculated_trace():
    report = analyze_events(sample())
    b = report["behavior"]
    assert b["action_output_validation"] == {
        "action": {"valid": 3, "unavailable_action": 1, "malformed_json": 1, "invalid_action_schema": 1},
        "action_repair": {"valid": 3},
    }
    assert b["executed_recipe_rechecks"] == 3
    assert b["recipe_recheck_budget_spent"] == 6
    assert b["distinct_recipe_recheck_observations"] == 1
    assert b["longest_same_action_streak"] == {
        "action": "examine cookbook", "attempts": 4, "executions": 3, "first_step": 3, "last_step": 6}
    assert b["longest_no_score_increase_streak"] == 5
    assert b["last_score_increase_step"] == 1 and b["maximum_observed_score"] == 0.25
    assert b["movement_attempts"] == 0
    assert [a["action"] for a in b["recorded_inventory_actions"]] == ["take water", "put water in counter"]
    assert report["turns"][2]["first_response_validation"] == "unavailable_action"
    assert report["turns"][-1]["executed"] is False


def test_missing_public_view_does_not_invent_action_availability():
    report = analyze_events([
        {"event": "model_response", "step": 1, "purpose": "action", "text": '{"action":"move east"}'}])
    assert report["behavior"]["action_output_validation"]["action"] == {"availability_unknown": 1}
    assert report["behavior"]["maximum_observed_score"] is None


def test_inspector_preserves_raw_trace_and_round_trips_csv(tmp_path, monkeypatch, capsys):
    trace, table = tmp_path / "events.jsonl", tmp_path / "actions.csv"
    raw = "".join(json.dumps(e) + "\n" for e in sample())
    trace.write_text(raw)
    monkeypatch.setattr("sys.argv", ["inspect_episode", str(trace), "--csv", str(table),
                                    "--step", "3", "--show-prompts"])
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert [t["step"] for t in report["turns"]] == [3]
    assert len(report["requests"]) == 2
    assert trace.read_text() == raw
    with table.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 6
    assert rows[0]["observation"] == 'You take water.\n"Quoted"'


def test_csv_argument_cannot_overwrite_jsonl(tmp_path, monkeypatch):
    trace = tmp_path / "events.jsonl"
    trace.write_text("original")
    monkeypatch.setattr("sys.argv", ["inspect_episode", str(trace), "--csv", str(trace)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert trace.read_text() == "original"
