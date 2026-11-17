# Implementation status and verification handoff

**Snapshot: November 17, 2026. Audience: teammate preparing the project progress report.**

This document summarizes the implementation, verification methods, preliminary diagnostics, current obstacles, and proposed next steps. It covers work since commit `18ade457aef86bf907c0877db9432d318095bfbc` on November 16, 2026, titled “Preserve v17/v30 calibration and Modal laptop handoff.” The current branch is `codex/modal-calibration-handoff`. The implementation and original handoff are checkpointed in `4a847e1`.

**Follow-up proposal, November 17:** [compare memory schemes before and after reader fine-tuning](pretrained-vs-finetuned-memory-proposal.md), initially holding the writer fixed. This broader system-accuracy question counts ordinary reader errors as outcomes; high reader accuracy is not a universal prerequisite for that comparison. It develops an alternative to the earlier worked-example-only next step below. No task-specific fine-tuning, new inference, or writer pilot has been performed or authorized by publishing the proposal.

**Current position:** we have implemented a controlled memory-research harness, tested its software behavior, and exercised its tokenizer, reader, logging, persistence, collection, and shutdown paths on Modal. The first authorized run stopped correctly at reader qualification. The primary comparison of model-written prose versus JSON under different memory budgets has **not run**.

There are preliminary CookingWorld and reader-qualification observations. Report them as development/qualification evidence, separately from the planned memory experiment. The report can present an implementation and verification milestone with preliminary qualification evidence while leaving the primary memory-comparison results explicitly pending.

## 1. Research objective and current scope

The broad objective is to study how an LLM writes and uses external memory, and how limited storage affects downstream decisions. We initially used CookingWorld, where an agent must retain recipe and progress information while selecting cooking actions. Development runs showed that unreliable task execution could obscure the effect of memory.

The current frozen protocol, **memory-probe-v1**, replaces cooking decisions with controlled assignment updates and factual questions. Its primary question is:

> Does reducing stored-memory allowance from 256 to 64 tokens change the accuracy difference between model-written JSON and model-written prose after 12 intervening no-change rewrites?

The frozen pilot rule could instead select 128 as the lower allowance. This is a comparison of complete memory systems: writing, compression, retention, validation/fallback, and subsequent reading. It does not isolate JSON syntax alone.

The model is stock `Qwen/Qwen3-4B-Instruct-2507`, revision `cdbee75f17c01a7cc42f958dc650907174af0554`. No task training, adapter, or replacement model has been introduced. The current reader failed its prerequisite gate, so v1 ended before the writer/budget pilot. A reader-only v2 is a proposal, not an implemented continuation.

The authoritative study specification is [memory-probe-v1.md](memory-probe-v1.md). The longer [research redesign proposal](research-redesign-proposal.md) and [critique](research-redesign-critique.md) document design development; where their scope differs, use the frozen v1 protocol and package.

## 2. Work completed since the last commit

### CookingWorld execution and diagnosis

We established Modal A10/A10G execution, model caching, immutable run settings, durable result storage, accounting, and evidence retrieval. An initial v30/JSON migration pilot succeeded. A separate v30 full-history control repeatedly proposed preparation after a meal already existed. These were separate observations under different memory conditions, not evidence of a general format advantage.

Actor v31 improved meal-finalization priority and repair routing. Two full-history controls succeeded on development seeds 0 and 1. Subsequent v31/v17 bounded-memory calibration lost all four prose/JSON games across those seeds. The largest stored note was 203 of the configured 512 tokens, with no over-budget rejections. The observed failures therefore did not establish that a 512-token limit was intrinsically insufficient. Traces included wrong actions despite retained recipe facts, unsupported completion claims, malformed JSON followed by fallback, and repeated low-value actions.

A later four-seed full-history readiness run succeeded on three seeds and lost seed 2 through a wrong cooking-method choice. The frozen all-four-success gate failed. No history-window comparison was launched. Small selected-request readout diagnostics further separated visible-fact extraction and action-selection problems; their limited selected cases do not identify internal reasoning or general reliability. V32 probes were prepared and parked rather than promoted into the active actor.

