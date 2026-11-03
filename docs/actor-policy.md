# Actor policy revisions and failure analysis

## Why v2 exists

Development episode `4168f196f79e4a5db196c993cc071686` used
`Qwen/Qwen3-4B-Instruct-2507` revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, FP16 on a Tesla T4, greedy decoding,
seed 0, budget 80, and reread price 2. It reached score 0.25 after taking water,
put that water down, never moved to another room, and spent 68 budget units on
34 identical recipe rereads. It ended with one budget unit left when another
two-unit reread was attempted.

All 60 generated responses were valid JSON. Fourteen original responses requested
unavailable `take flour`; thirteen repairs selected a legal alternative, mostly
another cookbook examination, while one repair repeated the unavailable action.
The complete visible history was retained. The largest prompt was 2,396 tokens,
below the 8,192-token limit. These findings motivate gameplay/availability
instructions rather than a JSON-only formatting change or a larger context.

A separate manually scripted public-action mechanics check completed the same
game in seven charged actions. That verifies feasibility, not Qwen capability;
the seed-specific action sequence is not included in either actor prompt.

## Choosing a policy

`PromptedActor(prompt_version="v1")` and `--actor-prompt v1` retain the original
system instructions and generic repair feedback. This remains the API/CLI
default so existing experiments are not silently changed.

`PromptedActor(prompt_version="v2")` and `--actor-prompt v2` add:

- The objective of gathering ingredients, following directions, preparing, and
  eating the meal.
- Current-location and carried-item tracking from supplied evidence, including
  the consequence of putting down required ingredients.
- Exact current-action selection and exploration/prerequisite steps when a
  desired ingredient cannot currently be taken.
- Conditional recipe recovery when information is missing or uncertain, plus
  the distinction between another identical observation and task progress.
- Budget awareness using the already-public remaining budget and action prices.
- Separate repair feedback for malformed JSON, a missing/nonstring action field,
  and an unavailable command.

All instructions are generic. The substantive v2 policy is shared between
full-history and bounded-memory modes; only the supplied context label differs.
Prose/structured/hybrid writers are unchanged. No hidden plan, live helper calls,
score fields, seed-specific locations, or inventory oracle is added to the actor.
Only supplied memory/history carries information between turns.

The one-repair maximum, exact-action validation, failure charging, available
actions, and environment termination rules are unchanged. The actor does not
filter unaffordable actions, ban rereads, replace actions, or stop loops in code.
Such choices remain model behavior to measure. Actor metadata records the prompt
version (`s2-action-v2` or `full-history-v2`), and exact requests remain in the log.

## Rerunning the development comparison

The Colab launcher explicitly defaults to `ACTOR_PROMPT = "v2"`, the original
model revision, FP16, greedy decoding, budget 80, and price 2. Keep these non-policy
settings fixed when comparing v1/v2. The launcher records the policy choice in
the manifest and refuses mixed settings, existing completed seeds, and partial
attempts in a single pilot directory.

Use separate pilot directories for versions, keep the original run, and compare
matched development seeds 0–4. Start with one v2 episode and inspect it before
the additional four. Do not assume improvement from these code changes: the
implementation was tested with scripted inference and tiny random local Qwen3
weights; actual production-Qwen improvement requires the Colab run.

Example after installing the optional inference dependencies:

```sh
.venv/bin/python -m game_memory.run_episode \
  --backend transformers --strategy full_history --actor-prompt v2 \
  --model-revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --dtype float16 --seed 0 --recheck-cost 2 --action-budget 80 \
  --output-dir /path/to/persistent/actor-v2-pilot
```

The real-model CLI still supports the full-history diagnostic only. Wiring P1
writers into the real bounded-memory CLI and running six conditions is a
subsequent milestone. Do not mix this actor-policy comparison with evidence for
memory-format effects or use held-out evaluation seeds during prompt development.

## Offline inspection

From the repository root:

```sh
.venv/bin/python -m game_memory.inspect_episode /path/to/events.jsonl \
  --csv /path/to/actions.csv

.venv/bin/python -m game_memory.inspect_episode /path/to/events.jsonl \
  --step 13 --show-prompts
```

Inspection reads the saved trace; it does not start Java, load weights, execute
actions, or change the raw trace/results. CSV output must use a `.csv` filename.
The notebook saves `actions.csv` and `trace-analysis.json` beside the episode.

The analysis separates primary/repair syntax, schema, and availability outcomes
using the public view available at generation time. Missing view/response data
is labeled unknown/missing rather than declared valid. It also reports selected
action frequencies, movement attempts, charged reread budget, distinct reread
observations, and recorded take/put/inventory commands with their observations.

The longest same-action streak counts final selected attempts, including a last
unaffordable attempt; executions are reported separately. The longest score
plateau counts attempts without a new best observed score, starting at zero.
Useful exploration can occur during a score plateau, and score may remain high
after an ingredient is put down. Inventory-command records are not an inferred
inventory. Interpret these diagnostics with the actual observations; they are
not policy feedback and never stop or steer the game.

The full-history checkpoint auditor includes these behavioral metrics while
retaining its independent accounting checks. It rejects mixed configurations;
summarize v1/v2 pilots separately before comparing matched results. Capability
and scientific interpretation remain separate from logging/infrastructure pass
flags.
