"""CLI for a real CookingWorld game with explicitly fake integration components."""

import argparse
from pathlib import Path

from .actor import PromptedActor
from .environment import CookingWorldEnvironment
from .integration_fixtures import FakeMemory, FakeModel
from .runner import EpisodeConfig, run_episode


def main() -> int:
    # Read launch options, not saved JSON artifacts. Example:
    # python -m game_memory.run_episode --strategy hybrid --recheck-cost 5
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["fake"], default="fake")
    parser.add_argument("--strategy", choices=["prose", "structured", "hybrid"], default="prose")
    parser.add_argument("--recheck-cost", type=int, choices=[2, 5], default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--action-budget", type=int, default=6)
    parser.add_argument("--memory-token-limit", type=int, default=256)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/s2-fixtures"))
    args = parser.parse_args()
    # Freeze one episode's settings before constructing the matching components.
    config = EpisodeConfig(seed=args.seed, strategy=args.strategy,
                           recheck_cost=args.recheck_cost, action_budget=args.action_budget,
                           memory_token_limit=args.memory_token_limit)
    # The game is real; the model and memory below are explicitly fake. Replace
    # these through the documented runner interfaces when L1/P1 are available.
    # The context manager closes the Java process on normal exit or exceptions.
    with CookingWorldEnvironment(recheck_cost=config.recheck_cost,
                                  action_budget=config.action_budget) as environment:
        result = run_episode(config, environment, PromptedActor(), FakeMemory(args.strategy),
                             FakeModel(), output_dir=args.output_dir)
    print(f"INTEGRATION FIXTURE: fake model/memory; status={result['status']}; "
          f"termination={result['termination_reason']}; steps={result['steps']}; "
          f"budget_spent={result['budget_spent']}; recipe_rechecks={result['recipe_rechecks']}")
    print(f"Saved to {args.output_dir / result['episode_id']}")
    # Shell success means the run finished correctly, even if the agent lost.
    # Component/infrastructure errors return a nonzero exit status instead.
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    # Runs only when launched as a script/module, not when another file imports it.
    raise SystemExit(main())