Sources: [Modal migration pilot](modal-pilot-2026-11-16.md), [v30 full-history control](modal-full-history-control-2026-11-16.md), [v31 finalization](actor-v31-finalization-2026-11-16.md), [four bounded-memory losses](v31-v17-roomy-calibration-2026-11-16.md), [four-seed readiness report](../artifacts/history-window-modal-baseline/20261117T023432Z-01de8202/report.md), and [selected-request diagnostic](../artifacts/method-readout-modal-execution/20261117T032231Z-3fe0a360/report.md).

### Code simplification

The CookingWorld cleanup retained v31 with full-history, prose, and structured JSON memory. It consolidated gameplay into `game_memory.run_episode` and read-only reporting into `game_memory.summarize_diagnostics`. Hybrid/history-window policies, retired actor variants, separate session/evaluation/inspection paths, and superseded launchers were removed from the active core.

The cleanup retired 21 specifically authorized files after archiving their exact starting bytes. Pre-cleanup actor fixtures captured 22 cases and 44 turns; parity tests preserved the retained actor requests, routing, and outcomes. The v17 writers retained strict syntax/size validation, one repair, and exact previous-valid-state fallback. A later small `_messages` hook enabled the probe-specific prompt while tests pinned the original v17 messages to their pre-refactor capture.

The cleanup is reversible from its archived source; historical experiments were not erased or rescored. A post-cleanup full-history seed-0 development episode succeeded in 11 actions, while still exhibiting unnecessary actions and repaired proposals. That success did not replace the earlier failed four-seed gate.

Sources: [minimal-core guide](minimal-core.md), [cleanup completion report](../artifacts/minimal-core-cleanup-v1/attempt-20261116-232112/completion-report.md), and [post-cleanup episode evidence](../artifacts/qwen-v31-minimal-core-v1/minimal-core-full-history-seed0-20261117T043648Z-setup2/inspection.json).

### Restricted-choice interface

We implemented `legal-choice-v1`, an opt-in CookingWorld action interface that scores labels for the complete public legal-action list using one model forward pass. It avoids free-form action parsing/review/repair in that interface and preserves the selected legal action unchanged, including harmful choices. The default CookingWorld actor remains v31.

The scoring adapter validates labels at the actual chat-template prefix, requires distinct nonspecial single-token labels, selects the largest candidate logit, and breaks exact ties by supplied order. It records token IDs, logits, conditional probabilities, selected labels, actual prompt hashes, and usage. The CookingWorld legal-choice gameplay experiment has not run. The same scoring capability was subsequently exercised with real Qwen in the controlled qualification task.

Source: [legal-choice specification and verification history](legal-choice-v1.md).

### Controlled task and Modal transport

We implemented the controlled generator, writer adapters, reader prompts, exact-input result reuse, scripted controls, qualification and pilot rules, audits, planned analysis, and annotation sampling. Design reviews removed a deterministic reassignment shortcut, aligned the pilot rule with the interaction question, added an immediate post-update probe, and balanced annotation selection.

P1 software reviews fixed exact assessment/write coverage, incomplete-pilot error propagation, and full repair-request/routing verification. The Modal transport then added package/runtime/cache checks, preflight-before-load ordering, one-load execution, request limits, persistent unit commits, collection, and shutdown. Further review fixed local collection imports, repeated evidence retrieval, noninteractive shutdown, and preservation of valid pilot-stop classification.

The active scientific package is `package-v2`; its audit corrections preserved the original model-facing texts, splits, annotation plan, and planned counts. Earlier packages and transport packets remain immutable historical evidence.

Sources: [P1 revision 2 report](../artifacts/memory-probe-v1/p1r2-20261117T192619Z/report.md) and [accepted transport report](../artifacts/memory-probe-v1/s1-preparation-20261117T200538Z/report.md).

