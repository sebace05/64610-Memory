"""Offline declared-grid analysis. No inference, launching, or semantic intervention."""

import argparse
import csv
from dataclasses import fields
import io
import itertools
import json
from pathlib import Path

from .summarize_diagnostics import summarize
from .contracts import CookingWorldConfig
from .transformers_model import TransformersConfig


def summarize_annotation(checkpoint: dict) -> dict:
    """Count supplied human labels; never infer facts or parse agent content."""
    required = checkpoint["required"]
    assessments = checkpoint["assessments"]
    if len(set(required)) != len(required) or set(required) != set(assessments):
        raise ValueError("required facts must have exactly one assessment each")
    statuses = {"supported", "omission", "contradiction", "unknown"}
    if any(value not in statuses for value in assessments.values()):
        raise ValueError("unknown fact assessment")
    claims = checkpoint["claims"]
    if any(c["classification"] not in {"supported", "contradiction", "invented", "unknown"} for c in claims):
        raise ValueError("unknown claim assessment")
    supported = sum(v == "supported" for v in assessments.values())
    inspectable = sum(c["classification"] != "unknown" for c in claims)
    incorrect = sum(c["classification"] in {"contradiction", "invented"} for c in claims)
    return {"required_facts": len(required), "supported_facts": supported,
            "omissions": sum(v == "omission" for v in assessments.values()),
            "unknown_facts": sum(v == "unknown" for v in assessments.values()),
            "retention": supported / len(required) if required else None,
            "inspectable_claims": inspectable, "incorrect_claims": incorrect,
            "claim_accuracy": (inspectable - incorrect) / inspectable if inspectable else None}


def validate_manifest(manifest: dict) -> None:
    required = {"schema_version", "protocol_id", "stage", "source", "actor", "memory",
                "model", "runtime", "game", "action_budget", "strategies",
                "memory_token_limits", "recheck_costs", "seeds"}
    if not required <= manifest.keys():
        raise ValueError("comparison manifest missing required fields")
    if manifest["schema_version"] != 1 or not isinstance(manifest["protocol_id"], str) or not manifest["protocol_id"].strip():
        raise ValueError("invalid comparison schema/protocol")
    if manifest["stage"] not in {"development", "held_out"}:
        raise ValueError("invalid stage")
    for key in ("strategies", "memory_token_limits", "recheck_costs", "seeds"):
        values = manifest[key]
        if not isinstance(values, list) or not values or len(set(values)) != len(values):
            raise ValueError(f"{key} must be a nonempty unique list")
    if set(manifest["strategies"]) != {"prose", "structured"}:
        raise ValueError("comparison requires both strategies")
    if len(manifest["memory_token_limits"]) != 2 or any(type(v) is not int or v <= 0 for v in manifest["memory_token_limits"]):
        raise ValueError("comparison requires two positive integer allowances")
    if any(type(v) is not int or v not in {2, 5} for v in manifest["recheck_costs"]):
        raise ValueError("invalid reread prices")
    if any(type(v) is not int for v in manifest["seeds"]):
        raise ValueError("seeds must be integers")
    if type(manifest["action_budget"]) is not int or manifest["action_budget"] <= 0:
        raise ValueError("invalid action budget")
    if not manifest["source"].get("source_digest"):
        raise ValueError("source_digest required")
    for key in ("actor", "memory", "model", "runtime", "game"):
        if not isinstance(manifest[key], dict) or not manifest[key]:
            raise ValueError(f"{key} identity required")
    for key, cls in (("model", TransformersConfig), ("game", CookingWorldConfig)):
        if set(manifest[key]) != {field.name for field in fields(cls)}:
            raise ValueError(f"{key} must contain serialized configuration fields")
        cls(**manifest[key])
    if set(manifest["memory"]) != {"prose", "structured"}:
        raise ValueError("memory identities must match strategies")
    # Identity equality below also prevents mixing historical and new policies.
    identities = list(manifest["memory"].values())
    for key in ("prompt_version", "version", "update_policy", "semantic_validation",
                "fallback", "max_repairs", "render_version"):
        if any(key not in value for value in identities) or identities[0][key] != identities[1][key]:
            raise ValueError(f"memory policy mismatch: {key}")
    fold = manifest["game"].get("game_fold")
    if (manifest["stage"] == "held_out" and fold != "test") or (manifest["stage"] == "development" and fold not in {"train", "dev"}):
        raise ValueError("stage disagrees with game fold")


