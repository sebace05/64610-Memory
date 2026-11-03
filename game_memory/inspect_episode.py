"""Offline trace inspection. Never feed this analysis or scores to the agent."""

import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from .actor import validate_action_output


def analyze_events(events: list[dict]) -> dict:
    """Classify output errors against the public view at each generation.

    A score plateau is a diagnostic proxy, not a reason to terminate or replace
    actions. Inventory actions below are observations of commands, not an
    inferred oracle inventory. The actor receives none of these derived fields.
    """
    header = next((e for e in events if e["event"] == "episode_start"), {})
    current_view = None
    responses = {}
    validations = {"action": Counter(), "action_repair": Counter()}
    turns = []
    inventory_actions = []
    frequencies = Counter()
    recipe_observations = set()
    recipe_count = recipe_cost = movement_attempts = 0
    best_score = 0.0
    observed_score = False
    no_increase = longest_no_increase = 0
    last_increase = None
    streak_action = None
    streak_start = streak_attempts = streak_executions = 0
    longest_streak = {"action": None, "attempts": 0, "executions": 0,
                      "first_step": None, "last_step": None}
    for event in events:
        name = event["event"]
        if name == "reset":
            current_view = event["view"]
        elif name == "model_response" and event["purpose"] in validations:
            purpose = event["purpose"]
            text = event.get("text")
            allowed = current_view.get("allowed_actions") if current_view is not None else None
            if text is None:
                reason = "response_text_missing"
            else:
                _, reason = validate_action_output(text, allowed)
            classification = reason or "valid"
            validations[purpose][classification] += 1
            responses[(event["step"], purpose)] = (text, classification)
        elif name == "action":
            step, transition = event["step"], event["transition"]
            action = transition.get("action", "")
            view = transition.get("view", {})
            first, first_reason = responses.get((step, "action"), (None, "response_missing"))
            repair, repair_reason = responses.get((step, "action_repair"), (None, None))
            row = {
                "step": step, "action": action,
                "first_response": first, "first_response_validation": first_reason,
                "repair_response": repair, "repair_response_validation": repair_reason,
                "valid_action": transition.get("valid_action"),
                "executed": transition.get("executed"),
                "action_cost": transition.get("action_cost"),
                "budget_remaining": view.get("budget_remaining"),
                "score": transition.get("score"), "observation": view.get("observation"),
            }
            turns.append(row)
            frequencies[action] += 1
            movement_attempts += action.startswith("move ")
            if transition.get("recipe_recheck"):
                recipe_count += 1
                recipe_cost += transition["action_cost"]
                recipe_observations.add(view.get("observation"))
            if transition.get("executed") and (action == "inventory" or
                                                action.startswith(("take ", "put "))):
                inventory_actions.append({"step": step, "action": action,
                                          "observation": view.get("observation")})
            score = transition.get("score")
            if isinstance(score, (int, float)):
                observed_score = True
                if score > best_score:
                    best_score, no_increase, last_increase = score, 0, step
                else:
                    no_increase += 1
                    longest_no_increase = max(longest_no_increase, no_increase)
            if action != streak_action:
                streak_action, streak_start, streak_attempts, streak_executions = action, step, 0, 0
            streak_attempts += 1
            streak_executions += bool(transition.get("executed"))
            if streak_attempts > longest_streak["attempts"]:
                longest_streak = {"action": action, "attempts": streak_attempts,
                                  "executions": streak_executions,
                                  "first_step": streak_start, "last_step": step}
            current_view = view
    return {
        "kind": "offline_episode_inspection", "episode_id": header.get("episode_id"),
        "episode_kind": header.get("kind"),
        "actor": header.get("components", {}).get("actor"),
        "behavior": {
            "action_output_validation": {p: dict(c) for p, c in validations.items()},
            "action_frequencies": dict(frequencies),
            "movement_attempts": movement_attempts,
            "executed_recipe_rechecks": recipe_count,
            "recipe_recheck_budget_spent": recipe_cost,
            "distinct_recipe_recheck_observations": len(recipe_observations),
            "longest_same_action_streak": longest_streak,
            "longest_no_score_increase_streak": longest_no_increase,
            "last_score_increase_step": last_increase,
            "maximum_observed_score": best_score if observed_score else None,
            "recorded_inventory_actions": inventory_actions,
        },
        "turns": turns,
        "errors": [e for e in events if e["event"] in {"episode_error", "model_error"}],
        "interpretation": "Score plateaus can include useful exploration. Command records do not "
                          "constitute an oracle inventory. Review observations before attributing failures.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--csv", type=Path, help="Save a derived turn table as a .csv file")
    parser.add_argument("--step", type=int, help="Inspect one turn instead of printing all turns")
    parser.add_argument("--show-prompts", action="store_true")
    args = parser.parse_args()
    if args.show_prompts and args.step is None:
        parser.error("--show-prompts requires --step")
    if args.csv and args.csv.suffix.lower() != ".csv":
        parser.error("--csv must name a .csv file; raw traces/results must be preserved")
    if args.csv and args.csv.resolve() == args.trace.resolve():
        parser.error("CSV output cannot overwrite the input trace")
    try:
        events = [json.loads(line) for line in args.trace.read_text().splitlines()]
        report = analyze_events(events)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="") as stream:
            fields = list(report["turns"][0]) if report["turns"] else ["step", "action"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(report["turns"])
    if args.step is not None:
        matching = [e for e in events if e.get("step") == args.step]
        if not matching:
            parser.error("requested step is absent from the trace")
        report["turns"] = [t for t in report["turns"] if t["step"] == args.step]
        report["errors"] = [e for e in report["errors"] if e.get("step") == args.step]
        if args.show_prompts:
            report["requests"] = [e for e in matching if e["event"] == "model_request"]
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