## 3. Implementation map

| Component | File | Responsibility and boundary |
|---|---|---|
| Public game contracts | [contracts.py](../game_memory/contracts.py) | Public view, configuration, and transition types; keep privileged engine state out of agent inputs. |
| CookingWorld environment | [environment.py](../game_memory/environment.py) | Simulator interaction, action costs, and termination. |
| V31 actor | [actor.py](../game_memory/actor.py) | Existing model-driven cooking decisions, review, and repair; retained behavior protected by parity fixtures. |
| Optional choice actor | [choice_actor.py](../game_memory/choice_actor.py) | Map public legal actions to scored labels without selecting a better action programmatically. |
| Bounded memory | [memory.py](../game_memory/memory.py) | Prose/JSON rendering, token allowance, strict JSON acceptance, one repair, and previous-state fallback. |
| Full history | [diagnostics.py](../game_memory/diagnostics.py) | Preserve public interaction records without invoking a writer. |
| Model adapter | [transformers_model.py](../game_memory/transformers_model.py) | Pinned cached model/tokenizer, explicit greedy generation, restricted label scoring, actual token/time metadata. |
| Runner and inference ledger | [runner.py](../game_memory/runner.py) | Game wiring and reusable `_LoggedModel`; preserve requests, responses, errors, and known usage. |
| Gameplay preparation | [pilot.py](../game_memory/pilot.py), [run_episode.py](../game_memory/run_episode.py) | Manifest protection and the consolidated CookingWorld entry point. |
| Independent game reporting | [summarize_diagnostics.py](../game_memory/summarize_diagnostics.py) | Reconcile trace evidence and accounting without editing input results. |
| Controlled study | [memory_probe.py](../game_memory/memory_probe.py) | Generator, prompts, controls, writer chains, reader reuse, gates, auditing, package freeze, and planned analysis. |
| Modal orchestration | [memory_probe_modal.py](../game_memory/memory_probe_modal.py) | Frozen-package execution, cache/runtime preflight, request cap, collection, verification, and targeted shutdown. |

Research logic is in Python modules; notebooks are not the implementation of the controlled experiment. The new path reuses existing writers, model scoring, and inference logging instead of introducing a separate inference framework.

## 4. Frozen controlled experiment

### Public task and memory flow

Each family has eight opaque entity names and four destinations: amber, blue, green, and violet. Destination values can repeat. Observation 0 gives all assignments. Observation 1 updates one assignment and revokes another. Twelve subsequent observations contain no assignment changes.

Four counterfactual sibling worlds require the four different destination answers. Updated-query families share the initial target value and vary its explicit update, including an identity update. Untouched-query families vary the target's initial value while another entity receives a shared update. This prevents the new destination from being recovered by a deterministic old-to-new shortcut.

The intended flow is:

```text
Previous bounded note + current public observation + public rules
                         |
                  prose or JSON writer
                         |
            validate, render, count whole note
                         |
                 stored bounded note
                         |
             reader + current query/options
                         |
                  scored label A-E
```

The writer receives exactly `previous_memory`, `last_event`, `observation`, `public_rules`, and `memory_token_limit`. It never receives the future query, options, gold answer, hidden evaluator state, or a scripted sufficient note. Tests require identical writer requests when only future query/options/gold change.

Prose is stored literally, including whitespace. Generated JSON uses model-chosen keys and the inherited strict, value-preserving canonical rendering. The allowance includes keys, punctuation, whitespace, and any stored plans. A rejected candidate gets one repair; a second rejection retains the exact previous valid state. This is syntax/size handling, not semantic correction.

Reader calls are stateless restricted-label forwards over A-E: four destinations plus insufficient information. They receive no family ID, allowance, or probe-position label. Exact identical inputs can reuse a physical reader result within a family; each logical assessment retains its own gold answer and source-call reference. Writer outputs are never reused this way.

### Splits, probes, and controls

