# S2: episode runner and integration handoff

## Current milestone

The episode runner connects the real S1 environment to interchangeable actor,
model, and memory interfaces. The included model/memory components are explicitly
fake integration fixtures. S2's real-model acceptance criterion remains open until
L1 and P1 are connected and a real-model episode is saved.

No model weights, API access, GPU, or additional packages are needed for this stage.
Use the existing S1 environment and dependencies, including Java.

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m game_memory.run_episode --backend fake --strategy prose \
  --recheck-cost 2 --action-budget 6 --seed 0
.venv/bin/python -m game_memory.run_episode --backend fake --strategy hybrid \
  --recheck-cost 5 --action-budget 6 --seed 0
```

Each invocation creates a new directory under `artifacts/s2-fixtures/`, containing
`events.jsonl` and `result.json`. The fake model first requests `examine cookbook`
and then `look around` repeatedly. The game ends by budget exhaustion. This proves
the wiring and cost flow, not gameplay capability or comparative memory quality.
The fake tokenizer counts whitespace words; its usage numbers are not Qwen tokens.
All artifacts involving any fake or unmarked component are labeled
`kind: integration_fixture`, including scripted successes.

## Verification status

The complete S1/S2 suite passes: 32 tests. On the local machine, pytest plugin
metadata discovery was slow; verification used built-in plugins only:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

Saved CLI examples are indexed in `artifacts/s2-fixtures/README.md`.

## Components

- `components.py`: `Generation`, `Message`, `MemoryContext`, `MemoryUpdate`, and
  small model/memory/actor protocols for independent implementations.
- `actor.py`: fresh action prompt per turn and one permitted JSON/action repair.
- `runner.py`: initialization, turn loop, token guard, exact request/response
  tracing, usage accounting, and result records.
- `integration_fixtures.py`: fake model and fake prose/JSON/hybrid placeholders.
  These are not Pablo's research memory implementations.
- `run_episode.py`: CLI for fake integration runs and an explicit real-Transformers
  full-history diagnostic. See [the Qwen checkpoint](qwen-checkpoint.md). Real
  bounded-memory components remain pending; the CLI rejects a real-model run
  with placeholder research memory.

## Turn order and isolation

1. Reset the environment and receive the standardized free initial recipe.
2. Initialize empty memory and perform one memory write from that initial view.
3. Render and count the complete bounded memory. The actor sees the latest
   AgentView and that memory only; it does not receive the environment or logger.
4. Generate an action, optionally repair it once with the same turn's evidence,
   then pass it to the S1 wrapper. Invalid outputs remain invalid budgeted actions.
5. Log the transition. On nonterminal actions, update memory from its previous
   serialized state, the action, the new observation, and public task context.
6. Repeat until success, terminal failure, or budget exhaustion; then save a result.

No memory write runs after the final action because there is no later decision.
The initial write and every nonterminal write are counted. This implementation
choice is recorded in each trace header and must remain the same across formats.
Token overflow returned by a memory module is a component-contract error; real
memory modules must implement their own one-repair/previous-valid-state fallback
and report its events. No oversized memory is passed to the actor.

The actor embeds rendered memory literally rather than JSON-escaping it again.
Consequently the memory guard counts the actual memory text shown in the prompt,
including its internal punctuation/separators. Fixed prompt headers, the current
observation, and allowed actions are outside the stored-memory allowance.
Do not implement a backend that silently retains a chat from previous turns;
`generate()` must use only its supplied messages.

## Handoff to Liam and Pablo

Liam's model implements `generate(messages, purpose=...)`, `count_tokens(text)`,
and JSON-compatible `metadata`. Use the real tokenizer for `count_tokens` without
adding chat-template special tokens. Generation includes actual input/output
tokens and elapsed seconds. Metadata should identify model/tokenizer revisions,
precision, decoding settings, and `is_fake: False`. Both acting and memory writing
receive the same logged model adapter, which records repair calls too.

Pablo's memory implements `empty()`, `update(...)`, `render()`, and metadata with
the matching strategy name, implementation version, and `is_fake: False`.
Memory state crosses the interface as serialized text; implementations may parse
it into objects internally. Hybrid must render its combined state within one
allowance. Return `MemoryUpdate(memory=..., events=(...))` after handling any
malformed/over-budget model output. The logger and environment are not passed in.

```python
from pathlib import Path
from game_memory.actor import PromptedActor
from game_memory.environment import CookingWorldEnvironment
from game_memory.runner import EpisodeConfig, run_episode

# Supply Liam's model and Pablo's strategy as model and memory.
config = EpisodeConfig(strategy="prose", recheck_cost=2)
with CookingWorldEnvironment(recheck_cost=config.recheck_cost,
                              action_budget=config.action_budget) as env:
    result = run_episode(config, env, PromptedActor(), memory, model,
                         output_dir=Path("artifacts/development"))
```

## Results and error handling

`status: completed` means valid gameplay reached an ending, not necessarily success.
Use `success`, `failure`, and `termination_reason` to interpret the outcome.
Component exceptions produce `status: error`, `success: null`, and a phase/error
record, rather than silently becoming game losses. A failed model request also
sets `usage_complete: false`; known token totals then exclude unknown usage.

Each trace contains configuration and component identity, initial view, exact
model messages/responses, memory before/after, action transitions, validation
events, and terminal results. Token usage is aggregated over all completed model
calls, with totals by purpose. Score, budget units, inference usage, and runtime
remain separate. `result.json` is published after the trace closes.

The caller owns and closes the environment. Each invocation gets a fresh episode
ID so existing results are not overwritten. An interrupted invocation may leave
an incomplete trace without a result; batch scheduling and resume are S3.

## Remaining S2 acceptance work

- Connect the real candidate model and real bounded-memory implementation.
- Record exact model/precision/generation settings and a real-model trace.
- Confirm a valid ending with complete logs; success is not required to prove
  integration, but capability must be evaluated separately in L2.
- Keep fixture artifacts out of model evaluation and reserve held-out seeds.
