# Local checkpoint results: Qwen 4B on RTX 5070 Ti

These are development diagnostics, not the prose-versus-JSON comparison. Runs
used `Qwen/Qwen3-4B-Instruct-2507` at revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, FP16, enforced greedy decoding,
one location, two ingredients, an 80-action budget, and prompt v11 for the
paired successful full-history checks. Each artifact directory contains its
immutable manifest, raw trace, launch log, and checkpoint report. Earlier prompt
versions and interrupted attempts remain in their own artifact directories.

## Gameplay readiness

| Condition | Seed | Outcome | Actions | Budget | Recipe rereads | Repairs | Input / output tokens | Model time | Episode time |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full history, v11 | 0 | Success | 12 | 13/80 | 1 | 1 | 19,358 / 118 | 8.75 s | 10.35 s |
| Full history, v11 | 1 | Success | 8 | 9/80 | 1 | 0 | 11,072 / 70 | 5.42 s | 7.32 s |

The seeds produced different recipes: chicken wing with red apple for seed 0,
and chicken wing with salt for seed 1. Both traces reached `prepare meal` and
`eat meal`. This supports proceeding to a bounded-memory pilot, but does not
establish that bounded memory is viable or that the two memory strategies differ.

## Trace annotations

**Successful seed 0, v11.** The model opened the fridge, gathered the chicken
wing and red apple, took the knife, sliced and roasted the apple, grilled the
chicken in the toaster, then prepared and ate the meal. It used one repair and
one recipe reread, with no repeated action. The directions in this generated
recipe listed grilling the chicken before preparing the apple; the trace
completed both preparations and succeeded, but did not follow their global
listed order. This is a remaining planning weakness even in a successful run.

**Bounded-memory prose, seed 0.** The first pilot (v11) repeated `examine
cookbook` while its writer memory already contained the complete recipe. The
next attempt (v12) still reread it; v13 reduced that behavior but alternated
`examine knife` and `examine cookbook` without taking the knife. Each attempt
was interrupted after the repeated inspection loop became clear. These are
incomplete diagnostics and do not count toward the eight-episode MVP. A later
v13 run with the guard completed nine game actions, then stopped with
`actor_guard_failure` after four repair calls and one repeated-repair rejection.
It used 24,877 input tokens, 1,900 output tokens, and 115.75 seconds end to end;
the independent trace audit passes. The model opened containers and gathered the
chicken, but did not complete the recipe. Its files are in
`artifacts/mvp-v13-prose-price2-seed0-guard-stop/`. The earlier partial traces
and interruption logs are in
`artifacts/mvp-v11-prose-price2-seed0/`,
`artifacts/mvp-v12-prose-price2-seed0/`, and
`artifacts/mvp-v13-prose-price2-seed0/`.

## Historical bounded pilots

Earlier development runs stopped at `actor_guard_failure` after one failed
inspection repair. This was too strict for measuring model gameplay. Their raw
artifacts are preserved, but they are excluded from the eight-condition table
below. The subsequent runs let legal repeated inspections consume the normal
game budget. The full test suite passes (284 tests).

## Completed eight-condition development MVP (natural gameplay)

Real Qwen 4B on RTX 5070 Ti, actor prompt v11, memory prompt v11, 256-token
actor-visible memory, one room and two ingredients. All eight traces passed the
independent logging/accounting audit. All ended in normal budget exhaustion with
no game success; a loss is a measured outcome, not an infrastructure failure.
Earlier actor-guard pilot artifacts remain separate.

