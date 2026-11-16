# Experiment status and remaining work — November 15, 2026

**Follow-up:** The runtime has since been configured, all 313 tests passed, and
the eight development episodes were regenerated and audited. See the
[reproduction report](reproduction-2026-11-15.md) for the current evidence and
remaining fairness issue. The assessment below preserves the initial review,
before that setup and replay.

Reviewed revision: `739e72def5ef65d8e0a8fd24d879cdc401de2066` (`main`),
“Add memory comparison pilots and evaluation protocol.” The working tree was
clean when this review began. This report inspects the local code, documentation,
notebook settings, and available artifacts. It does not launch GPU experiments.

**Current assessment**

The project has an implemented experiment pipeline and a documented, completed
eight-episode development pilot. The latest reported pilot has useful gameplay:
prose succeeds in all four cells, while structured JSON loses all four. This is
enough for a descriptive development milestone, subject to recovering and checking
the underlying evidence. It is not yet a defensible general conclusion about
memory format or the effect of recovery cost.

The immediate work is evidence recovery, verification, and clarifying the
comparison. Another large evaluation is premature. The active scope in
[AGENTS.md](../AGENTS.md) remains two memory formats × two reread costs × two
development seeds, one table, and two annotated traces. Hybrid and the 120-game
study remain deferred even though their implementation and protocol now exist.

**Research question and experiment**

The question is whether the cost of recovering forgotten recipe information changes
the relative performance of prose and structured JSON memory in CookingWorld.
“Price” means simulated action-budget units, not money or inference tokens.

The latest documented development comparison uses:

- `Qwen/Qwen3-4B-Instruct-2507`, revision
  `cdbee75f17c01a7cc42f958dc650907174af0554`, on RTX 5070 Ti, FP16,
  with corrected greedy decoding.
- One room, two ingredients, an 80-unit action budget, and seeds 0 and 1.
- One free initial recipe; subsequent cookbook reads/examinations cost 2 or 5.
- A shared 256-token actor-visible memory allowance, using the Qwen tokenizer.
- Actor `s2-action-v29` and memory writer `p1-memory-v16`.

These are the settings reported in [the results](mvp-results.md), not settings
independently recovered from real-model manifests in this checkout.

**What has been developed**

| Component | Current implementation | Evidence limit |
| --- | --- | --- |
| Environment | Real TextWorldExpress/Java simulator; public observations; explicit reread costs, budget accounting, and termination. | Saved S1 artifacts verify environment behavior, not Qwen capability. |
| Episode runner | Initializes memory, executes actions, updates memory, records raw model calls, results, errors, tokens, and time. Fixtures, development, full-history diagnostics, and test-fold evaluation have separate labels. | Accounting and isolation still need checking against the actual pilot traces. |
| Qwen adapter | Pinned model revision, tokenizer-based counts, configurable output/context limits, and explicit greedy decoding that disables inherited checkpoint sampling defaults. | Historical runs before the decoding correction must remain separate. |
| Actor | Versioned prompts through v29; model-based ingredient review before meal preparation and progress-aware repair for unavailable proposals. v29 leaves legal repeats available. | Review/repair calls are part of the policy and inference cost; they must remain fixed across conditions. |
| Memory | Prose, JSON, and hybrid implementations; rendered-token limits; one repair; logged fallback behavior. | Semantic checks and fallback assistance differ between formats. |
| Execution | Real bounded-memory CLI integration, immutable pilot manifests, duplicate/partial-run guards, durable launch logs, and a Colab model-session workflow. | The default notebook and local script still launch an older full-history capability check. |
| Inspection | Saved-trace inspection and an auditor checking accounting, configuration consistency, memory limits, and permitted prompt fields. | A passing trace audit does not establish factual memory quality or a fair scientific comparison. |
| Larger evaluation | Six-condition launcher, source digest, held-out protocol, and analysis using matched-seed bootstrap intervals. | No held-out evaluation results or evaluation manifest are present here; this work is outside the active MVP. |

The new commit therefore contains substantive implementation and reported pilot
progress, rather than only planning. Existing tests cover actor reviews, memory
validation/fallback, runner accounting, and basic evaluation failure guards.

**Reported experimental progress**

