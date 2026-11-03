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

The `v2-mechanics` candidate was introduced on seed 0
for one targeted correction to the supplied v2 run. It prepends the verified rules
that ingredients must be carried together, putting them down removes them from
inventory, and preparation/eating occur through the available game commands.
The runner rejects this prompt if inventory capacity is limited. V2's remaining
instructions and repair feedback are identical. No locations of ingredients or
seed-specific action sequence is provided, and no action is forced or filtered.
Actual Qwen improvement from this primer is still unverified.

The subsequent v2-mechanics capability check selected one room/one ingredient.
This changed generated recipes as well as navigation, so it is a separate task
configuration from the earlier larger games. No Qwen success on it has been verified.

The supplied small-game ZIP now confirms episode `b2915faebfd34093b67938921d71fce9`:
`examine cookbook` → `open fridge` → `take chicken wing` →
`cook chicken wing in oven`. The oven roasts, but the retained recipe required
grilling. All four actions were legal; the last caused terminal failure at score
0.25 with 75 budget units remaining. There were no repairs or infrastructure errors.
The `v3` candidate only prepends generic appliance rules (stove fries, oven roasts,
toaster grills) and a warning about irreversible cooking mistakes to v2-mechanics.
It supplies no ingredient names or action sequence, and filters no legal actions.
Actual Qwen improvement remains unverified; the notebook selects one matched run.

The original model revision, FP16, greedy decoding, budget 80, and price 2 remain
fixed. Keep these non-policy
settings fixed when comparing prompt versions. The shared CLI records the policy choice in an immutable manifest and rejects
changed settings, duplicate seeds, and partial attempts before loading weights.

Use separate pilot directories for versions, keep the original run, and compare
matched development seeds 0–4. Start with one v2 episode and inspect it before
the additional four. The supplied v2 seed-0 run still fails; see the matched comparison below.
Use the remaining development seeds to assess whether the observed changes generalize.

Example after installing the optional inference dependencies:

```sh
.venv/bin/python -m game_memory.pilot --output-dir /path/to/persistent/mechanics-checkpoint \
  --backend transformers --strategy full_history --actor-prompt v2-mechanics \
  --model-revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --dtype float16 --seed 0 --recheck-cost 2 --action-budget 80
```

The real-model CLI still supports the full-history diagnostic only. Wiring P1
writers into the real bounded-memory CLI and running six conditions is a
subsequent milestone. Do not mix this actor-policy comparison with evidence for
memory-format effects or use held-out evaluation seeds during prompt development.

## Supplied seed-0 comparison

Both runs use the same Qwen revision, T4/FP16, greedy decoding, price 2, and budget
80. This is one matched development instance, not evidence of a general advantage.

| Measure | v1 | v2 |
| --- | --- | --- |
| Task success | No | No |
| Final score | 0.25 | 0.50 |
| Charged recipe rereads | 34 | 5 |
| Action repairs | 14 | 4 |
| Final invalid actions | 1 | 0 |
| Movement actions | 0 | 1 |
| Model calls | 60 | 79 |
| Input tokens | 87,811 | 135,804 |
| Episode seconds | 144.33 | 202.77 |

V2 reaches the pantry and takes flour, then puts it down repeatedly. It examines
the shelf 45 times, including 28 consecutive final actions. Water remains on the
kitchen counter. It never returns to the kitchen to prepare/eat the meal. All 75
primary requests retain the complete visible history; maximum input is 2,567
tokens, so this is not context truncation. A separate public-action replay can
recover from its step-30 state and finish in five more actions. That is a manual
mechanics check, not a model success or a policy to give the agent.

Reduced rereading alone is insufficient: v2 spends the saved budget on more
unsuccessful actions, increasing inference usage. Preserve these traces, assess
the remaining development seeds, and diagnose capability before the six-condition
memory experiment. The orchestration refactor changes neither actor prompt.

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