| Item | Frozen plan | Execution status |
|---|---|---|
| Qualification | Q00-Q03: four families, 16 sibling worlds | Executed once; gate failed. |
| Development pilot | D00-D01: two families | Not executed. |
| Test | T00-T07: eight families, four per query stratum | No test-family inference. |
| P0 | Read after the update/revocation observation | Writer-chain measurements not executed. |
| P12 | Read after twelve no-change rewrites | Qualification uses complete supplied reference contexts; writer-chain measurements not executed. |
| Memory formats | Model-written prose and model-written JSON | Implemented and fixture-tested; no new controlled-study writer calls. |
| Allowances | Pilot 64/256; test lower allowance selected as 64 or 128 | No budget decision. |

Names and normalized task compositions are disjoint across splits. Seeds are derived from SHA-256, not Python's process-dependent `hash()`.

Controls include full public history, no memory, and sufficient prose/JSON notes produced by a forward reduction of public observations covering all entities. Qualification additionally tests missing/revoked facts and appropriate abstention. Scripted sufficient JSON uses entity-to-destination bindings; the generated JSON writer remains free to choose its schema. Qualification on reference notes is a prerequisite for a pilot, not proof of competence with every generated note.

### Gates and planned analysis

Q0 requires at least 15/16 correct separately for full history, sufficient prose, and sufficient JSON; at least 15/16 abstentions separately for the two missing-fact conditions; no-memory factual accuracy at most 4/16; matching sibling inputs outside memory; and zero technical failures. No-memory is a construction check, not a competence score.

Only a passing Q0 permits the pilot. Its frozen rule stops if both formats score at most 2/8 at P12/B256. Otherwise it selects 128 only if pooled P12/B64 correctness is below 4/16; it selects 64 otherwise. Incomplete or unauditable evidence cannot select a budget. No particular direction of format advantage or average accuracy decline is required.

For a completed test, the planned per-family interaction is:

```text
D_f = (JSON_low - prose_low) - (JSON_256 - prose_256), at P12
```

Each cell averages four siblings. The primary estimate gives equal weight to the two query-stratum means. Planned reporting includes all eight family effects, sign counts, a 10,000-resample stratified family bootstrap, P0/P12 accuracy and abstention, carry-forward controls, usage/timings, repairs/fallbacks, and 32 balanced P12 snapshots for annotation. Four families per stratum support weak population inference; interval coverage is not established. None of these primary analyses has been performed on real writer/test data.

## 5. How we verify the implementation

Verification separates software behavior, evidence integrity, and scientific qualification.

| Layer | Checks | What it establishes |
|---|---|---|
| Preservation | Before/after file ledgers, source/archive hashes, pre-refactor message captures, actor parity fixtures | Retained behavior and historical evidence were preserved within the declared scope. |
| Generator and boundaries | Counterfactual coverage, role separation, disjoint splits, filler leakage, reader sibling identity, writer-request invariance | Construction and visible-input rules hold for the generated study. |
| Memory policy | Strict JSON, duplicate-key/nonfinite/value-changing-number rejection, complete rendered size, repair routing, exact fallback | Outputs are routed according to the declared technical policy; factual quality remains a model outcome. |
| Reader/scoring | Prefix-stable distinct nonspecial label IDs, finite logits, vocabulary bounds, argmax/tie reconstruction, source-call links | Recorded label selection and mapping reconcile with the declared scorer. |
| Evidence audits | Exact planned identities once each, raw requests/responses, immutable completion hashes, independent gate and usage recomputation | Results reconcile with frozen inputs and raw records; aggregate row counts alone are insufficient. |
| Transport/failure behavior | Authorization/import/help safety, exclusive reservations, remote re-entry refusal, preflight before weights, request cap, ordered commits, error preservation, repeatable collection, shutdown | CPU fixtures verify control flow; actual execution verifies the exercised remote paths. |
| Research gate | Reader accuracy/abstention with sufficient or missing evidence | Determines whether this protocol permits the memory pilot. Passing software tests cannot substitute for this gate. |

