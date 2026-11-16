# Eight-episode reproduction — November 15, 2026

The runtime is working and all eight development cells have been regenerated.
All four condition-level trace audits pass. Outcomes, action counts, rereads,
and input/output token totals match the table already in
[mvp-results.md](mvp-results.md). Historical raw traces were unavailable, so this
is a new replay matching those reported metrics, not a full historical trace
comparison.

The important qualification is now measured: **all 30 prose memory updates used
programmed fallback memory; none accepted the model's replacement notebook**.
JSON accepted model output for 34 of 36 updates. The reproduced 4/4 versus 0/4
success result compares unequal memory policies and cannot isolate format alone.

**Setup and fixed settings**

The saved setup check reports no broken dependencies, Java 17, and **313 tests
passed in 52.39 seconds**, exit status 0. GPU access works through WSL2 on the
RTX 5070 Ti. PyTorch is `2.8.0+cu128`; Transformers is `4.57.6`.

Every episode used commit `739e72def5ef65d8e0a8fd24d879cdc401de2066`, actor
`s2-action-v29`, writer `p1-memory-v16`, and Qwen 4B revision
`cdbee75f17c01a7cc42f958dc650907174af0554`. Settings were FP16, enforced greedy
decoding, generation seed 0, context 8192, action output limit 128, memory output
limit 512, rendered memory allowance 256, and action budget 80. The game had
one room, two ingredients, no distractors or doors, unlimited inventory, and
one free initial recipe. Prices were 2/5 and game seeds 0/1.

The train fold was selected explicitly, following the existing CLI default;
the historical manifests were unavailable to independently confirm their fold.
These are development instances, not held-out evaluation results. No experiment
code or prompts were changed during the replay. The source snapshot and digest
are saved; manifests truthfully record `worktree_dirty: true` because the initial
status report was untracked when execution started.

**Measured results**

| Memory | Price | Seed | Outcome | Actions | Rereads | Budget spent | Score | Input / output tokens | Model / episode seconds |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Prose | 2 | 0 | Success | 9 | 0 | 9 | 1.000 | 17,375 / 900 | 53.1 / 54.7 |
| Prose | 2 | 1 | Success | 6 | 0 | 6 | 1.000 | 12,164 / 588 | 33.4 / 34.1 |
| Prose | 5 | 0 | Success | 9 | 0 | 9 | 1.000 | 17,375 / 900 | 50.3 / 50.9 |
| Prose | 5 | 1 | Success | 6 | 0 | 6 | 1.000 | 12,164 / 588 | 32.6 / 33.0 |
| JSON | 2 | 0 | Terminal failure | 13 | 4 | 17 | 0.714 | 17,082 / 2,584 | 145.1 / 145.7 |
| JSON | 2 | 1 | Terminal failure | 5 | 0 | 5 | 0.400 | 5,920 / 964 | 54.5 / 54.9 |
| JSON | 5 | 0 | Terminal failure | 13 | 4 | 29 | 0.714 | 17,082 / 2,584 | 146.1 / 146.8 |
| JSON | 5 | 1 | Terminal failure | 5 | 0 | 5 | 0.400 | 5,920 / 964 | 54.9 / 55.3 |

All episodes have `status: completed`, complete inference usage, and normal game
termination. No episode exhausted its budget. Model/episode times include all
writer, repair, and review calls; episode time excludes model loading. Summed
generation time is 569.9 seconds and summed episode time is 575.4 seconds.
Those sums exclude loading, initial checkpoint download, and orchestration idle
time and are not total time spent on the reproduction.

**Memory behavior and validity**

| Memory | Updates across four games | Accepted model replacements | Programmed fallbacks | Maximum rendered tokens |
| --- | ---: | ---: | ---: | ---: |
| Prose | 30 | 0 | 30 | 115 |
| JSON | 36 | 34 | 2 | 122 |

Every prose primary and repair output was rejected with `recipe_dropped`. For
example, the initial writer returned only `Carried items: none` and
`Recipe progress: none complete`, omitting the recipe. Python supplied the
initial recipe and then maintained inventory and completed preparations through
public-evidence fallbacks. JSON's two fallbacks followed malformed JSON and
retained the previous state; its accepted states could contain factual errors.

Every saved memory was independently re-tokenized with the pinned Qwen tokenizer.
Recorded counts matched and all were within 256 tokens. Neither format reached
that allowance in this replay, which weakens the case that these games test
forgetting caused by a tight memory budget. A writer can still omit important
facts below the limit, so this does not establish that memory quality is adequate.

**Two trace annotations**

1. **Prose / price 2 / seed 0:** The agent opened the fridge, took and grilled
   the chicken, took the apple and knife, sliced and roasted the apple, prepared
   the meal, and ate it. It won in nine actions without rereading. At initialization
   (event sequence 6) and after every nonterminal action, both writer attempts
   were rejected and fallback memory was supplied. The success therefore cannot
   demonstrate that a model-written prose notebook worked better than JSON.
   [Raw trace](../artifacts/reproduction-v29-v16-20261115/prose-p2/a2b5f740d8db42e89ae00624371aa504/events.jsonl).
2. **JSON / price 2 / seed 0:** After four recipe rereads, the agent completed
   the ingredient preparations but chose `eat red apple` at action 13. The last
   accepted memory, after action 12 (event sequence 80), marked `prepare meal`
   true despite no such executed action. It also listed three `carried_items`
   while `inventory` held only the roasted apple, and retained a closed-fridge
   claim after opening it. This is direct evidence of accepted contradictory
   state and invented progress preceding the terminal choice, though the trace
   alone does not establish which erroneous field caused that choice.
   [Raw trace](../artifacts/reproduction-v29-v16-20261115/structured-p2/8b2b96c499f74115b86549c3be31d28d/events.jsonl).

The JSON seed-1 loss used the stove where grilling required the toaster. Prices
changed charged budget, but not outcomes, action counts, rereads, or token totals
within a format/seed. This replay does not establish a recovery-cost effect.

**Evidence and remaining work**

The [artifact directory](../artifacts/reproduction-v29-v16-20261115/) contains
raw events/results, four immutable manifests and checkpoint reports, launch
logs, the source archive/checksum, dependency freeze, and the offline analysis
script. [Machine-readable summary](../artifacts/reproduction-v29-v16-20261115/summary.json)
and [CSV](../artifacts/reproduction-v29-v16-20261115/summary.csv) record all cells.
The [ZIP package](../artifacts/reproduction-v29-v16-20261115.zip) contains the
evidence without model weights. Artifacts remain ignored by Git; retain the ZIP
in durable shared storage rather than expecting a code pull to transfer it.

One launch log, prose / price 2 / seed 1, lacks the launcher's exit-status footer
and its tool session was no longer retrievable. Its episode result and terminal
trace are complete and pass audit, but the underlying launcher exit status is
unknown. That limitation is recorded explicitly in `summary.json`; no exit
status was invented and the completed gameplay was not rerun to replace it.
The other four launch logs record exit status 0.

The setup, evidence-regeneration, and episode-audit tasks are now complete,
subject to that launch-status limitation. **The remaining P0 research task is
fairness:** define equivalent semantic validation and fallback assistance across
formats, and verify that intended model-written memory is actually used. Any
change needs new versions and a separate development grid. Keep this replay as
the preserved baseline. Reassess memory pressure on development data before
freezing a larger experiment. Hybrid and the 120-game evaluation remain deferred.