Development proceeded through several distinct stages, which must remain separate:

1. Corrected-greedy full-history v11 checks succeeded on both development seeds.
   This established that Qwen could solve the two-ingredient task with history.
2. The first completed bounded-memory v11 grid lost all eight games through budget
   exhaustion, largely involving repeated cookbook inspection.
3. Follow-up diagnostics found both implementation and model failures: a prose
   fallback could drop the recipe; retaining the recipe did not eliminate loops;
   later prompts sometimes replaced reread loops with appliance inspections.
4. Actor reviews and updated memory handling led to the v29/v16 replay below.
   The results document reports all eight audits passing, no infrastructure
   errors, no budget exhaustion, and no identical actions on adjacent turns.

Latest development table, transcribed from
[docs/mvp-results.md](mvp-results.md):

| Memory | Reread cost | Seed | Outcome | Actions | Rereads | Input / output tokens | Model / episode seconds |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Prose | 2 | 0 | Success | 9 | 0 | 17,375 / 900 | 53.2 / 53.7 |
| Prose | 2 | 1 | Success | 6 | 0 | 12,164 / 588 | 36.5 / 38.1 |
| Prose | 5 | 0 | Success | 9 | 0 | 17,375 / 900 | 53.6 / 54.1 |
| Prose | 5 | 1 | Success | 6 | 0 | 12,164 / 588 | 36.8 / 38.3 |
| JSON | 2 | 0 | Terminal failure | 13 | 4 | 17,082 / 2,584 | 152.3 / 152.9 |
| JSON | 2 | 1 | Terminal failure | 5 | 0 | 5,920 / 964 | 58.0 / 59.7 |
| JSON | 5 | 0 | Terminal failure | 13 | 4 | 17,082 / 2,584 | 152.4 / 152.9 |
| JSON | 5 | 1 | Terminal failure | 5 | 0 | 5,920 / 964 | 57.2 / 57.7 |

Episode time excludes model loading. The model and episode times are reported
measurements, not newly reproduced timings.

The two existing trace annotations describe useful mechanisms. In the prose
seed-1 run, Qwen's review caught premature meal preparation and selected taking
salt; a later repair recognized completed grilling. In the JSON seed-0 run,
conflicting inventory fields accompanied four cookbook rereads, followed by
`eat red apple`, which ended the game. These narratives need confirmation from
their raw events before being treated as independently reviewed findings.

**What prevents a stronger conclusion**

1. **The real-model evidence is missing from this checkout.** The referenced
   `artifacts/mvp-v29-memory-v16-.../` directories are absent. The available
   artifacts are S1 environment records and S2 fake-model fixtures. Git ignores
   new `artifacts/` outputs, so pulling code does not retrieve those runs. The
   documented results may be correct, but their manifests, observations, prompts,
   outcomes, accounting, and audits cannot currently be rechecked here.
2. **The comparison changes more than representation.** In
   [memory.py](../game_memory/memory.py), prose requires `Carried items` and
   `Recipe progress` lines and has coded checks for inventory, recipe retention,
   progress, and some new observations, plus public-evidence fallbacks. JSON
   chooses its own fields and has a narrower semantic check/fallback around
   successful meal preparation. Hybrid does not receive those prose/JSON semantic
   checks. These helpers use public evidence, but unequal assistance can explain
   part of a format difference. A format-neutral actor review does not remove
   this writer-policy difference.
3. **There are only two unique development recipes.** Reusing them at two prices
   does not create four independent game instances per format. Prompts were
   repeatedly developed on these seeds, so they are unsuitable for an unbiased
   estimate of general performance.
4. **Recovery cost has not produced an observed behavioral contrast in this
   replay.** Outcomes, action counts, reread counts, and token totals match across
   prices for each format/seed. JSON seed 0 spends 17 budget units at price 2 and
   29 at price 5, but still ends through the same terminal mistake. This supports
   correct cost charging; it does not demonstrate a recovery-cost effect on
   behavior or relative success. The free recipe and short task may also impose
   little memory pressure; that remains a hypothesis to inspect on development
   data before any larger protocol is frozen.