The code records requests before inference and preserves returned outputs even if later rejected. Errors retain known usage and identify incomplete accounting instead of silently substituting zero. Technical errors and incomplete evidence propagate as failures; an audited model-performance stop is valid research evidence.

New negative tests deliberately corrupt assessment identities, logits, selected labels, writer states, repair messages, recorded events, and hashed files. These checks test whether the auditor rejects inconsistent evidence. Fixture token counters, logits, and commit callbacks are explicitly synthetic.

The latest saved software checks, before S1, are:

| Selection | Passed | Skipped | Exit |
|---|---:|---:|---:|
| Controlled-probe tests at accepted P1 revision 2 | 54 | 0 | 0 |
| Final transport-focused tests | 46 | 0 | 0 |
| Final relevant suite | 290 | 23 | 0 |
| Final full suite | 483 | 25 | 0 |

The full-suite skips comprise 22 torch-dependent Transformers cases, one actual cached-tokenizer check, one torch-dependent pilot case, and one Java 9+ check. They remain skipped local checks. S1 separately supplies actual GPU evidence for the tokenizer/scorer paths it exercised; it does not retroactively pass every skipped test. A known upstream TextWorldExpress cleanup warning is retained where observed. Earlier interrupted/failing development attempts are preserved alongside successful final checks.

Exact commands, full logs, exits, and skip lists are in the [accepted preparation packet](../artifacts/memory-probe-v1/s1-preparation-20261117T200538Z/). The full-suite command is `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q -rs`. These results are saved evidence, not a claim that tests were rerun while writing this document.

## 6. Authorized S1 execution and preliminary observations

S1 was authorized for one A10 worker, at most one Qwen weight load, a 600-second startup cap, 7200-second execution cap, 6900-second soft deadline, zero configured retries, and at most 1070 physical requests. The intended sequence was cached-tokenizer preflight, Q0, then D00-D01 only if Q0 passed. No test-family inference or S2 was authorized.

The runtime was an NVIDIA A10G with Python 3.12.10, torch 2.8.0, Transformers 4.57.6, tokenizers 0.22.1, safetensors 0.6.2, huggingface-hub 0.36.0, and CUDA 12.8. Inference used CUDA float16, context 8192, seed 0, and the pinned revision. Writer generation would use greedy decoding and cap 1024; no writer generation occurred.

The existing `memory-research-cache` was mounted read-only and `memory-research-results` held evidence. Cached-only loading and offline environment settings were enforced. Actual tokenizer preflight passed before the one weight load: 76 distinct Q0 prompts, label IDs 32-36, and 112 frozen sufficient notes measuring 45-67 tokens, all within the required 256-token reference allowance. All-split preflight counting/rendering performed no test-family inference.

| Qualification condition | Observed | Required | Outcome |
|---|---:|---:|---|
| Full history | 15/16 correct | At least 15/16 | Pass |
| Sufficient prose | 16/16 correct | At least 15/16 | Pass |
| Sufficient JSON | 13/16 correct | At least 15/16 | Fail |
| Missing-fact prose | 16/16 abstentions | At least 15/16 | Pass |
| Missing-fact JSON | 16/16 abstentions | At least 15/16 | Pass |
| No memory | 0/16 factual correct; all abstained | At most 4/16 factual correct | Pass |

Sibling inputs matched and there were zero technical model failures. The run ended as **`valid_research_stop`**. D00-D01 did not run; no budget was selected, no writer quality was measured, and no S2 planning estimate is available.

All three JSON errors occurred in Q00. Across its four sibling contexts, the reader always chose green while the explicit `tevug` value varied across the four destinations. The prose and full-history controls answered all four Q00 siblings correctly. The failed JSON notes contained the correct fact and were only 47-48 tokens. The full-history error was a separate Q03 sibling. The internal cause is unknown.

