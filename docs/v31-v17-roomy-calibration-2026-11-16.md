# v31/v17 generous-memory calibration — four completed losses

November 16, 2026. All four declared prose/JSON × seed 0/1 games completed. Prose won 0/2 and JSON won 0/2. All failures occurred before meal preparation. Earlier v31 full-history controls won both seeds; those are separate capability diagnostics, not additional bounded conditions.

| Format | Seed | Outcome | Score | Actions | Budget | Rereads | Stored tokens |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| Prose | 0 | terminal_failure | 0.429 | 7 | 7/80 | 0 | 180–203/512 |
| Prose | 1 | budget_exhaustion | 0.400 | 42 | 80/80 | 38 | 128–203/512 |
| JSON | 0 | budget_exhaustion | 0.286 | 80 | 80/80 | 0 | 140–141/512 |
| JSON | 1 | budget_exhaustion | 0.400 | 77 | 80/80 | 3 | 95–106/512 |

## What the traces show

**Prose seed 0:** memory 40 retains “slice the red apple”; response 42 selects “chop red apple,” and action 43 executes that wrong cut and ends the game. The relevant recipe fact was available in memory, so omission of that fact does not explain this decision.

**Prose seed 1:** after open-fridge, take-chicken and grilling actions 7/13/19, memory 22 says “meal preparation complete.” No salt-taking or meal preparation had occurred. Responses 24/26 attempt unavailable `eat meal`. The writer later invents a valid-action list and retains the completion claim while the actor falls into 38 cookbook rereads. This appears to conflate ingredient preparation with finished meal preparation; the trace does not isolate one phrase as the sole cause of the loop.

**JSON seed 0:** after knife taking (7) and apple slicing (21), primary writer responses 9/23 and repair responses 11/25 contain an extra closing brace. Both updates fall back to exact previous valid state (12/26), losing explicit new progress. Memory 32 changes progress to `examine_knife`; the remaining 77 actions examine the knife. The recipe remains, but explicit slicing completion is absent from later memory. No cooking or meal-preparation checkpoint is reached.

**JSON seed 1:** memory 30 still includes the recipe after grilling at 27. Memory 38 drops its recipe field and explicit prepare-meal direction after an invalid action. Cookbook reread 41 supplies the recipe again, but memory 44 does not restore that field/direction. Memory 72 replaces the grilling marker with `examine_toaster`; 68 consecutive toaster examinations follow from action 10 through 77. No salt-taking or meal preparation occurs. Ingredient names remain stored; an `inventory.salt=present` flag already existed at reset, so its carriage meaning remains unknown rather than automatically being labeled false.

Four offline diagnosis JSON files under the review root cite public event sequence IDs, exact observations and memory quotes. They score specific facts/claims, not whole-object accuracy. Model-managed schema meanings are not assumed; unreached checkpoints and absence of post-terminal memory are explicit. None of these annotations entered model inputs.

## Memory and inference accounting

All **206 stored renderings** independently matched the pinned cached tokenizer. The largest was **203/512 tokens**. There were zero over-budget rejections and zero generation-limit hits. There were **204 primary accepted writes, zero repaired accepted writes and two previous-state fallbacks**, reconciling to 206 updates. JSON seed 0 made two writer-repair calls and had four malformed-JSON rejections. All stored memories were nonempty. Technical acceptance alone did not establish useful state retention.

The four games consumed **255,235 input tokens, 33,935 output tokens**, and **1203.58 synchronized generation seconds**. These are descriptive costs for unequal-length failed games, not evidence of format efficiency. All actor, writer, review and repair usage is included.

| Condition | Load seconds | Episode seconds | Generation seconds | Outer pilot seconds | Actual GPU |
| --- | ---: | ---: | ---: | ---: | --- |
| prose seed 0 | 6.87 | 65.11 | 64.53 | 78.87 | NVIDIA A10G |
| prose seed 1 | 6.60 | 263.02 | 262.02 | 277.12 | NVIDIA A10 |
| structured seed 0 | 6.42 | 441.39 | 440.14 | 456.52 | NVIDIA A10 |
| structured seed 1 | 7.85 | 438.47 | 436.88 | 455.66 | NVIDIA A10G |