5. **Launch instructions and status pages disagree.** The checkpoint guide's
   opening reflects the later replay, but its closing section still describes
   the earlier all-budget-exhaustion MVP. The runner and actor references contain
   obsolete statements that real bounded-memory CLI integration is pending.
   The main notebook defaults to full-history v3 with one ingredient, and the
   local script also defaults to that capability task, using BF16. Neither
   default reproduces the FP16 v29/v16 comparison. The additional root notebook
   is pinned to an older commit and v2-mechanics.

**Verification performed for this report**

Inspected the latest commit, core execution and memory code, launch defaults,
evaluation/analysis code, tests, current plans, and local artifact inventory.
Attempted the prescribed full suite:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

It exited with status 127 because `.venv/bin/python` does not exist in this
checkout. The results document reports an earlier 309-test pass; this review
does not independently confirm that pass or the current runtime/GPU setup.
No dependencies were installed, experiments run, or existing evidence changed.

**Remaining tasks, in execution order**

| Priority | Task | Completion criterion |
| --- | --- | --- |
| P0 | Recover the actual development evidence from the machine/account or Drive location used for the runs. | All eight v29/v16 episodes have their manifests, raw events, results, audit reports, and launch logs available together; historical/partial runs remain separately labeled. |
| P0 | Restore or identify the project runtime in this checkout. | `.venv/bin/python` works; dependency and Java checks and the full suite pass; optional model checks and GPU/runtime identity are recorded for real inference. Explain any skipped checks. |
| P0 | Re-audit and inspect actual gameplay before another comparison. | Reconcile eight unique `(format, price, seed)` cells against manifests; verify prompts, precision, token allowance, free reset recipe, reread charges, all review/repair usage, terminal outcomes, and absence of hidden history/diagnostic inputs. Read the two annotated traces in full. |
| P0 | State the claim this experiment can test and resolve unequal writer assistance. | Either explicitly report a comparison of these complete memory policies with the limitation, or define equivalent evidence-based validation/fallback rules for a format-focused comparison. Any behavior change receives a new version and separate development runs. |
| P1 | Make one documented launch path reproduce the intended comparison. | Explicitly select bounded memory, v29/v16 (or newly versioned policies), FP16, one room/two ingredients, allowance 256, budget 80, prices 2/5, seeds 0/1, and pinned model/code. Record the actual game fold and generation settings. Keep historical capability launchers labeled as such. |
| P1 | Finish the MVP evidence package. | Produce the table from recovered results, including outcomes, score, budget, rereads, tokens, generation and episode time; retain two evidence-backed annotations. Rerun only missing/invalid cells, or a whole newly versioned grid if policy/settings change. Preserve every old attempt. |
| P1 | Assess whether the task exercises the research question. | On development data, distinguish lost information, contradictory memory, failure to use correct memory, and irreversible gameplay mistakes. Report whether prices change behavior. If memory pressure is inadequate, choose and version a revised task before held-out work. |
| P1 | Reconcile documentation and handoff instructions. | README, checkpoint guide, runner/memory/actor references agree on completed versus pending work; include artifact location and the exact frozen launch settings. |
| Later | Prepare a larger study only after the MVP and comparison definition are settled. | Freeze the question, policies, seeds, task, model, analysis, and source snapshot before opening held-out games. Keep hybrid deferred unless it is explicitly included in the next scope. |

For a later 120-game study, the existing
[protocol](experiment-3x2-protocol.md) proposes three formats × two prices ×
20 matched test-fold seeds (1000–1019). Before using it, supply the required
`evaluation-manifest.json` and source snapshot, reconcile the protocol with any
policy changes, and verify first-episode audits, exact grid coverage, fixed
settings, interruption/error preservation, and paired analysis end to end.
The current evaluation tests cover duplicate/error/partial results and source
digest changes; they do not establish that complete workflow. No such manifest,
source snapshot, or held-out result set was found locally.

**Definition of a successful experiment**

For the current MVP: eight matched, auditable real-model outcomes under fixed,
declared settings; a reproducible table; two accurate trace annotations; and a
clear account of what the memory policies and recovery prices did. Gameplay
losses and a null price effect are valid results. A claim that prose is generally
better, or that price changes the format advantage, requires a fair, frozen
comparison on additional held-out instances with uncertainty reported at the
matched-seed level.