This is a reader-qualification observation before compression. The 16 sibling worlds belong to only four families; they are not 16 independent task replications. These observations establish neither general format superiority nor a memory-capacity effect.

### Actual accounting

| Measurement | Observed value |
|---|---:|
| Physical reader forwards | 76 |
| Logical assessments | 96 |
| Reused assessments | 20 |
| Actual input tokens, physical calls counted once | 30,108 |
| Accounted decision output tokens | 76 |
| Writer/generation/repair/fallback calls | 0 |
| Unknown-usage requests | 0 |
| Synchronized reader-forward time | 6.93 s |
| Adapter model-load time | 8.41 s |
| Whole Q0 unit wall time | 7.64 s |
| Reported worker time | 29.15 s |

The decision tokens are scored labels, not autoregressively generated text. Forward time excludes tokenization, transfer, validation, and CPU selection. Q0 excludes model loading. The worker counter is sampled before the final outcome save/commit and excludes image construction/container startup. No GPU-cost amount or writer throughput was measured. Q0 timing cannot supply the missing writer-pilot runtime estimates.

The real run exercised entry, preflight, qualification-unit, and final results-volume commit paths. Downloaded completion hashes, prompts, logits, mapping, coverage, reuse, and usage were independently checked. The saved App inventory showed **stopped with zero tasks**. No retry, resubmission, pilot, or S2 occurred. A successful run does not establish crash-rescheduling durability under unobserved failure modes.

Primary sources: [S1 execution report](../artifacts/memory-probe-v1/s1-execution-20261117T202458Z/report.md), [independent audit](../artifacts/memory-probe-v1/s1-execution-20261117T202458Z/independent-audit.json), and [raw qualification events](../artifacts/memory-probe-v1/s1-preparation-20261117T200538Z/collection-bdm5ddqa/download/stage/qualification/events.jsonl).

## 7. Current obstacles and next steps

The frozen reader did not qualify with complete JSON evidence, ending v1 under its declared gate. CookingWorld had already shown that decision errors could occur despite retained public facts. Reader competence controls help prevent attributing every wrong answer to compression or retention. The follow-up training-comparison proposal instead measures end-to-end accuracy with those reader errors included, while preserving controls and notebook inspection for interpretation.

The controlled-study writers and planned analysis are implemented and fixture-tested, but their real behavior remains unknown. We do not yet know generated-note factual quality, deterioration over twelve rewrites, the appropriate lower allowance, the format-by-budget interaction, or writer-pilot runtime. No task training or evaluation of a replacement model has been performed.

Earlier proposed next work at the original handoff, **not implemented or authorized**; see the follow-up proposal above for the subsequent training-comparison direction:

1. Preserve v1 as an ended protocol with a failed qualification gate. Update the active-status documentation and checkpoint the accepted source without altering frozen historical packages/results.
2. Specify one reader-only v2 intervention. The current recommendation is one fixed worked example demonstrating lookup and label selection, with the same Qwen checkpoint and unchanged qualification threshold. Use fresh, frozen qualification families; observed Q0 cases are development evidence.
3. After separate approval and execution authorization, run that bounded qualification once. If it passes, specify the new protocol's writer/budget pilot before any final test. If it fails, make a separate reader/task decision rather than accumulating prompt patches or relaxing the gate.

CookingWorld, model training, model switching, extra pilots, price comparisons, hybrid memory, large evaluations, dashboards, and optimization are outside the current next step. The proposed example is an untested intervention, not a demonstrated solution or a continuation of the stopped S1 run.

## 8. Reproducibility and evidence locations

Repository: `/Users/abdivu/Desktop/school/6.4610/64610-Memory`.

