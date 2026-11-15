"""Audit and summarize the frozen 20-seed, six-condition evaluation."""

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
import time

from game_memory.summarize_diagnostics import summarize


METRICS = ("success", "score", "recipe_rechecks", "budget_spent",
           "input_tokens", "output_tokens", "model_elapsed_seconds", "runtime_seconds")


def mean(values):
    return sum(values) / len(values)


def interval(values):
    ordered = sorted(values)
    return [ordered[int(0.025 * len(ordered))], ordered[int(0.975 * len(ordered))]]


def analyze(root: Path):
    protocol = json.loads((root / "evaluation-manifest.json").read_text())
    seeds = protocol["seeds"]
    conditions = [(item["strategy"], item["recheck_cost"])
                  for item in protocol["conditions"]]
    cells = {}
    for strategy, price in conditions:
        directory = root / f"{strategy}-p{price}"
        audit = summarize(directory)
        if not audit["logging_checks_passed"]:
            raise ValueError(f"Trace audit failed in {directory}: {audit['issues']}")
        if len(audit["episodes"]) != len(seeds):
            raise ValueError(f"Incomplete condition {directory}: {len(audit['episodes'])}/{len(seeds)}")
        results = {}
        for path in directory.glob("*/result.json"):
            result = json.loads(path.read_text())
            config = result["config"]
            seed = config["seed"]
            if seed in results or seed not in seeds:
                raise ValueError(f"Duplicate or unexpected seed {seed} in {directory}")
            if (config["strategy"], config["recheck_cost"]) != (strategy, price):
                raise ValueError(f"Wrong condition in {path}")
            if config["game"] != protocol["game"] or config["action_budget"] != protocol["action_budget"]:
                raise ValueError(f"Game settings changed in {path}")
            if config["memory_token_limit"] != protocol["memory_token_limit"]:
                raise ValueError(f"Memory allowance changed in {path}")
            if result["status"] != "completed" or result["kind"] != "evaluation":
                raise ValueError(f"Incomplete or mislabeled result in {path}")
            if result["components"]["actor"]["prompt_version"] != "s2-action-" + protocol["actor_prompt"]:
                raise ValueError(f"Actor prompt changed in {path}")
            if result["components"]["memory"]["prompt_version"] != protocol["memory_prompt_version"]:
                raise ValueError(f"Memory prompt changed in {path}")
            model = result["components"]["model"]
            if any(model.get(key) != value for key, value in protocol["model"].items()):
                raise ValueError(f"Model settings changed in {path}")
            results[seed] = result
        if set(results) != set(seeds):
            raise ValueError(f"Seed coverage mismatch in {directory}")
        cells[f"{strategy}-p{price}"] = results

    table = []
    for strategy, price in conditions:
        results = [cells[f"{strategy}-p{price}"][seed] for seed in seeds]
        row = {"strategy": strategy, "recheck_cost": price, "episodes": len(results),
               "wins": sum(result["success"] is True for result in results),
               "termination_counts": dict(Counter(result["termination_reason"] for result in results))}
        for metric in METRICS:
            row[metric + "_mean"] = mean([float(result[metric]) for result in results])
        table.append(row)

    rng = random.Random(20261106)
    draws = [[rng.choice(seeds) for _ in seeds] for _ in range(20_000)]

    def paired_difference(left, right, metric, selected):
        return mean([float(cells[left][seed][metric]) - float(cells[right][seed][metric])
                     for seed in selected])

    comparisons = []
    for price in (2, 5):
        for strategy in ("structured", "hybrid"):
            left, right = f"{strategy}-p{price}", f"prose-p{price}"
            for metric in ("success", "recipe_rechecks", "budget_spent", "runtime_seconds"):
                comparisons.append({"comparison": f"{left} minus {right}", "metric": metric,
                                    "estimate": paired_difference(left, right, metric, seeds),
                                    "bootstrap_95_interval": interval([
                                        paired_difference(left, right, metric, selected)
                                        for selected in draws])})
    for strategy in ("structured", "hybrid"):
        for metric in ("success", "recipe_rechecks"):
            def difference_in_differences(selected):
                return (paired_difference(f"{strategy}-p5", "prose-p5", metric, selected)
                        - paired_difference(f"{strategy}-p2", "prose-p2", metric, selected))
            comparisons.append({"comparison": f"{strategy} vs prose, price 5 minus price 2",
                                "metric": metric,
                                "estimate": difference_in_differences(seeds),
                                "bootstrap_95_interval": interval([
                                    difference_in_differences(selected) for selected in draws])})

    analysis = {"created_utc": datetime.now(timezone.utc).isoformat(),
                "planned_episodes": len(seeds) * len(conditions),
                "analyzed_episodes": sum(row["episodes"] for row in table),
                "source_digest": protocol["source_digest"],
                "table": table, "paired_comparisons": comparisons,
                "bootstrap": {"seed": 20261106, "resamples": len(draws),
                              "unit": "matched game seed", "interval": "percentile 95%"}}
    (root / "analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    lines = ["# Held-out 3×2 evaluation", "", f"Episodes: {analysis['analyzed_episodes']}/120.", "",
             "| Memory | Reread cost | Wins | Terminal failure | Budget exhausted | Mean score | Mean rereads | Mean budget spent | Mean input tokens | Mean output tokens | Mean model sec | Mean episode sec |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in table:
        counts = row["termination_counts"]
        lines.append("| {strategy} | {recheck_cost} | {wins}/20 | {failure} | {exhausted} | {score_mean:.3f} | {recipe_rechecks_mean:.2f} | {budget_spent_mean:.2f} | {input_tokens_mean:.0f} | {output_tokens_mean:.0f} | {model_elapsed_seconds_mean:.1f} | {runtime_seconds_mean:.1f} |".format(
            **row, failure=counts.get("terminal_failure", 0),
            exhausted=counts.get("budget_exhaustion", 0)))
    lines += ["", "## Paired contrasts", "", "Differences use matched seeds. Intervals resample whole seeds 20,000 times.", "",
              "| Contrast | Metric | Estimate | 95% bootstrap interval |",
              "|---|---|---:|---:|"]
    for item in comparisons:
        low, high = item["bootstrap_95_interval"]
        lines.append(f"| {item['comparison']} | {item['metric']} | {item['estimate']:.3f} | [{low:.3f}, {high:.3f}] |")
    (root / "analysis.md").write_text("\n".join(lines) + "\n")
    return analysis


if __name__ == "__main__":
    root = Path(sys.argv[1])
    if len(sys.argv) == 3:
        pid = int(sys.argv[2])
        while Path(f"/proc/{pid}").exists():
            time.sleep(30)
    result = analyze(root)
    print(f"Audited and analyzed {result['analyzed_episodes']} episodes", flush=True)