| Memory | Reread price | Seed | Actions | Rereads | Budget | Actor tokens | Writer tokens | Input/output tokens | Model seconds | Episode seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| prose | 2 | 0 | 43 | 37 | 80/80 | 52,943 | 36,686 | 86,309/3,320 | 204.9 | 206.0 |
| prose | 2 | 1 | 43 | 37 | 79/80 | 51,688 | 34,984 | 83,140/3,532 | 216.8 | 218.0 |
| prose | 5 | 0 | 21 | 14 | 76/80 | 25,599 | 21,222 | 45,195/1,626 | 100.4 | 102.2 |
| prose | 5 | 1 | 20 | 15 | 80/80 | 23,839 | 18,796 | 41,035/1,600 | 98.8 | 100.5 |
| structured | 2 | 0 | 42 | 38 | 79/80 | 52,675 | 38,471 | 82,292/8,854 | 539.2 | 541.0 |
| structured | 2 | 1 | 41 | 39 | 80/80 | 51,470 | 37,763 | 80,648/8,585 | 513.8 | 515.9 |
| structured | 5 | 0 | 19 | 15 | 78/80 | 23,618 | 16,894 | 36,834/3,678 | 219.1 | 221.1 |
| structured | 5 | 1 | 18 | 15 | 77/80 | 22,586 | 16,521 | 35,346/3,761 | 228.3 | 230.0 |

Token columns count all generation and repair calls. Episode time excludes model
loading; each episode used a separate process. The eight runs are too small to
claim one memory format is better. The main observed limitation is repeated
cookbook inspection, and structured writing used substantially more generated
tokens and model time in these runs.

**Trace annotation, prose / price 2 / seed 0.** Qwen opened the fridge, took
the chicken wing, and later took the red apple. Its initial bounded memory
contained the complete recipe. Starting at action 11, it repeatedly chose
`examine cookbook`; the game charged each reread until budget exhaustion at
action 43 (37 rereads overall). This is recorded model behavior, not a guard
termination. Artifact: `artifacts/mvp-natural-v11-prose-p2-s0/`.

**Trace annotation, structured / price 2 / seed 0.** Qwen read the cookbook,
opened the fridge, and took the chicken wing, then repeatedly examined the
cookbook through action 42 (38 rereads overall). The initial JSON memory also
incorrectly described closed containers as open and marked the red apple's
ingredient status true before a take. This is a writer grounding error visible
in the raw trace, not an environment action. Artifact:
`artifacts/mvp-natural-v11-structured-p2-s0/`.

## Root-cause follow-up: prose fallback and sustained rereads

The price-2 seed-0 prose trace exposed a real memory bug at action 10. When a
writer placed the recipe after `Latest action:`, the public-evidence fallback
removed that line and everything following it, including the recipe. Qwen then
saw only inventory and a knife observation, making action 11's cookbook reread
reasonable. The fallback now removes only the superseded evidence lines; the
change is versioned as memory v12 and has a regression test.

A fresh v12 seed-0 replay kept the recipe at action 10 but still exhausted the
budget after 48 actions and 32 rereads. Its audit passed. This shows the recipe
loss contributed to the first reread but does not explain the sustained loop.
From action 12 onward the actor repeatedly selected the cookbook while the
recipe was present and `cook chicken wing in toaster` was legal. The actor's
fresh per-turn prompt has no action history beyond bounded memory, and repeated
recipe observations feed back into that memory. This is an observed model/prompt
feedback loop, not an environment execution error. The v12 replay is a separate
development diagnostic and is not mixed into the eight-condition v11 table.

## Goal-first actor prompt v17 pilot

A new actor prompt put the goal and next unfinished recipe direction first,
without inserting a seed-specific next action or filtering legal actions. On a
replay of the recorded action-11 request, Qwen still selected `examine
cookbook`. The complete real-Qwen seed-0 prose / price-2 / memory-v12 pilot
ended at budget exhaustion: 44 actions, 36 rereads, 80/80 budget, 56,563 input
tokens, 3,423 output tokens, 220.2 seconds of model generation, and 221.5
seconds end to end. Its independent trace audit passed. It opened the fridge
first and gathered both ingredients, then repeatedly examined the cookbook.
The comparable actor-v11 / memory-v12 development replay had 48 actions, 32
rereads, 122,199 input tokens, and 236.3 seconds end to end. Prompt v17 cut
input tokens but did not solve the loop. These are separate development pilots;
the fixed eight-condition v11 table above is unchanged. Artifact:
`artifacts/mvp-v17-memory-v12-prose-p2-s0/`.

## Two-part actor prompt v18 pilot