def analyze(root: Path, manifest: dict | None = None, *, include_fixtures: bool = False) -> dict:
    """Audit each immutable condition, then require the exact declared cells.

    Invalid/error cells remain visible; primary contrasts are unavailable until
    the entire planned grid is technically valid and completed. Losses count zero.
    """
    root = Path(root)
    if manifest is None:
        manifest = json.loads((root / "comparison-manifest.json").read_text())
    validate_manifest(manifest)
    expected = set(itertools.product(manifest["strategies"], manifest["memory_token_limits"],
                                     manifest["recheck_costs"], manifest["seeds"]))
    issues, rows, seen = [], [], set()
    pilots = sorted(root.rglob("pilot-manifest.json"))
    covered_files = set()
    for path in pilots:
        directory = path.parent
        try:
            pilot = json.loads(path.read_text())
            config = pilot["episode"]
            strategy = config["strategy"]
            wanted = {"strategy": strategy, "memory_token_limit": config["memory_token_limit"],
                      "recheck_cost": config["recheck_cost"], "action_budget": manifest["action_budget"],
                      "game": manifest["game"]}
            if config != wanted:
                raise ValueError("condition settings disagree with comparison")
            identities = {"source": manifest["source"], "actor": manifest["actor"],
                          "memory": manifest["memory"][strategy], "model": manifest["model"],
                          "runtime": manifest["runtime"], "protocol_id": manifest["protocol_id"]}
            if pilot["schema_version"] != 2 or any(pilot.get(k) != v for k, v in identities.items()):
                raise ValueError("condition identity/schema disagrees with comparison")
            report = summarize(directory, include_fixtures=include_fixtures)
            issues.extend({"directory": str(directory.relative_to(root)), **issue} for issue in report["issues"])
            issues.extend({"directory": str(directory.relative_to(root) / p), "error": "partial cell"}
                          for p in report["pending"])
            for result_path in directory.rglob("result.json"):
                covered_files.add(result_path)
                result = json.loads(result_path.read_text())
                cell = (result["config"]["strategy"], result["config"]["memory_token_limit"],
                        result["config"]["recheck_cost"], result["config"]["seed"])
                if cell in seen:
                    issues.append({"directory": str(result_path.parent.relative_to(root)), "error": "duplicate cell", "cell": list(cell)})
                seen.add(cell)
                if cell not in expected:
                    issues.append({"directory": str(result_path.parent.relative_to(root)), "error": "unplanned cell", "cell": list(cell)})
                actual = {k: v for k, v in result["config"].items() if k != "seed"}
                model = result["components"]["model"]
                if (actual != config or result.get("source") != manifest["source"]
                    or result["components"]["actor"] != manifest["actor"]
                    or result["components"]["memory"] != identities["memory"]
                    or any(model.get(k) != v for k, v in (manifest["model"] | manifest["runtime"]).items())
                    or result.get("protocol_id") != manifest["protocol_id"]):
                    issues.append({"directory": str(result_path.parent.relative_to(root)), "error": "episode identity/settings mismatch"})
                if result["status"] != "completed":
                    issues.append({"directory": str(result_path.parent.relative_to(root)), "error": "error cell"})
            for episode in report["episodes"]:
                rows.append({**episode, "strategy": strategy, "memory_token_limit": config["memory_token_limit"],
                             "recheck_cost": config["recheck_cost"],
                             "condition": str(directory.relative_to(root))})
        except (OSError, ValueError, KeyError, TypeError) as error:
            issues.append({"directory": str(directory.relative_to(root)), "error": str(error)})
    for path in set(root.rglob("result.json")) - covered_files:
        issues.append({"directory": str(path.parent.relative_to(root)), "error": "unaudited result"})
    for path in root.rglob("events.jsonl"):
        if not any(parent == pilot.parent for pilot in pilots for parent in path.parents):
            issues.append({"directory": str(path.parent.relative_to(root)), "error": "orphan trace"})
    missing = sorted(expected - seen)
    issues.extend({"cell": list(cell), "error": "missing cell"} for cell in missing)
    effects = []
    if not issues:
        low, high = sorted(manifest["memory_token_limits"])
        values = {(r["strategy"], r["memory_token_limit"], r["recheck_cost"], r["seed"]): int(r["success"])
                  for r in rows}
        for price in manifest["recheck_costs"]:
            contrasts = {strategy: sum(values[strategy, high, price, seed] - values[strategy, low, price, seed]
                                      for seed in manifest["seeds"]) / len(manifest["seeds"])
                         for strategy in manifest["strategies"]}
            effects.append({"recheck_cost": price, "high_minus_low": contrasts,
                            "interaction_json_minus_prose": contrasts["structured"] - contrasts["prose"]})
    return {"schema_version": 1, "protocol_id": manifest["protocol_id"], "stage": manifest["stage"],
            "valid": not issues, "planned_cells": len(expected), "observed_cells": len(seen),
            "issues": issues, "episodes": rows, "allowance_effects": effects,
            "interpretation": "Matched descriptive results; development seeds do not support strong statistical claims."}


def render_report(report: dict, format: str) -> str:
    if format == "json":
        return json.dumps(report, indent=2, sort_keys=True) + "\n"
    columns = ["strategy", "memory_token_limit", "recheck_cost", "seed", "status", "success",
               "termination_reason", "score", "steps", "recipe_rechecks", "budget_spent",
               "input_tokens", "output_tokens", "model_elapsed_seconds", "runtime_seconds", "load_seconds",
               "usage_complete", "memory_evidence", "generation_by_purpose", "output_limit_hits",
               "launcher_exit_status"]
    if format == "csv":
        columns += ["comparison_valid", "comparison_issues", "allowance_effects"]
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                          for k, v in {**row, "comparison_valid": report["valid"],
                                       "comparison_issues": report["issues"],
                                       "allowance_effects": report["allowance_effects"]}.items()}
                         for row in (report["episodes"] or [{}]))
        return stream.getvalue()
    if format != "markdown":
        raise ValueError("unknown report format")
    lines = [f"Valid comparison: {report['valid']}", "", "| " + " | ".join(columns) + " |",
             "| " + " | ".join("---" for _ in columns) + " |"]
    lines.extend("| " + " | ".join(str(row.get(k, "unknown")).replace("|", "\\|") for k in columns) + " |"
                 for row in report["episodes"])
    lines.extend(["", "Issues: " + json.dumps(report["issues"]), "",
                  "Allowance effects: " + json.dumps(report["allowance_effects"]), "", report["interpretation"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--format", choices=["json", "csv", "markdown"], default="json")
    parser.add_argument("--include-fixtures", action="store_true")
    args = parser.parse_args()
    report = analyze(args.root, include_fixtures=args.include_fixtures)
    print(render_report(report, args.format), end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
