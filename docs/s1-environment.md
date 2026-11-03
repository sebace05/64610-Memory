# S1: CookingWorld environment and cost wrapper

## Setup

Requirements: Python 3.10+ and a working Java runtime. Dependencies are pinned in
`requirements.txt`. No GPU or model access is needed for simulator checks.
Current Colab instructions and Java startup handling live in
[the checkpoint guide](qwen-checkpoint.md).

From the repository root:

```sh
java -version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m game_memory.pilot --output-dir artifacts/local-checks --check
```

The simulator starts a local Java process and communicates over local sockets.
Use the wrapper as a context manager so that the process is closed afterward.
The checks save their logs and dependency versions without loading model weights.
They do not establish model capability. The old S1 fixture generator has been
retired from the application; its
[complete source](https://github.com/sebace05/64610-Memory/blob/a7a2cd27b3967dbd1f989ea89df151881b6be0b6/game_memory/verify_s1.py)
and [original setup instructions](https://github.com/sebace05/64610-Memory/blob/a7a2cd27b3967dbd1f989ea89df151881b6be0b6/docs/s1-environment.md)
remain at their original revision. Existing traces and summaries are preserved.

## Public interface

```python
from game_memory import CookingWorldConfig, CookingWorldEnvironment

with CookingWorldEnvironment(recheck_cost=5, action_budget=80) as env:
    view = env.reset(seed=0, game_config=CookingWorldConfig())
    # Give view and bounded memory to the actor; never give it env internals.
    transition = env.step("examine cookbook")
    print(transition.action_cost)  # 5
    print(transition.view.budget_remaining)  # 75
```

`AgentView` contains only observation, goal, allowed actions, remaining budget,
and rechecking price. `Transition` additionally contains scoring and termination
fields for the runner/logger. Only `transition.view` belongs in action prompts.
The adapter never generates gold paths and never calls `getObjectTree()`.

Default engineering fixture: three locations, two recipe ingredients, no distractor
ingredients, no doors, unlimited inventory, and the train fold. This small setup
is for integration; research difficulty and memory demand still need Liam's pilot.
Seeds 0, 1, and 2 are development fixtures and must not become held-out instances.

## Cost and observation rules

- Reset performs one real `read cookbook` action for free, then returns the
  starting-room observation plus that initial recipe. No navigation, teleporting,
  or hidden solution is used. Reset fails if the cookbook is not accessible.
- Every later valid `read cookbook` **or `examine cookbook`** costs the chosen
  treatment price, 2 or 5. In TextWorldExpress 1.1.0 both reveal the full recipe.
- Other valid actions cost 1. Carrying the cookbook does not make later reads free.
- Action case and whitespace are normalized before matching actual allowed actions.
  Unsupported text, including `read recipe` and `help`, is an invalid action,
  costs 1, and does not execute or substitute an engine action. Formatting repair
  belongs in the actor/runner, not in this wrapper.
- An unaffordable action is not executed or charged; the episode ends with
  `budget_exhaustion`. This can leave a positive unused budget. The attempted action
  still counts in wrapper steps, but not in successful recipe rereads.
- Reaching zero budget after an action also ends the episode. Engine success or
  failure takes precedence if the final affordable action ends the game.
- `terminated` means engine success/failure; `truncated` means a wrapper budget
  or engine move limit ended the episode. `done` is true for either. Further actions
  require reset. Both normalized and raw game scores are retained without changing
  the engine's reward/scoring logic.
- No automatic look/inventory/recipe observations are added on later turns.
  The engine also supplies helper fields, but the wrapper does not expose those
  through `AgentView`. Allowed-action lists are sorted and retained; they expose
  ordinary available interactions and are not an exhaustive guarantee against cues.

## Verification and handoff

The historical verification script obtained a separate privileged diagnostic solution, added
an `examine cookbook` step, and replays the exact action sequence twice at price 2
and once at price 5. It verified successful completion, repeatability, matching
observations/actions/scores/termination, and a budget difference of exactly
`3 × charged recipe rereads`. The historical script used solution paths;
the wrapper explicitly resets with `generateGoldPath=False`.

Tests additionally cover invalid actions, both recipe access commands, book
pickup, budget exhaustion without engine execution, terminal failure, and success
on the last budget unit. `artifacts/s1/` contains environment-verification fixtures,
not model-evaluation results. Do not use its diagnostic actions as an agent policy.

Pablo and Liam can develop against the reset and step records in the JSONL traces
without launching Java. Colin can inspect scoring/cost fields, but the final
model-run result schema and batch persistence belong to S2/S3.

This task does not implement memory, inference, model-format repair, evaluation
statistics, or resumable experiment batches.

Upstream: <https://github.com/cognitiveailab/TextWorldExpress>.