The actor was asked to output both its first unfinished recipe direction and
one exact available action. The prompt included only general CookingWorld
appliance rules (grill/toaster, roast/oven, fry/stove). In a replay of the v17
loop decision with both ingredients carried, Qwen chose `cook chicken wing in
toaster`. In the complete real-Qwen seed-0 prose / price-2 / memory-v12 pilot,
it identified `grill the chicken wing` but chose `examine toaster` on every one
of 80 actions, before gathering the chicken wing. The game ended at normal
budget exhaustion: 80 actions, 0 recipe rereads, 77,271 input tokens, 7,840
output tokens, 469.1 model seconds, and 470.3 episode seconds. The independent
trace audit passed. This is a separate development pilot, not part of the
fixed eight-condition v11 table. Artifact:
`artifacts/mvp-v18-memory-v12-prose-p2-s0/`.

## Immediate-repeat exclusion and reasoned-action diagnostics

Actor v19 excludes the previous accepted action from the next turn's offered
list and validates against that reduced list. A partial real-Qwen run recorded
51 actions with no identical neighbors; Qwen alternated `examine toaster` and
`examine oven`. That run was interrupted after the behavior was established,
and its partial raw trace is preserved under
`artifacts/mvp-v19-memory-v12-prose-p2-s0/`.

Actor v21 also requires a nonempty one-sentence `reason` in every model action
response; the reason and `next_direction` remain in the raw model trace, while
only its legal `action` is sent to the game. The repair prompt requests all
three fields. A separate seed-0, price-2, 20-budget diagnostic completed with
20 actions, zero recipe rereads, and normal budget exhaustion. Qwen explained
that it needed to inspect the toaster to understand how to grill, then cycled
through toaster, oven, and stove inspections without gathering the chicken.
Four excluded repeated-toaster outputs were rejected and charged as invalid
action attempts; no identical accepted actions were consecutive. The
independent trace audit passed. This short diagnostic does not replace the
80-budget MVP results. Artifact:
`artifacts/mvp-v21-reasons-prose-p2-s0-budget20/`.

## Model-reviewed action pilot (actor v28, memory v14)

The v24 prose actor and v14 memory completed seed 0 in nine actions, but on
seed 1 Qwen proposed `prepare meal` while salt was not carried. Its generic
invalid-action repair chose `examine toaster` and began an inspection loop.
The recipe and `Carried items: chicken wing` were present in the actor input.
Prompt-only v25 and v26 diagnostics fixed one seed while regressing the other;
v27 used a model ingredient review but still repaired an unavailable repeated
grill command into an inspection. These attempts remain separate artifacts.

Actor v28 retains v24's ordinary action prompt and the unrestricted legal
action list. When Qwen proposes `prepare meal`, a second Qwen call checks the
public recipe against carried items. When Qwen proposes an unavailable action,
its repair call checks recipe progress before choosing another allowed action.
The code validates the returned command but does not substitute a scripted
action or prohibit repeated inspections. Both calls and their raw outputs are
recorded and charged to inference usage.

| Prose, price 2 | Result | Actions | Rereads | Input / output tokens | Model / episode seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| Seed 0 | success | 9 | 0 | 16,711 / 875 | 51.7 / 52.2 |
| Seed 1 | success | 6 | 0 | 11,642 / 580 | 35.8 / 37.5 |

Both traces passed the independent logging and isolation audit in
`artifacts/mvp-v28-memory-v14-prose-p2-seeds01/checkpoint-report.json`.
Seed 1 followed open fridge, take chicken wing, grill, take salt, prepare
meal, eat meal. Its action log includes one ingredient review that replaced
the premature `prepare meal`, and one progress-aware repair after an
unavailable repeated grill command. Seed 0 followed its required slice and
roast directions before preparing and eating. The full suite passed with
304 tests.

A structured-memory v28 / price-2 / seed-1 exploratory run was stopped after
seven actions when Qwen moved from an unavailable repeated grill command to
inventory, cookbook, and toaster inspections. Its partial trace is preserved
under `artifacts/mvp-v28-memory-v14-structured-p2-seeds01/`; it is not a
completed result or evidence of a strategy effect. The JSON memory retained
`carried_items` and `recipe_status`, but Qwen still failed to choose a useful
action. Do not fold this partial run into the fixed eight-condition v11 table.

