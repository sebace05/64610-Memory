"""Run fixture episodes or explicit real-model full-history diagnostics."""

import argparse
import os
from pathlib import Path

from .actor import PROMPT_VERSIONS, PromptedActor
from .environment import CookingWorldEnvironment
from .diagnostics import FullHistoryMemory
from .integration_fixtures import FakeMemory, FakeModel
from .runner import EpisodeConfig, run_episode


def main(argv=None) -> int:
    # Read launch options, not saved JSON artifacts. Example:
    # python -m game_memory.run_episode --strategy hybrid --recheck-cost 5
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["fake", "transformers"], default="fake")
    parser.add_argument("--strategy", choices=["prose", "structured", "hybrid", "full_history"],
                        default="prose")
    parser.add_argument("--recheck-cost", type=int, choices=[2, 5], default=2)
    parser.add_argument("--actor-prompt", choices=PROMPT_VERSIONS, default="v1",
                        help="v1 reproduces the baseline; v2 adds progress and specific repair instructions")
    seeds = parser.add_mutually_exclusive_group()
    seeds.add_argument("--seed", type=int, default=0)
    seeds.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--action-budget", type=int, default=None)
    parser.add_argument("--memory-token-limit", type=int, default=256)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--model-id", default="Qwen/Qwen3-4B-Instruct-2507")
    parser.add_argument("--model-revision", help="Immutable 40-character Hugging Face commit")
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--dtype", choices=["bfloat16", "float16", "float32"], default="bfloat16")
    parser.add_argument("--context-limit", type=int, default=8192)
    parser.add_argument("--action-max-new-tokens", type=int, default=128)
    parser.add_argument("--memory-max-new-tokens", type=int, default=512)
    parser.add_argument("--generation-seed", type=int, default=0)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--pilot", action="store_true", help="Enforce an immutable pilot manifest and attempt guards")
    parser.add_argument("--prepare-only", action="store_true", help="Validate and record the pilot without loading weights")
    args = parser.parse_args(argv)
    if args.prepare_only and not args.pilot:
        parser.error("--prepare-only requires --pilot")
    if args.backend == "transformers":
        if args.strategy != "full_history":
            parser.error("real inference currently requires --strategy full_history; "
                         "P1 bounded-memory integration with this CLI remains pending")
        if not args.model_revision:
            parser.error("--model-revision is required for real inference")
    elif args.model_revision:
        parser.error("--model-revision requires --backend transformers")
    selected_seeds = args.seeds if args.seeds is not None else [args.seed]
    if len(set(selected_seeds)) != len(selected_seeds):
        parser.error("duplicate game seeds are not allowed in a diagnostic invocation")
    budget = args.action_budget if args.action_budget is not None else (
        80 if args.backend == "transformers" else 6)
    # Validate the entire requested set before loading weights or starting Java.
    try:
        configs = [EpisodeConfig(seed=seed, strategy=args.strategy,
                                 recheck_cost=args.recheck_cost, action_budget=budget,
                                 memory_token_limit=args.memory_token_limit)
                   for seed in selected_seeds]
        if args.backend == "transformers":
            from .transformers_model import TransformersConfig
            model_config = TransformersConfig(
                revision=args.model_revision, model_id=args.model_id, device=args.device,
                dtype=args.dtype, context_limit=args.context_limit,
                action_max_new_tokens=args.action_max_new_tokens,
                memory_max_new_tokens=args.memory_max_new_tokens,
                generation_seed=args.generation_seed, local_files_only=args.local_files_only,
            )
    except ValueError as error:
        parser.error(str(error))
    default_output = ("artifacts/qwen-diagnostics" if args.backend == "transformers" else
                      "artifacts/qwen-diagnostic-fixtures" if args.strategy == "full_history" else
                      "artifacts/s2-fixtures")
    output_dir = args.output_dir or Path(default_output)
    actor = PromptedActor(full_history=args.strategy == "full_history", prompt_version=args.actor_prompt)
    if args.pilot:
        from .pilot import prepare_pilot, runtime_environment
        os.environ.update(runtime_environment())
        try:
            manifest = prepare_pilot(output_dir, configs[0], actor,
                                     model_config if args.backend == "transformers" else None,
                                     args.backend, selected_seeds)
        except (ValueError, KeyError, TypeError) as error:
            parser.error(str(error))
        if args.prepare_only:
            print(f"Pilot prepared: {output_dir / 'pilot-manifest.json'}")
            print(manifest["runtime"])
            return 0
    if args.backend == "transformers":
        from .transformers_model import TransformersModel
        model = TransformersModel(model_config)
    else:
        model = None  # Create a fresh script for each fixture episode.
    for config in configs:
        full_history = config.strategy == "full_history"
        memory = FullHistoryMemory() if full_history else FakeMemory(config.strategy)
        with CookingWorldEnvironment(recheck_cost=config.recheck_cost,
                                      action_budget=config.action_budget) as environment:
            result = run_episode(config, environment,
                                 actor,
                                 memory, model if model is not None else FakeModel(),
                                 output_dir=output_dir)
        print(f"{result['kind']}: seed={config.seed}; status={result['status']}; "
              f"termination={result['termination_reason']}; steps={result['steps']}; "
              f"budget_spent={result['budget_spent']}; recipe_rechecks={result['recipe_rechecks']}")
        print(f"Saved to {output_dir / result['episode_id']}")
        # A game loss is valid data. Stop on infrastructure errors so repeated
        # context/OOM errors do not waste the remaining diagnostic allocation.
        if result["status"] != "completed":
            print(f"Error: {result['error']}")
            return 1
    return 0


if __name__ == "__main__":
    # Runs only when launched as a script/module, not when another file imports it.
    raise SystemExit(main())
