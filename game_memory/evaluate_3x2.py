"""Run the frozen 120-episode held-out grid with one loaded Qwen model."""

import argparse
import json
from pathlib import Path

from .actor import PromptedActor
from .contracts import CookingWorldConfig
from .environment import CookingWorldEnvironment
from .memory import HybridMemory, ProseMemory, StructuredMemory, PROMPT_VERSION
from .pilot import prepare_pilot, runtime_environment
from .runner import EpisodeConfig, run_episode, source_digest
from .summarize_diagnostics import summarize
from .transformers_model import TransformersConfig, TransformersModel


MEMORIES = {"prose": ProseMemory, "structured": StructuredMemory,
            "hybrid": HybridMemory}


def completed_seeds(directory: Path) -> set[int]:
    """Read durable results; a partial or erroneous episode requires review."""
    completed = set()
    for path in directory.glob("*/result.json"):
        result = json.loads(path.read_text())
        if result["status"] != "completed":
            raise ValueError(f"Infrastructure error in {path}; preserve and investigate it")
        seed = result["config"]["seed"]
        if seed in completed:
            raise ValueError(f"Duplicate seed {seed} in {directory}")
        completed.add(seed)
    for path in directory.glob("*/events.jsonl"):
        if not (path.parent / "result.json").exists():
            raise ValueError(f"Partial episode in {path.parent}; preserve it before resuming")
    return completed


def run(root: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    protocol = json.loads((root / "evaluation-manifest.json").read_text())
    if source_digest(repo) != protocol["source_digest"]:
        raise ValueError("Executable source changed since the evaluation freeze")
    seeds = tuple(protocol["seeds"])
    if len(seeds) != 20 or len(set(seeds)) != 20:
        raise ValueError("Evaluation requires 20 distinct frozen seeds")
    conditions = tuple((item["strategy"], item["recheck_cost"])
                       for item in protocol["conditions"])
    if set(conditions) != {(name, price) for name in MEMORIES for price in (2, 5)}:
        raise ValueError("Evaluation requires all six distinct conditions")
    if PROMPT_VERSION != protocol["memory_prompt_version"]:
        raise ValueError("Memory prompt changed since the evaluation freeze")
    actor = PromptedActor(prompt_version=protocol["actor_prompt"])
    if "immediate_repeat_policy" in actor.metadata:
        raise ValueError("Frozen actor must leave legal repeats available")
    model_config = TransformersConfig(**protocol["model"])
    game = CookingWorldConfig(**protocol["game"])
    if game.game_fold != "test":
        raise ValueError("Held-out evaluation must use the test fold")

    import os
    os.environ.update(runtime_environment())
    done = {}
    for strategy, price in conditions:
        directory = root / f"{strategy}-p{price}"
        seen = completed_seeds(directory)
        if not seen <= set(seeds):
            raise ValueError(f"Unexpected seed in {directory}")
        remaining = [seed for seed in seeds if seed not in seen]
        config = EpisodeConfig(seed=seeds[0], strategy=strategy, recheck_cost=price,
                               action_budget=protocol["action_budget"],
                               memory_token_limit=protocol["memory_token_limit"], game=game)
        prepare_pilot(directory, config, actor, model_config, "transformers", remaining,
                      memory_metadata=MEMORIES[strategy]().metadata,
                      protocol_id="deferred-3x2-v1")
        done[(strategy, price)] = seen

    if all(len(seen) == len(seeds) for seen in done.values()):
        print("All 120 evaluation episodes already have results.", flush=True)
    else:
        model = TransformersModel(model_config)
        for seed in seeds:
            for strategy, price in conditions:
                if seed in done[(strategy, price)]:
                    continue
                config = EpisodeConfig(seed=seed, strategy=strategy, recheck_cost=price,
                                       action_budget=protocol["action_budget"],
                                       memory_token_limit=protocol["memory_token_limit"], game=game)
                directory = root / f"{strategy}-p{price}"
                with CookingWorldEnvironment(recheck_cost=price,
                                             action_budget=config.action_budget) as environment:
                    result = run_episode(config, environment,
                                         PromptedActor(prompt_version=protocol["actor_prompt"]),
                                         MEMORIES[strategy](), model, output_dir=directory,
                                         protocol_id="deferred-3x2-v1")
                print(f"seed={seed} {strategy} price={price} status={result['status']} "
                      f"termination={result['termination_reason']} steps={result['steps']} "
                      f"spent={result['budget_spent']}", flush=True)
                if result["status"] != "completed":
                    raise RuntimeError(f"Infrastructure error; inspect {directory / result['episode_id']}")
                done[(strategy, price)].add(seed)
                if len(done[(strategy, price)]) == 1:
                    report = summarize(directory)
                    if not report["logging_checks_passed"]:
                        raise RuntimeError(f"First trace audit failed in {directory}: {report['issues']}")

    for strategy, price in conditions:
        directory = root / f"{strategy}-p{price}"
        report = summarize(directory)
        (directory / "checkpoint-report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n")
        if not report["logging_checks_passed"] or len(report["episodes"]) != len(seeds):
            raise RuntimeError(f"Coverage or trace audit failed in {directory}")
    print("All 120 evaluation episodes completed and passed trace audits.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    run(args.root)


if __name__ == "__main__":
    main()