The [DSSR paper](https://arxiv.org/html/2609.32805v2) is relevant to a later
memory analysis: it separates missing decision-relevant state from a reader's
failure to use available state, and uses a frozen, trained reader to compare
memory formats. Our observed seed-1 prose failure had the needed facts in
memory, so it is evidence of reader/action-selection error at that decision.
The paper's reported success rates do not transfer directly to this untrained
actor or to these two small development seeds.

## Format-neutral actor and public-evidence memory replay (v29/v16)

The v28 review text referred to prose `Ingredients` and `Carried items` labels.
The JSON writer instead used keys such as `recipe_status.ingredients` and
`carried_items`, so v29 asks the same Qwen reviewer to identify required
ingredients and currently carried items in either representation. It still
does not remove legal actions or substitute a coded choice. A partial v29/v14
JSON trace then showed a confirmed `prepare meal` observation followed by a
writer output that still said `prepare meal: false` and listed the original
ingredients as carried. Memory v16 rejects that stale public state and, if
both writer attempts fail, preserves the confirmed meal in a compact JSON
state. The fallback records facts from the executed action and observation;
it contains no next action or hidden game state.

The eight-cell development replay used one pinned Qwen checkpoint, actor v29,
memory v16, two recipe seeds, and the same 80-action budget throughout. Each
cell has its own immutable manifest and raw trace. All eight independent trace
audits passed, with no infrastructure errors, budget exhaustion, or adjacent
repetition of the same action.

| Memory | Price | Seed | Outcome | Actions | Rereads | Input / output tokens | Model / episode seconds |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Prose | 2 | 0 | success | 9 | 0 | 17,375 / 900 | 53.2 / 53.7 |
| Prose | 2 | 1 | success | 6 | 0 | 12,164 / 588 | 36.5 / 38.1 |
| Prose | 5 | 0 | success | 9 | 0 | 17,375 / 900 | 53.6 / 54.1 |
| Prose | 5 | 1 | success | 6 | 0 | 12,164 / 588 | 36.8 / 38.3 |
| JSON | 2 | 0 | terminal failure | 13 | 4 | 17,082 / 2,584 | 152.3 / 152.9 |
| JSON | 2 | 1 | terminal failure | 5 | 0 | 5,920 / 964 | 58.0 / 59.7 |
| JSON | 5 | 0 | terminal failure | 13 | 4 | 17,082 / 2,584 | 152.4 / 152.9 |
| JSON | 5 | 1 | terminal failure | 5 | 0 | 5,920 / 964 | 57.2 / 57.7 |

**Trace annotation, prose / price 2 / seed 1.** Qwen opened the fridge, took
and grilled the chicken wing, then proposed `prepare meal` without carrying
salt. The model review selected `take salt`. On the next turn Qwen proposed an
unavailable repeated grill command; its model repair recognized the completed
grill step and selected `prepare meal`, after which Qwen ate the meal. This
run succeeded in six actions and made no recipe rereads. Trace and audit:
`artifacts/mvp-v29-memory-v16-prose-p2-seeds01/`.

**Trace annotation, JSON / price 2 / seed 0.** Qwen reread or examined the
cookbook four times, but between those actions it gathered the apple, sliced
and roasted it, found the chicken, and grilled it. It then chose `eat red
apple`, a terminal game loss. The JSON memory exposed conflicting `inventory`
and `carried_items` fields during this run. This is a memory/reader failure to
study, not evidence that the simulator blocked progress or that the actor
prevented repeats. Trace and audit:
`artifacts/mvp-v29-memory-v16-structured-p2-seeds01/`.

The price-5 artifacts are in matching `...-p5-seeds01/` directories. The
price difference changes the budget cost of rereads, so the JSON seed-0 run
spent 17 budget units at price 2 and 29 at price 5 despite the same 13 game
actions. This small development grid establishes the absence of the previous
budget-exhaustion loop in these eight runs. It does not establish a general
success rate or prove the actor cannot loop on another recipe. The full suite
passed with 309 tests.