| Record | Location |
|---|---|
| Frozen scientific specification | [docs/memory-probe-v1.md](memory-probe-v1.md) |
| Accepted study package | [package-v2 manifest](../artifacts/memory-probe-v1/package-v2/manifest.json) |
| P1 software acceptance | [P1 revision 2 report](../artifacts/memory-probe-v1/p1r2-20261117T192619Z/report.md) |
| Accepted transport and final software tests | [S1 preparation packet](../artifacts/memory-probe-v1/s1-preparation-20261117T200538Z/report.md) |
| Actual run, authorization, command exits, and independent audit | [S1 execution packet](../artifacts/memory-probe-v1/s1-execution-20261117T202458Z/report.md) |
| Downloaded runtime/preflight/model/stage evidence | [Collected remote files](../artifacts/memory-probe-v1/s1-preparation-20261117T200538Z/collection-bdm5ddqa/download/) |
| Real-evidence collector verdict | [collection-verification.json](../artifacts/memory-probe-v1/s1-preparation-20261117T200538Z/collection-bdm5ddqa/collection-verification.json) |
| Saved shutdown verdict | [verified.json](../artifacts/memory-probe-v1/s1-preparation-20261117T200538Z/shutdown-6ket32rt/verified.json) |
| Execution evidence hashes | [execution-evidence-sha256.json](../artifacts/memory-probe-v1/s1-execution-20261117T202458Z/execution-evidence-sha256.json) |

Key identities:

```text
Study: memory-probe-v1
Active package: artifacts/memory-probe-v1/package-v2/
Manifest digest: f13e098e790f52159d5f34d5b1d608f8da1829a9b10ae84c4413beaebdba4fa6
Source ZIP SHA-256: 341927b9d47cf8a651885169ff6677d9a94098e6f8a7a9e9c58cfbca42e36f55
S1 run: memory-probe-v1-s1-20261117T200538Z
Execution packet: artifacts/memory-probe-v1/s1-execution-20261117T202458Z/
Derived Modal image: im-0dJq04p9gbWjNlIMbSkdOm
```

The manifest digest uses the implementation's specified JSON serialization convention. Source archives and file ledgers allow checks against the actual frozen bytes even while the working tree evolves. During review, all original 1,879 pre-transport files, accepted packet files, and frozen source matched their saved hashes; the execution ledger covered 84 files and matched. Those counts describe the corresponding historical ledgers, not the total current repository size.

`artifacts/` is Git-ignored. The implementation and handoff are tracked as of `4a847e1`, but a fresh clone does not supply these raw evidence packets. The committed Markdown provides the narrative; selected hashed evidence must be transferred separately if the teammate needs reproducibility. Relative artifact links resolve only when those files are present in the same repository/evidence layout.

README now links this handoff and the follow-up proposal. AGENTS retains the earlier CookingWorld minimal-core checkpoint wording within the frozen source boundary. Use the probe specification and dated execution report for the completed study's status, and the follow-up proposal for the new direction; none supplies new execution authorization.

## 9. Guidance for writing the progress report

A suitable report structure is: motivation and research question; original CookingWorld confounds; simplified architecture and controlled-task design; model/configuration and information boundaries; verification methodology; preliminary qualification observations; limitations; and proposed next work.

Claims supported by the current evidence include:

- We implemented the controlled task, bounded-memory adapters, restricted reader, evidence audits, and Modal transport.
- Offline behavior/failure tests passed under the recorded selections, with optional skips disclosed.
- One real cached-tokenizer/Qwen qualification run completed with reconciled usage and verified saved shutdown state.
- The frozen reader gate failed on sufficient JSON, and the program correctly stopped before the memory pilot.

Keep the primary comparison explicitly unfinished. Do not claim that JSON or prose is generally superior, that a storage capacity limit was found, that repeated rewriting caused the observed errors, that the writers were empirically validated by S1, that greedy decoding guarantees correct/deterministic behavior across runtimes, or that passing tests proves research validity. No causal explanation for the JSON errors has been established.

This handoff was compiled from repository files, frozen manifests, saved test logs, and audited execution records. Writing it added this Markdown document only; it did not rerun tests, alter implementation/evidence, launch inference, or create a Git commit.
