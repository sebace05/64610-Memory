# Episode runner reference

For current status and Colab instructions, use [the checkpoint guide](qwen-checkpoint.md).
This page describes the runner contract; it is not a separate implementation plan.

## Turn order

1. Reset the real simulator and receive the standardized free initial recipe.
2. Initialize empty memory and write from the initial public observation.
3. Render memory and count its exact actor-visible tokens.
4. Ask the actor for one action, allowing one repair using the same evidence.
5. Execute and log the action. Invalid output remains a budgeted failed attempt.
6. Update memory after nonterminal actions, then repeat until the game ends.

No writer runs after the terminal action. Initialization, acting, writing, and
repairs all contribute to inference accounting. Bounded strategies receive only
the current public view and their stored memory. Full-history diagnostics are
explicitly separate and exempt from the bounded-memory allowance. Scoring,
logger records, and hidden simulator state never enter agent inputs.

## Interfaces and ownership

[components.py](../game_memory/components.py) defines the small model, memory,
and actor protocols. [contracts.py](../game_memory/contracts.py) defines public
views, game settings, and transitions. [runner.py](../game_memory/runner.py)
connects them. The caller owns and closes the environment.

```python
from pathlib import Path
from game_memory.actor import PromptedActor
from game_memory.environment import CookingWorldEnvironment
from game_memory.runner import EpisodeConfig, run_episode

# Supply a real model and memory strategy implementing components.py.
config = EpisodeConfig(strategy="prose", recheck_cost=2)
with CookingWorldEnvironment(recheck_cost=config.recheck_cost,
                              action_budget=config.action_budget) as env:
    result = run_episode(config, env, PromptedActor(), memory, model,
                         output_dir=Path("artifacts/development"))
```

## Results and fixtures

Every attempt gets a new episode directory. `events.jsonl` records exact model
requests/responses, observations, memory changes, actions, accounting, identities,
and errors. `result.json` is published after the trace closes. Interrupted runs
may retain partial traces; the pilot guards preserve them and reject reuse.

`status: completed` means valid gameplay ended; inspect `success` and
`termination_reason` separately. Infrastructure errors have `status: error` and
`success: null`. Failed model calls set `usage_complete: false`, preserving known
usage without inventing totals. Fake or unmarked components label the entire
run `integration_fixture`; their usage cannot estimate Qwen cost or capability.

```sh
.venv/bin/python -m game_memory.run_episode --backend fake --strategy prose \
  --recheck-cost 2 --action-budget 6 --seed 0
```

This optional wiring check saves locally under `artifacts/s2-fixtures/`.
[Committed examples](../artifacts/s2-fixtures/README.md) remain preserved.
Real bounded-memory CLI integration is pending; fake runs do not satisfy it.