Generation time excludes tokenization/transfer/decode. Episode time excludes loading; outer pilot time includes process startup/loading/gameplay. Modal worker startup, audits and image building have separate records. Every episode subprocess returned 0 and no inference/OOM error occurred. A gameplay loss is valid data. Exact per-purpose costs and peak-RAM records are in the raw evidence.

## Frozen policy, audit correction and limitations

Actor `s2-action-v31`, writer `p1-memory-v17`, renderer `p1-render-v2`; Qwen/Qwen3-4B-Instruct-2507 revision `cdbee75f17c01a7cc42f958dc650907174af0554`. CUDA FP16, greedy decoding, generation seed 0, context 8192, actor cap 128, writer cap 1024, memory allowance 512. Train seeds 0/1; one room, two ingredients, zero distractors, no doors, unlimited inventory, one free initial recipe, budget 80 and reread price 2. Requested A10, four CPUs, 32 GiB host RAM; actual A10/A10G identities are reported above. Python 3.12.10, Torch 2.8.0/CUDA 12.8, Transformers 4.57.6, Java 17 and Modal 1.6.4. These are development observations, not held-out results or a formal factorial comparison.

Original protocol: `qwen-v31-v17-modal-a10-roomy-calibration-v1`, executable digest `1cc6aec3a37373e057887185207439e5f9a3a57ae576d89ffe69ac41f3a93429`, uploaded snapshot `0850c519629af699e1aec65451ca1200e9f3df1a187b117b8cb839b8ac839207`. The original CPU preflight passed 394 tests with no skips.

Prose seed 1 finished its game, then its remote audit failed because the auditor’s explicit repair-policy allowlist omitted v31’s new identifier. The original failed worker status/audit remain unchanged. Adding that identifier preserves the checks requiring exact latest memory and a recorded same-turn rejected proposal. A separately saved corrected audit passes on the original downloaded trace; gameplay was not rerun.

A new regression exercises real simulator wiring with scripted inference and confirms a fabricated rejected proposal still fails the audit. Its first fixture used the fake writer’s historical prompt contract and failed while the other 394 tests passed; that failed CPU attempt is preserved. The corrected focused regression passed, then the complete suite passed **395 tests with zero skips** before JSON launches resumed.

JSON runs use the explicitly declared audit-only addendum protocol `qwen-v31-v17-modal-a10-roomy-calibration-audit-v2`, digest `4842d1833f630ac961a39025eb1f8ad6a4ba2bfed51eb87605644dc0951728ce`, snapshot `119ef30d5263b2a01d1b8389281ee2e753dfdcd7b6af0ec8f8b4e43c3a1327c2`. Per-file checks confirm `summarize_diagnostics.py` is the sole changed game_memory file: actor, writer, renderer, environment, runner, model adapter and dependencies remained identical. Launcher/test changes are preserved in uploaded source ZIPs. This analysis-only identity split is disclosed; the four results are not passed off as one exact-source factorial manifest. Each condition is independently audited.

## Evidence and next development checkpoint

Plans, addendum, four per-cell summaries, corrected audit and public-evidence diagnoses are in `artifacts/modal-review/v31-v17-roomy-20261116/`. Each summary records its run reference and exact downloaded evidence root. Raw cloud evidence remains in `memory-research-results`, with weights only in `memory-research-cache`. No episode was replaced, retried or tuned mid-run; four GPU episodes were launched in this calibration. Failed audit/CPU attempts are preserved separately.

The combined package is `artifacts/modal/v31-v17-roomy-20261116-evidence.zip` with adjacent SHA-256. It contains raw traces/results, original and corrected audits, source snapshots, validation attempts, references, summaries, diagnoses and this report. ZIP CRC and per-file hashes are verified. It excludes environments, credentials and model weights. The combined ZIP is local; raw results remain durable on Modal.

The generous-memory behavior gate remains unmet: neither format achieved useful bounded gameplay success here, and the observed size boundary was nonbinding. The next development target is state fidelity and use: preserve confirmed possession and completed operations across unrelated observations; separate observed facts from plans and unsupported completion/action claims; investigate the actor choosing the wrong recipe method despite correct stored instructions. JSON syntax repair also failed on two informative updates. These call for separately versioned, focused changes with controls before a tighter-memory or eight-game comparison. This checkpoint does not authorize another sweep or more GPU runs.
