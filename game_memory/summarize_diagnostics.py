"""Audit full-history pilot logs; never interpret fixtures as model capability."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path


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

            require(result["config"]["strategy"] == "full_history", "not a full-history diagnostic")
            fixture = any(c.get("is_fake") is not False for c in result["components"].values())
            require(include_fixtures or not fixture, "fixture excluded; use --include-fixtures only for plumbing checks")
            require(result["kind"] == ("integration_fixture" if fixture else "full_history_diagnostic"),
                    "component labels disagree with result kind")
            require(events and events[0]["event"] == "episode_start", "missing episode_start")
            require(events[-1]["event"] == "episode_end", "missing episode_end")
            require(events[-1]["result"] == result, "result disagrees with trace")
            require([e["sequence"] for e in events] == list(range(len(events))), "broken event sequence")
            require(events[0]["config"] == result["config"] and
                    events[0]["components"] == result["components"], "header disagrees with result")
            require(events[0].get("source") == result.get("source"), "source identity disagrees with trace")
            require(events[0].get("memory_token_limit_applies") is False, "history limit exemption not explicit")
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
            require(not any(e["purpose"].startswith("memory") for e in replies), "diagnostic unexpectedly ran a memory writer")
            require(result["status"] in {"completed", "error"}, "unknown episode status")
            if result["status"] == "completed":
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
                "output_limit_hits": sum(e.get("metadata", {}).get("finish_reason") == "length" for e in replies),
                "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
                "model_elapsed_seconds": result["model_elapsed_seconds"],
                "runtime_seconds": result["runtime_seconds"],
            })
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            issues.append({"directory": label, "error": str(error)})
    if len(fingerprints) > 1:
        issues.append({"directory": ".", "error": "mixed configurations or source identities; summarize each pilot separately"})
    real = [e for e in episodes if e["kind"] == "full_history_diagnostic"]
    completed = [e for e in real if e["status"] == "completed"]
    clean = not issues and not pending
    return {
        "kind": "full_history_checkpoint_report", "logging_checks_passed": clean,
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
