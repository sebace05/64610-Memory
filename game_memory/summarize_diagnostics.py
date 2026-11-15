"""Audit real pilot logs and traces; never interpret fixtures as model capability."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from .actor import validate_action_output
from .inspect_episode import analyze_events

def summarize(root: Path, *, include_fixtures: bool = False) -> dict:
    directories = sorted({p.parent for pattern in ("events.jsonl", "result.json")
                          for p in root.rglob(pattern)})
    if not directories:
        raise ValueError("no episode traces or results found")
    episodes, issues, pending, fingerprints, identities = [], [], [], set(), set()
    for directory in directories:
        label = str(directory.relative_to(root))
        if not (directory / "result.json").exists():
            pending.append(label)
            continue
        try:
            result = json.loads((directory / "result.json").read_text())
            events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]

            def require(condition, message):
                if not condition:
                    raise ValueError(message)

            strategy = result["config"]["strategy"]
            require(strategy in {"full_history", "prose", "structured", "hybrid"},
                    "unknown memory strategy")
            fixture = any(c.get("is_fake") is not False for c in result["components"].values())
            require(include_fixtures or not fixture, "fixture excluded; use --include-fixtures only for plumbing checks")
            expected_kind = ("integration_fixture" if fixture else
                             "full_history_diagnostic" if strategy == "full_history" else
                             "evaluation" if result["config"]["game"]["game_fold"] == "test"
                             else "development")
            require(result["kind"] == expected_kind,
                    "component labels disagree with result kind")
            require(events and events[0]["event"] == "episode_start", "missing episode_start")
            require(events[-1]["event"] == "episode_end", "missing episode_end")
            require(events[-1]["result"] == result, "result disagrees with trace")
            require([e["sequence"] for e in events] == list(range(len(events))), "broken event sequence")
            require(events[0]["config"] == result["config"] and
                    events[0]["components"] == result["components"], "header disagrees with result")
            require(events[0].get("source") == result.get("source"), "source identity disagrees with trace")
            require(events[0].get("memory_token_limit_applies") is (strategy != "full_history"),
                    "memory token-limit policy is not explicit")
            actions = [e["transition"] for e in events if e["event"] == "action"]
            replies = [e for e in events if e["event"] == "model_response"]
            require(result["steps"] == len(actions), "step total disagrees with trace")
            require(result["budget_spent"] == sum(a["action_cost"] for a in actions), "budget total disagrees with trace")
            require(result["recipe_rechecks"] == sum(a["recipe_recheck"] for a in actions), "reread total disagrees with trace")
            for field in ("input_tokens", "output_tokens"):
                require(result[field] == sum(e[field] for e in replies), f"{field} total disagrees with trace")
            require(math.isclose(result["model_elapsed_seconds"],
                                 sum(e["elapsed_seconds"] for e in replies)),
                    "model latency total disagrees with trace")
            require(set(result["usage_by_purpose"]) == {e["purpose"] for e in replies},
                    "usage purpose labels disagree with trace")
            for purpose, usage in result["usage_by_purpose"].items():
                selected = [e for e in replies if e["purpose"] == purpose]
                require(usage["calls"] == len(selected), "purpose call total disagrees with trace")
                for field in ("input_tokens", "output_tokens"):
                    require(usage[field] == sum(e[field] for e in selected),
                            f"purpose {field} total disagrees with trace")
            request = None
            model_errors = 0
            for event in events:
                if event["event"] == "model_request":
                    require(request is None, "unmatched model request")
                    request = (event["step"], event["purpose"])
                elif event["event"] in {"model_response", "model_error"}:
                    require(request == (event["step"], event["purpose"]), "unmatched model response/error")
                    request = None
                    model_errors += event["event"] == "model_error"
            require(request is None, "unfinished model request")
            require(result["usage_complete"] == (model_errors == 0), "incorrect usage completeness")
            updates = [e for e in events if e["event"] == "memory_update"]
            memory_replies = [e for e in replies if e["purpose"].startswith("memory")]
            latest_memory_by_request = {}
            latest_memory = None
            for event in events:
                if event["event"] == "memory_update":
                    latest_memory = event["memory"]
                elif (event["event"] == "model_request"
                      and event["purpose"] in {"action", "action_review", "action_repair"}):
                    latest_memory_by_request[event["sequence"]] = latest_memory
            if strategy == "full_history":
                require(not memory_replies, "full-history diagnostic unexpectedly ran a memory writer")
            else:
                limit = result["config"]["memory_token_limit"]
                require(bool(memory_replies), "bounded-memory episode has no writer calls")
                require(all(type(e["memory_tokens"]) is int and 0 <= e["memory_tokens"] <= limit
                            for e in updates), "rendered memory exceeds its declared token allowance")
                require(sum(e["purpose"] == "memory" for e in memory_replies) == len(updates),
                        "memory update count disagrees with primary writer calls")
                for event in events:
                    if event["event"] != "model_request" or not event["purpose"].startswith("memory"):
                        continue
                    require(len(event["messages"]) in {2, 4},
                            "memory writer received unexpected message history")
                    payload = json.loads(event["messages"][1]["content"])
                    require(set(payload) == {"previous_memory", "action", "observation", "context"},
                            "memory writer input contains unexpected fields")
                    require(set(payload["context"]) == {"goal", "budget_remaining", "recheck_cost",
                                                         "memory_token_limit"},
                            "memory writer context contains unexpected fields")
                for event in events:
                    if event["event"] != "model_request" or event["purpose"] not in {"action", "action_review", "action_repair"}:
                        continue
                    require(len(event["messages"]) in {2, 4}, "actor received unexpected conversation history")
                    user = event["messages"][1]["content"]
                    public, rendered = user.split("\nBounded memory:\n", maxsplit=1)
                    payload = json.loads(public.removeprefix("Current game input:\n"))
                    require(set(payload) == {"observation", "goal", "allowed_actions",
                                             "budget_remaining", "recheck_cost"},
                            "bounded actor input contains unexpected fields")
                    latest = latest_memory_by_request[event["sequence"]]
                    if rendered != latest:
                        prefix = latest + "\nPrevious unavailable proposal: "
                        require(event["purpose"] in {"action_repair", "action_review"} and
                                result["components"]["actor"].get("action_repair_policy") in {
                                    "qwen_unavailable_action_progress_review_v1",
                                    "qwen_format_neutral_unavailable_review_v1"} and
                                rendered.startswith(prefix),
                                "actor input disagrees with the latest bounded memory update")
                        proposal = rendered[len(prefix):]
                        preceding = [response for response in replies
                                     if response["step"] == event["step"] and
                                     response["sequence"] < event["sequence"] and
                                     response["purpose"] in {"action", "action_review"}]
                        require(any(validate_action_output(response["text"],
                                                           payload["allowed_actions"])[0] == proposal
                                    for response in preceding),
                                "actor repair proposal was not recorded in this turn")
            require(result["status"] in {"completed", "error"}, "unknown episode status")
            if result["status"] == "completed":
                guard_failures = [e for e in events if e["event"] == "actor_guard_failure"]
                if result["termination_reason"] == "actor_guard_failure":
                    require(len(guard_failures) == 1 and guard_failures[0]["step"] == len(actions) + 1,
                            "actor guard failure disagrees with trace")
                    require(result["success"] is False and result["failure"] is False,
                            "actor guard failure was mislabeled as a game outcome")
                else:
                    require(bool(actions) and actions[-1]["termination_reason"] == result["termination_reason"],
                            "completed episode has no matching terminal action")
                    require(result["success"] == actions[-1]["success"], "success disagrees with trace")
            else:
                require(result["success"] is None and result["error"] is not None,
                        "infrastructure error must not be labeled a game loss")
            config = {k: v for k, v in result["config"].items() if k != "seed"}
            model = {k: v for k, v in result["components"]["model"].items() if k != "load_seconds"}
            fingerprint = json.dumps({"config": config, "model": model,
                                      "actor": result["components"]["actor"],
                                      "memory": result["components"]["memory"],
                                      "source": result.get("source")}, sort_keys=True)
            fingerprints.add(fingerprint)
            identity = (fingerprint, result["config"]["seed"])
            require(identity not in identities, "duplicate game seed/configuration; use a separate attempt directory")
            identities.add(identity)
            episodes.append({
                "directory": label, "episode_id": result["episode_id"],
                "kind": result["kind"], "seed": result["config"]["seed"],
                "status": result["status"], "success": result["success"],
                "termination_reason": result["termination_reason"], "error": result["error"],
                "steps": result["steps"], "budget_spent": result["budget_spent"],
                "recipe_rechecks": result["recipe_rechecks"],
                "invalid_actions": sum(not a["valid_action"] for a in actions),
                "action_repair_calls": sum(e["purpose"] == "action_repair" for e in replies),
                "actor_guard_failures": sum(e["event"] == "actor_guard_failure" for e in events),
                "output_limit_hits": sum(e.get("metadata", {}).get("finish_reason") == "length" for e in replies),
                "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
                "model_elapsed_seconds": result["model_elapsed_seconds"],
                "runtime_seconds": result["runtime_seconds"],
                "actor_prompt": result["components"]["actor"].get("prompt_version"),
                "memory_strategy": strategy,
                "memory_calls": sum(e["purpose"] == "memory" for e in memory_replies),
                "memory_repair_calls": sum(e["purpose"] == "memory_repair" for e in memory_replies),
                "max_memory_tokens": max((e["memory_tokens"] for e in updates), default=0),
                "fixture": fixture,
                "behavior": analyze_events(events)["behavior"],
            })
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            issues.append({"directory": label, "error": str(error)})
    if len(fingerprints) > 1:
        issues.append({"directory": ".", "error": "mixed configurations or source identities; summarize each pilot separately"})
    real = [e for e in episodes if not e["fixture"]]
    completed = [e for e in real if e["status"] == "completed"]
    clean = not issues and not pending
    return {
        "kind": ("full_history_checkpoint_report" if real and
                 all(e["memory_strategy"] == "full_history" for e in real)
                 else "bounded_memory_checkpoint_report"), "logging_checks_passed": clean,
        "real_model_capability_tested": bool(completed),
        "infrastructure_checks_passed": clean and bool(completed) and len(completed) == len(real),
        "real_completed": len(completed), "real_successes": sum(e["success"] is True for e in completed),
        "real_infrastructure_errors": len(real) - len(completed),
        "fixture_episodes": len(episodes) - len(real),
        "termination_counts": dict(Counter(e["termination_reason"] for e in real)),
        "issues": issues, "pending": pending, "episodes": episodes,
        "interpretation": "Inspect traces for gameplay, planning, and information-use failures. "
                          "This report does not establish memory-strategy effectiveness or statistical significance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--include-fixtures", action="store_true")
    args = parser.parse_args()
    try:
        report = summarize(args.root, include_fixtures=args.include_fixtures)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))
    # Gameplay losses are data. Broken logs, pending runs, and infrastructure
    # errors fail this technical checkpoint, independently of capability.
    return 0 if (report["logging_checks_passed"] and not report["real_infrastructure_errors"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
