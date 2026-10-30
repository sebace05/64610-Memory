"""Generate auditable S1 evidence using real games, not model inference.

Solution paths are privileged fixtures used only here. Never use them to choose
actions in the memory experiment or include them in an actor prompt.
"""

import argparse
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shlex
import subprocess
import sys

from textworld_express import TextWorldExpressEnv
from textworld_express.constants import JAR_PATH

from .contracts import CookingWorldConfig
from .environment import CookingWorldEnvironment, RECIPE_ACTIONS


def diagnostic_actions(seed: int, config: CookingWorldConfig) -> list[str]:
    backend = TextWorldExpressEnv(envStepLimit=1000)
    try:
        backend.reset(seed=seed, gameName="cookingworld", gameFold=config.game_fold,
                      gameParams=config.game_params(), generateGoldPath=True)
        # Add the alternative recipe-access command to exercise the bypass.
        return ["examine cookbook", *backend.getGoldActionSequence()]
    finally:
        backend.close()


def replay(seed: int, config: CookingWorldConfig, cost: int, actions: list[str]) -> list[dict]:
    with CookingWorldEnvironment(recheck_cost=cost) as env:
        initial = env.reset(seed, config)
        records = [{
            "event": "reset",
            "kind": "s1_diagnostic_not_model_evaluation",
            "metadata": env.metadata,
            "view": asdict(initial),
        }]
        for index, action in enumerate(actions, start=1):
            result = env.step(action)
            records.append({"event": "step", "step": index, **asdict(result)})
            if result.done:
                break
        return records


def engine_signature(records: list[dict]) -> list[dict]:
    """Remove treatment prices/budgets while retaining actual game behavior."""
    signatures = []
    for record in records:
        view = record["view"]
        signature = {k: view[k] for k in ("observation", "goal", "allowed_actions")}
        if record["event"] == "step":
            for key in ("action", "valid_action", "executed", "recipe_recheck",
                        "reward", "score", "score_raw", "success", "failure",
                        "terminated", "truncated", "termination_reason"):
                signature[key] = record[key]
        signatures.append(signature)
    return signatures


def verify(output_dir: Path, seeds: list[int], config: CookingWorldConfig) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for seed in seeds:
        actions = diagnostic_actions(seed, config)
        cheap = replay(seed, config, 2, actions)
        repeat = replay(seed, config, 2, actions)
        expensive = replay(seed, config, 5, actions)
        if cheap != repeat:
            raise RuntimeError(f"seed {seed}: reset/action replay is not reproducible")
        if engine_signature(cheap) != engine_signature(expensive):
            raise RuntimeError(f"seed {seed}: price changed game behavior")
        if not cheap[-1]["success"] or not expensive[-1]["success"]:
            raise RuntimeError(f"seed {seed}: diagnostic path did not complete within budget")
        rereads = sum(r.get("recipe_recheck", False) for r in cheap)
        difference = (sum(r.get("action_cost", 0) for r in expensive)
                      - sum(r.get("action_cost", 0) for r in cheap))
        if difference != 3 * rereads:
            raise RuntimeError(f"seed {seed}: incorrect treatment accounting")
        observed = {r.get("action") for r in cheap if r.get("recipe_recheck")}
        if not RECIPE_ACTIONS <= observed:
            raise RuntimeError(f"seed {seed}: both recipe aliases were not exercised")
        files = []
        for label, records in (("cheap", cheap), ("cheap-repeat", repeat), ("expensive", expensive)):
            filename = f"seed-{seed}-{label}.jsonl"
            with (output_dir / filename).open("w") as stream:
                for record in records:
                    stream.write(json.dumps(record, sort_keys=True) + "\n")
            files.append(filename)
        results.append({
            "seed": seed,
            "actions": len(cheap) - 1,
            "recipe_rechecks": rereads,
            "cheap_budget_spent": sum(r.get("action_cost", 0) for r in cheap),
            "expensive_budget_spent": sum(r.get("action_cost", 0) for r in expensive),
            "budget_difference": difference,
            "cheap_success": cheap[-1]["success"],
            "expensive_success": expensive[-1]["success"],
            "reset_replay_identical": True,
            "game_observations_scores_and_termination_identical": True,
            "both_recipe_access_commands_charged": True,
            "trace_files": files,
        })

    java = subprocess.run(["java", "-version"], capture_output=True, text=True, check=True)
    summary = {
        "kind": "s1_environment_verification_not_llm_results",
        "schema_version": 1,
        "command": shlex.join([sys.executable, "-m", "game_memory.verify_s1", *sys.argv[1:]]),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "java_version": (java.stdout + java.stderr).strip(),
        "textworld_express_version": version("textworld-express"),
        "jar_sha256": hashlib.sha256(Path(JAR_PATH).read_bytes()).hexdigest(),
        "game_config": asdict(config),
        "initial_recipe_cost": 0,
        "action_budget": 80,
        "results": results,
        "limitations": [
            "Scripted solution paths verify plumbing, not LLM capability or memory effectiveness.",
            "These are development fixtures, not the held-out evaluation seeds.",
            "Recipe access was checked via read/examine; this is not an exhaustive state-space audit.",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/s1"))
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    args = parser.parse_args()
    summary = verify(args.output_dir, args.seeds, CookingWorldConfig())
    for result in summary["results"]:
        print(f"seed={result['seed']} success at both prices; "
              f"rereads={result['recipe_rechecks']}; "
              f"budget={result['cheap_budget_spent']} vs {result['expensive_budget_spent']}; "
              "repeat and game behavior match")
    print(f"Saved traces and summary to {args.output_dir}")


if __name__ == "__main__":
    main()
