# Research redesign proposal: controlled recursive memory before autonomous cooking

November 17, 2026. **Proposed for critique; no implementation or execution authorization.** Prepared in response to [the designer handoff](codex-research-redesign-prompt.md). Existing code, experiments, failed gates, and protocols remain authoritative for their own checkpoints. This document proposes a new checkpoint, provisionally named **mutable-bindings-v1**; it does not replace AGENTS.md or authorize its activation.

**Revision 2:** addresses [the critique](research-redesign-critique.md): independent assignment updates, accuracy-independent allowance selection, post-update versus twelve-filler probes, balanced annotations, stratified precision planning, and probe-specific provenance checks. The [reviewed first draft](../artifacts/research-redesign-revision/attempt-20261117-xMHP83/proposal-reviewed-v1.md) is preserved byte-for-byte, SHA-256 6a7e22097c2e6afe5f886fdb1d009c770144c60989aa250068a1cfac61b4653e. No experiment settings have been executed under either draft.

## Decision and primary question

Use **Path B: a small randomized, fixed-transcript task** as the primary experiment. Qualify the existing Qwen reader first, allow one separately approved supervised-adaptation attempt if necessary, and freeze the selected reader before comparing memory systems. Keep CookingWorld for later integration testing, with its own qualification requirements.

**Primary falsifiable question:** For one qualified, frozen Qwen reader, does reducing the stored-memory allowance from 256 tokens to a calibrated smaller allowance change the difference in delayed-choice accuracy between an untrained prose memory writer and an untrained JSON memory writer, after twelve intervening irrelevant observations and rewrites?

The primary endpoint is correct factual choice at the terminal query. For each independent transcript family f, let A(f,F,B,L) be accuracy averaged across its four counterfactual siblings, where F is prose or JSON, B is stored allowance, and L is intervening filler writes. The primary family-level contrast is:

    D_f = [A(f,JSON,B_low,12) - A(f,prose,B_low,12)]
          - [A(f,JSON,256,12) - A(f,prose,256,12)]

Estimate the equally weighted mean of the updated-query and untouched-query stratum means, with a two-sided stratified family-bootstrap 95% interval. Zero is the null; neither format is predicted to win. An interval spanning zero is inconclusive about a difference, not proof of equivalence. Report all four long-delay cell accuracies alongside the interaction so a tradeoff or common collapse is visible.

This is a **complete memory-system comparison**: formatting instructions, writing, retention, syntax handling, compression, and later reading all contribute. It does not isolate a general causal effect of JSON syntax. The reader's use of equivalent, sufficient public-fact notes is a separate diagnostic. Immediate post-update accuracy, its change after twelve filler rewrites, overwrite errors, abstention, storage, and cost are secondary outcomes. A terminal correct choice completes this deliberately one-decision task; it is not evidence of autonomous game completion.

## Why this path

| Consideration | A: qualify/train CookingWorld reader | B: randomized fixed transcripts |
| --- | --- | --- |
| Causal clarity | Memory interacts with planning, inventory, action availability, and irreversible mistakes | Identical public streams and decisions can be compared across memory conditions |
| Implementation effort | Existing environment/runner; new supervision, reader adaptation, and recovery qualification may be needed | One small task/replay module and tests; reuse model, memory-validation, and logging primitives |
| Training | Potentially necessary; unknown for the current legal-choice interface | Start untrained; one small adaptation option only if the reader fails its control |
| Inference cost | Variable trajectory lengths; loops can dominate cost | Fixed writer schedule and one reader call per query; finite call ceilings |
| External validity | Stronger connection to interactive agents | Narrow claim about mutable factual memory; no autonomous exploration claim |
| Failure attribution | Several interacting sources of failure | Reader, retention, overwrite, and syntax failures can be examined on shared evidence |

The local evidence motivates this ordering, not a claim that CookingWorld cannot work. The [four-seed full-history gate](history-window-checkpoint.md) failed once with recipe evidence present. The [v31/v17 calibration](v31-v17-roomy-calibration-2026-11-16.md) lost all four games while recorded storage remained 95–203 of 512 tokens. The [older reproduction](reproduction-2026-11-15.md) also shows why programmed prose rescue cannot support a model-written format claim. These are development observations from different protocols, not pooled estimates.

Original TextWorld supports training and evaluating language-interacting RL agents; it does not promise pretrained LLM task competence. TextWorldExpress provides accelerated games, including configurable cooking tasks and held-out distributions. These are reasons to retain it as an integration environment. [Original TextWorld paper](https://arxiv.org/abs/1806.11532), [TextWorldExpress project](https://github.com/cognitiveailab/TextWorldExpress).

DSSR provides a relevant reader-training precedent: the same Qwen base family is behavior-cloned across contexts, then frozen; its reported 97.8% full-history validation success belongs to that adapted reader. Its original-TextWorld games, supplied inventory, scripted exploration, and filtered options differ from this repository. Its reported writer gains weaken with longer delays. Those observations support qualification and controlled delay, not a transferable success guarantee. [DSSR, setup and appendices A–B](https://arxiv.org/html/2609.32805v2).

## Task: mutable assignments with a delayed query

Each world has eight opaque entity names and four possible destinations: amber, blue, green, violet. Destinations may repeat; assignments are independent, not a permutation or a conservation puzzle.

Public rules, identical across conditions:

1. An assignment remains valid until a later explicit assignment update or revocation.
2. An assignment update states the current destination and supersedes the earlier record. It may repeat the same destination. Revocation means the current destination is unknown; an old assignment must not be reused.
3. Any entity may be queried later. The query is not disclosed during writing.
4. No record lookup, reread, or other information source is available at query time. Choose "insufficient information" when the supplied evidence does not justify a destination. This is abstention, not a successful information-recovery action.

Each stream contains:

- Observation 0: all eight initial assignments, in a family-specific shuffled order.
- Observation 1: explicitly assign one entity its current destination, which may equal its old destination, and revoke a different entity in the same public update.
- Twelve filler observations, each saying an unrelated random pulse occurred and no assignments changed. Filler contains no entity names, destination words, or query cues.
- A query probe immediately after observation 1, before any filler, and another after filler 12. Both ask the destination of the same entity whose current assignment is known in the complete public history.

The two query probes are stateless reads of the memory snapshots. They are never fed into subsequent writer inputs. Each writer runs one fourteen-write chain: initial observation, update, twelve fillers. The immediate probe does not alter the continuation. This avoids generating the identical factual prefix twice and requires no general cache or resume mechanism.

Half of families query the entity receiving the assignment update (**updated-query**); half query an untouched entity. Updated-query does not imply that the destination changed: exactly one sibling repeats its old value. The revoked entity is used in missing-information qualification, not as an answerable primary query. Therefore the primary answer is one of four destinations, while the reader always has a fifth "insufficient information" option.

The experimental L is 0 or 12 filler rewrites. Exact fact-specific lag is also logged: L subsequent rewrites for an updated query fact, including a repeated assignment, and L+1 for an untouched query fact, because the unrelated update follows its initial exposure. The immediate snapshot shows whether the generated state already failed at compression/update; changes at L=12 show subsequent deterioration or improvement. The manipulation jointly changes intervening observations, interference, and rewriting; it does not isolate elapsed time or rewrite error from recency.

### Counterfactual families and leakage controls

A family contains four sibling worlds ordered by final query answer: amber, blue, green, violet. For updated-query families, **all four initial observations are identical**, including the target's old destination. Only the target's explicit new assignment in observation 1 varies across the four destinations. Permit the one assignment update that leaves the destination unchanged. The old destination alone cannot identify which of the four updates occurred. For untouched-query families, vary the target's initial destination; another entity receives the same assignment update in all siblings.

Use a separate seeded balancing stream for update values, independent of names and option order. Within updated-query strata, allocate old destinations equally across families: four families per old destination in the 16-family final stratum, each containing all four new destinations. Within the untouched-query stratum, assign the other entity's old/new pair from shuffled cycles of the full 4×4 Cartesian product, including unchanged pairs: each pair occurs once across its sixteen final families. Smaller pools use truncated shuffled cycles with frequency differences at most one. Across every updated-query quartet each fixed old value must support all four possible new values. Offline checks must reject any generator that restores a deterministic old-to-new mapping. Same-initial-state/different-update quartets are mandatory in reader qualification and any training allocation.

All other facts, fillers, query wording, public rules, and option order are identical within a family. The complete reader input outside the memory block must be byte-identical across siblings at a given probe. Different memories should require different correct choices.

Options contain all four destinations and insufficient information, labeled A–E. A family-specific seeded permutation sets their order, shared across siblings and conditions and independent of the destination. No correct-option insertion, pruning, reference-action hint, seed, family identifier, or evaluator metadata appears in model input.

With empty memory, a deterministic reader receives identical inputs across four different factual answers. It can achieve at most one correct factual choice per quartet, or zero if it abstains. This construction is the main memory-demand check; a long transcript or high utilization alone would not establish demand.

## Fixed components and information boundary

**Reader:** Qwen/Qwen3-4B-Instruct-2507, revision cdbee75f17c01a7cc42f958dc650907174af0554; initially no adapter. Use the existing Transformers backend, FP16 on the declared A10/A10G target, context 8192, generation seed 0, and restricted single-token label argmax with first-in-supplied-order ties. Validate actual prefix-stable nonspecial label IDs. No reader generation, reviews, repairs, conversation state, or fallback action. Preserve actual templated prompt hashes, scores, and usage. Repeatability is separate from correctness.

**Reader prompt:** one new, frozen task-specific prompt, not a modification of v31 or legal-choice-v1. Its common system instruction is:

> Use only the supplied context and current query. Assignments persist until explicitly replaced or revoked; destinations may repeat. Choose the latest supported destination of the queried entity. If the assignment is absent, revoked, or unresolved, choose insufficient information. Do not infer a destination from the other entities or guess. In diagnostic notes, a JSON null denotes an unknown destination; an omitted entity supplies no assignment. The context may be public history, prose, or JSON. Return only the label of one listed option.

Layout is public rules/goal, literal retained context, current query, and one labeled option list. Conflicting claims without a determinable latest value require abstention. The reader sees neither the allowance nor the answerable/missing-case category. Its input is otherwise identical across formats and capacities. Initialize the writer with the last-event marker [INITIAL_OBSERVATION]; all later updates use [PUBLIC_UPDATE]. Neither marker carries a family ID or future query.

**Writer:** the unadapted pinned Qwen checkpoint throughout, even if the reader later receives a LoRA adapter. Generation is greedy with the existing enforcement against checkpoint sampling defaults; output cap 1024, context 8192, no truncation of inputs. Retain v17's one syntax/size repair and exact previous-valid-state fallback, including empty legal output. No semantic validation or fact replacement.

The new task needs a separately versioned, shared writer instruction, provisionally probe-writer-v1. Its conceptual guidance is identical for both formats:

> Maintain the latest confirmed assignment of every observed entity. Replace superseded assignments and distinguish revoked or unknown assignments from confirmed destinations. Destinations may repeat. Any entity may be queried later. Use only previous memory, the last event, and the new public observation. Do not invent assignments or retain irrelevant pulse descriptions. Your replacement is the only persistent notebook and its complete rendering must fit the stated token allowance.

Only the output-format instruction differs: literal natural-language notes versus a JSON object with model-chosen keys. Reuse existing strict JSON/value-preserving rendering and repair rules. Introduce no fixed task schema in the primary writers. Shared task guidance is an intentional intervention relative to v17; results cannot be labeled unchanged-v17 results. Freeze the exact text before calibration, then do not tune it within this checkpoint.

The writer receives only previous rendered memory, the latest public observation, last event marker, public task rules/goal, and B. At initialization previous memory is empty. It does not receive the future query, options, full transcript, generator state, or annotations. Transport/runtime errors propagate instead of becoming memory fallbacks.

**Persistent state:** exactly one rendered memory string per world/format/B chain. Plans, uncertainty, keys, punctuation, and headings all count. No hidden factual Python state, retrieval archive, KV cache, earlier rejected output, reader answer, cross-request conversation, or weight update may supplement it. A same-call repair may see its rejected candidate, as under v17; it does not persist to later updates.

The experiment driver/evaluator may retain raw transcripts, scores, and references outside the model boundary. A separate deterministic public-log reducer may construct diagnostic notes and scoring references; it must never be consulted by a primary writer or reader path. Factual world state is not an extra model input.

**Budget:** count the entire actor-visible memory with the pinned tokenizer, without special tokens. B excludes shared instructions, current query/options, chat template, and writer-input serialization overhead; those still count toward actual inference input tokens and context. Record both stored size and complete input size. The actor receives memory literally, without a second escaping layer. Full history is storage-unbounded but still context-limited. There is no game-action budget or paid reread in this primary task; CookingWorld prices are deferred.

## Minimal controls and what they establish

At both probe positions, use four reference inputs in addition to the primary generated memories:

1. **Full public history:** all observations up to the probe, no writer. Checks reader performance with the evidence available; not a guaranteed upper bound.
2. **No memory:** empty retained context with the same terminal input. Checks present-input shortcuts and abstention; the quartet construction bounds factual guessing at 25%.
3. **Sufficient public-fact prose note.**
4. **The equivalent sufficient public-fact JSON note.**

Construct sufficient notes by a predetermined forward reducer of public assignments, replacements, and revocations. Include the current state of all eight entities, regardless of the future query. Do not select facts using the query or model outcome. Both renderings express the same facts and uncertainty. These are explicitly scripted diagnostic memories, not model-written states. They must each fit 256 measured tokens before real inference begins; otherwise the proposed task is not ready.

These controls distinguish a reader that cannot use adequate context from a generated state that fails to preserve or communicate it. If a sufficient note also fits B_low and succeeds, it demonstrates a useful encoding at that budget for that case. It does not prove optimal compression, unavoidable loss in other cases, or that an online writer would choose that encoding.

Omit a recent-history window from the initial grid. It would answer an additional recency-baseline question without being needed to identify this configured-allowance interaction. A window may be a separately approved follow-up. No privileged-state oracle, hindsight best-of-N, regret estimator, model judge, or writer training is included.

## Reader qualification and the training decision

First complete the existing actual tiny-model and cached-tokenizer checks in a provisioned environment. Their currently documented skips are not passes. This proposal does not authorize dependency installation or that environment's acquisition.

Then evaluate the stock reader once on validation pool Q0: four fresh families, sixteen sibling worlds, with the long-delay input. For each world run full history, sufficient prose, sufficient JSON, missing-fact prose, missing-fact JSON, and no memory: **96 reader calls**. Index families 0–3 and siblings 0–3 in destination order. When the sum of those indices is even, missing-fact notes remove just the main queried assignment from the otherwise sufficient note and retain the main query. When odd, retain the complete sufficient note but query the revoked entity instead. Apply the same case in both formats. The expected choice for both missing-note formats is insufficient information, based on what the reader actually receives.

Pass requires:

- At least 15/16 correct for each of full history, sufficient prose, and sufficient JSON.
- At least 15/16 correct abstentions for each missing-note format.
- No-memory factual accuracy at most 4/16, and exact equality of sibling prompts outside memory.
- Zero technical failures and complete request/response/action provenance.

These are pragmatic small-sample qualification thresholds, not a claim of 95% population reliability. Passing may still miss sensitivity to arbitrary model-written schemas. A reader that passes is frozen without training. Do not train merely to improve the desired format result.

If it fails, stop writer experimentation. The only proposed adaptation option is a separately approved reader-only SFT attempt:

- 64 disjoint training families × four siblings × four context types = 1024 labeled examples.
- Context types: full history, sufficient prose, sufficient JSON, and a missing/revoked note. Index training families f=0–63, siblings w=0–3, and contexts c=0–3 in that order. For the missing-note context, use prose when floor(f/2)+floor(w/2) is even and JSON otherwise; use the omitted/revoked-case rule from qualification, based on f+w. Use delay 4 when floor(f/4)+w+c is even and 12 otherwise. These separate parity rules balance missing-case type, missing-note format, and delay across the training allocation. Even-indexed families query the reassigned entity and odd-indexed families query an untouched entity. Labels come from the public information actually supplied; missing context is labeled abstention, not the hidden factual destination.
- Fixed LoRA rank 8 on q_proj/v_proj, alpha 16, dropout 0; frozen base, full-vocabulary cross-entropy on the next label token; AdamW, learning rate 0.0001, weight decay 0, two epochs, microbatch 1, accumulation 16, seed 0, max norm 1. Use FP16 with loss scaling and no quantization. Abort on nonfinite loss or context overflow. No hyperparameter search, RL, DAgger, or writer adaptation.
- Use development cases for software checks only. Select the final two-epoch adapter, not whichever intermediate checkpoint favors one format. Record all preprocessing and adapter hashes.
- At most two A10 GPU-hours including training setup and checks. Adapter deployment must demonstrate that writer calls still use the unadapted base; never silently apply the reader adapter to the writer.
- Repeat the exact qualification procedure once on a different reserved pool Q1 of four families. No Q0 cases enter training. A second qualification failure ends this checkpoint and returns to design review; do not automatically try another model or larger dataset.

Compatible adapter dependencies would need to be pinned and authorized before this conditional branch. No such environment is verified here. This narrow task teaches lookup/update mechanics; it does not qualify CookingWorld planning or information-seeking. CookingWorld must separately test justified legal rereads/inventory actions when information is missing.

## Splits, calibration, gates, and final evaluation

Partition families before producing training examples, notes, or model outputs. Every sibling, query context, delay, capacity, and format derived from a family belongs to the same split. Use disjoint entity vocabularies and disjoint normalized assignment/update/query compositions across splits. Normalize away names, filler strings, and option permutations when checking composition overlap; a new seed or renamed entity is not enough. Keep 5-letter lowercase entity IDs distinct across splits. The worked names below are reserved examples and excluded from generated data.

Freeze an immutable manifest listing IDs, generator version, split allocation, exact prompts, note templates, endpoint, inference controls, option permutations, and stopping rules. Use separately named random streams derived by SHA-256 from protocol ID, split, family index, and purpose; never Python's salted hash. Declare the global seed as 0. Randomize sequential condition execution order once per family from its own purpose stream, independently of answers, and save it in the manifest. Seeds and generator/reference fields are evaluator-only. A failed uniqueness check stops preparation. The final test set is generated and sealed without human inspection of its facts or outcomes until settings are frozen; record hashes and coverage. All inspected historical CookingWorld seeds remain development material.

Allocation:

- Training: 64 families, used only for the conditional SFT branch.
- Development: four families; the first two are the writer calibration pilot. Other development cases support software/example checks, not a search for a winning format.
- Reader qualification: Q0 four families; Q1 four separate reserved families only if SFT is used.
- Protocol validation: V four additional families, evaluated after calibration freezes B_low.
- Final test: 32 independent families, sixteen updated-query and sixteen untouched-query. In every split/pool, even-indexed families query the reassigned entity and odd-indexed families query an untouched entity selected uniformly from the other six eligible entities. Choose reassigned/revoked indices independently of entity spellings, and independently shuffle the public initial-assignment order. No family replacement based on performance.

The initial capacities are **64 and 256 tokens**. At each B and in each format, write through all twelve fillers and probe at 4 and 12. Thus each family contributes four sibling worlds × two formats × two capacities × two probe positions = **32 primary decisions**.

Calibration on the first two development families is allowed one prespecified adjustment of the low allowance, applied to both formats:

1. Require long-delay high-budget accuracy at least 75% separately for each format. Failure stops this writer comparison; diagnose writer fidelity before spending more on budgets.
2. Let low be the mean long-delay accuracy across the two formats. Require low in [25%, 87.5%], with mean high minus mean low at least 12.5 percentage points.
3. If low <25%, try B_low=128 once. Otherwise, if low >87.5% or the high-minus-low gap is smaller than 12.5 points, try B_low=32 once. Keep 256 fixed. There is no second adjustment and no prompt, fact-count, delay, or model tuning.
4. If the adjusted condition still fails the same criteria, stop. Keep all calibration outcomes, including the initial unsuccessful setting, and return to design review.

These gates seek a usable performance range; their estimates are deliberately coarse and are not final evidence of a memory effect. A configured allowance can affect proactive compression without full utilization or explicit over-budget rejection. Conversely, even a measured effect of B does not establish an information-theoretic minimum.

Freeze settings, then run the same primary grid and controls on V. Apply the same long-delay high-budget and performance-range requirements. Additionally require at least 15/16 correct separately for full history, sufficient prose, and sufficient JSON at each of the two delays; the same sixteen sibling worlds supply each denominator. If V fails, do not change settings and reuse V as a fresh validation set. Preserve the failed validation and return for a new research decision. The historical CookingWorld gate remains failed and unrelated.

Open the final 32-family test once, only after V passes and a measured cost projection fits the remaining allocation. Run every declared cell. The primary estimate is the long-delay interaction above; report per-cell accuracies, the two query strata, and short-delay results as secondary. Bootstrap complete families 10,000 times with fixed seed 0, retaining all siblings and matched cells together. Do not treat writer updates, siblings, or repeated probes as independent trials. Do not select the better delay or report only the winning capacity.

Thirty-two independent families provide a small, coarse comparison, useful for large effects and failure characterization. They do not justify a general claim that a 5–10-point advantage exists or is absent, broad model superiority, or benchmark-wide reliability. Report the actual interval; if it is wide, the result is inconclusive. More samples require a separate decision.

## Costs, errors, and finite resource limits

Per family there are sixteen writer chains, each fourteen writes: **224 primary writer calls**, at most 224 writer-repair calls, 32 primary reader decisions, and 32 reference-reader calls. Generation output is capped at 1024 for every writer/repair call. Reader output accounting is one selected token per scored decision. A short-delay probe never creates a writer call.

For the final 32 families: **7168 primary writes**, at most 7168 repairs, and **2048 reader calls including controls**. The two-family minimum calibration pilot has 448 primary writes, at most 448 repairs, and 128 reader calls. One low-budget adjustment adds at most 224 primary writes, 224 repairs, and 32 primary reader calls; previously collected reference inputs are unchanged and must not be counted as new inference.

Maximum proposed allocation is **14 A10/A10G GPU-hours across all new model work**, split into ceilings: reader qualification/checks 0.5 h; development calibration 1.5 h; conditional SFT 2 h; protocol validation 1.5 h; final test 8 h; startup/measurement allowance 0.5 h. Unused training allocation is not permission to expand another stage. Count allocated GPU wall time, including model loading and idle setup; also report generation time separately. These ceilings and the expectation of several GPU-hours are planning estimates, not measured throughput or price quotes.

Before final execution, project full coverage using the observed pilot call lengths, repair frequency, peak memory, and measured end-to-end rate. If it does not fit its ceiling, return to critique before opening test outcomes. Do not silently reduce sample size or omit controls. Use no more than one GPU concurrently. Any dollar ceiling requires the user's separate provider/rate decision.

For every condition report primary/repair/reader calls, input/output tokens, exact stored size, cap hits, rejection/fallback counts, synchronized generation/forward time with its scope, tokenization-inclusive replay time, load time, allocated GPU wall time, and peak CUDA allocation. Charge shared writer prefixes once per actual chain; identify that both probe positions reuse those writes. Report total cost per chain and cost to reach each probe. A shared loaded base is not free startup, and a one-token scorer is not assumed faster without measurement.

Infrastructure failures stop the worker immediately and retain partial traces and original status. No automatic retry or replacement family. The final endpoint is reported as incomplete if any declared cell is missing; technical failures are neither silently dropped nor counted as ordinary incorrect choices. Any resumed completion requires an explicit documented decision preserving the first attempt. Writer syntax/size rejection with declared fallback is a memory-system outcome, not automatically an infrastructure failure.

Accuracy counts a wrong destination or abstention on an answerable primary query as noncompletion. Report destination-answer coverage for all decisions; factual accuracy may include lucky guesses and is not itself a retention measure. Independently annotate four long-delay memory snapshots per test family, one per format/B at sibling index (family index modulo 4): **128 snapshots**. A second annotator checks all four snapshots for the first eight families, giving 32 double-coded states. Report unsupported-answer rate only for this annotated sample, with ambiguous support separate. Use public logs only and the existing annotation principles. Classify retained supported bindings, omissions, stale overwrites, revoked-as-known claims, invented mappings, ambiguous semantics, and syntax/fallback consequences. Do not infer arbitrary JSON key meanings. Use sufficient-note results to diagnose reader errors, but do not claim that a trace reveals the model's internal cause or that this annotation sample explains every error.

## Complete worked short-delay episode

The following are **illustrative ideal memories, not generated outputs or token measurements**. There are eight entities, one update containing reassignment and revocation, four filler writes, and one terminal query. Query and sufficient-note templates are shared between formats. No fact reducer supplies these states to a primary writer.

Public observation 0:

    Assignments: mavik=violet; tesun=blue; lorpa=green; nedev=violet;
    fesan=blue; kurim=amber; pavos=violet; zilen=green.

Illustrative prose M0:

    Mavik is assigned to violet. Tesun is assigned to blue. Lorpa is assigned to green.
    Nedev is assigned to violet. Fesan is assigned to blue. Kurim is assigned to amber.
    Pavos is assigned to violet. Zilen is assigned to green.

Illustrative JSON J0, shown as its complete compact rendering:

    {"fesan":"blue","kurim":"amber","lorpa":"green","mavik":"violet","nedev":"violet","pavos":"violet","tesun":"blue","zilen":"green"}

Public observation 1:

    Update: mavik is now assigned to green, replacing its previous assignment.
    Tesun's assignment is revoked; its destination is now unknown.

Illustrative prose M1:

    Mavik is assigned to green. Tesun's assignment is revoked; its destination is unknown.
    Lorpa is assigned to green. Nedev is assigned to violet. Fesan is assigned to blue.
    Kurim is assigned to amber. Pavos is assigned to violet. Zilen is assigned to green.

Illustrative JSON J1:

    {"fesan":"blue","kurim":"amber","lorpa":"green","mavik":"green","nedev":"violet","pavos":"violet","tesun":null,"zilen":"green"}

For this diagnostic encoding only, null means revoked/unknown, and an absent key means the note supplies no assignment. That semantic convention is explained equally to the prose and JSON reader; it is not a required primary-writer schema.

Public observations 2–5, each a separate writer update:

    2. Ambient pulse bunaf. No assignments changed.
    3. Ambient pulse kezor. No assignments changed.
    4. Ambient pulse wudep. No assignments changed.
    5. Ambient pulse jaxol. No assignments changed.

The ideal snapshots are M2=M3=M4=M5=M1 and J2=J3=J4=J5=J1, meaning the full strings are retained unchanged. The equality notation belongs only to this explanation; the model never receives an uncounted pointer to M1/J1. An actual writer may omit or corrupt facts and that outcome must be preserved.

Current public query, identical for both formats and for all four sibling worlds:

    What is mavik's current destination?
    A. amber
    B. blue
    C. green
    D. violet
    E. insufficient information

Correct choice with M5 or J5: **C**. The old violet assignment is superseded. For the amber counterfactual sibling, its earlier observations instead establish amber as mavik's latest assignment; the exact same query/options require **A**. No current input distinguishes those histories except retained context.

Missing-fact read of the same terminal query: remove mavik's sentence from M5 or its key from J5, leaving the other seven entries. The justified choice becomes **E**, although the evaluator still knows the actual world destination. This is a reader diagnostic, not a successful factual answer in the main task. A separate query for tesun also requires **E** because its assignment was explicitly revoked.

Budget policy at every snapshot is T(memory) <= B, where T is the pinned tokenizer's encode length without special tokens. Every sentence, newline, JSON key, quote, brace, null, and stored plan counts. Counts for M0/M1/J0/J1 are **unmeasured** here. Before inference, measure and publish them. If a candidate exceeds B, use only the fixed one-repair/previous-state policy; never inject these ideal examples as rescue. If either sufficient diagnostic rendering exceeds 256, stop preparation rather than declaring it sufficient under that allowance.

## Smallest implementation and verification sequence

This section is a proposed future handoff, not permission to implement now.

1. **Repair general evidence provenance first.** Current source inspection still finds the general v31 auditor checking public inputs/history/budgets without establishing the final selected-output-to-action or accepted-writer-output-to-memory links. The [critique evidence](design-critique-2026-11-17-evidence.json) records both mutation probes passing. Also select optional-article diagnostic normalization from recorded actor metadata. Add negative tests for mismatched actions, literal prose, canonical JSON, previous-state fallback, and review/repair routing. Do not infer semantic correctness or change live actor/writer behavior.
2. **Preserve the recent legal-choice verification work.** Its [report](../artifacts/legal-choice-v1-verification/attempt-20261117-164128/report.json) records 383 passes and 25 skips; actual tiny forwards and cached-Qwen tokenizer/config checks remain unexecuted. The new error-accounting and special-token checks do not fix the separate general-auditor gaps. This design review inspected code and existing evidence; it did not rerun mutation probes or tests.
3. **Add one task/replay module and direct tests.** Suggested location: game_memory/memory_probe.py with generator, fixed prompt builders, sequential replay, references, and a small CLI. Reuse Message/Generation, the Transformers scorer, token counting, memory validation/repair, and request-before-call logging. If extracting a small shared helper is necessary, prove unchanged v31/v17 prompts and outcomes with existing fixtures. Do not force this task through CookingWorld-specific action costs or the full-history-only legal-choice actor. No environment replacement or general experiment framework.
4. **Keep writer changes explicit and small.** Enable the fixed new shared writer instruction/identity while preserving v17 defaults and historical paths. Keep syntax, canonicalization, budget, and fallback machinery shared. Reader requests remain format-neutral. No new task-specific semantic validators.
5. **Offline acceptance:** test seeded quartet construction; disjoint splits/compositions; exact identical terminal views/options; all four answers; overwrite/revocation semantics; no repeated decisive facts in fillers; query exclusion from writer inputs; correct snapshots and lag counts; both budgets; no cross-world memory; no reader-answer feedback; full and partial failure accounting; deliberate output/memory/action tampering. Snapshot hashes must come from independent expected content, not the function under test. Fix source/fixture mismatches rather than weakening assertions.
6. **Actual runtime checks:** use the cached pinned tokenizer/config to recount notes, validate the exact new prompt's labels, enforce context limits, and independently recompute prompt hashes. Run the existing tiny CPU forward tests and relevant/full suites in an already provisioned environment, preserving failures/skips. Do not treat fake IDs, whitespace counts, or skipped cases as model verification.
7. **Seek separate authorization for qualification, then calibration, validation, and final inference.** Each stage must pass before the next opens. The SFT branch additionally needs authorization for dependencies and training. Save immutable protocol/source/runtime identities, declared coverage, raw requests/results/errors, and actual resource use in fresh directories. No existing manifest or failed result is overwritten.

## Path A remains a viable alternative, not a parallel experiment

If retaining autonomous CookingWorld as the primary claim is more important than attribution, replace this recommendation through a new design decision. Do not run both projects concurrently by default.

A bounded alternative would start with the untrained legal-choice reader and the current one-room/two-ingredient mechanics, full public action set, initial recipe, budget 80, and reread cost 2. Qualify on fresh games with full history and forward-derived sufficient public notes before deciding training is needed. Accept any dependency-correct successful route; do not require recipe listing order when the engine does not.

If adaptation is needed, propose at most 100 training games and 2000 supervised decisions, with 20 development games and separate 40-game qualification and 40-game final pools. Use different engine folds where available and reject duplicate normalized recipe compositions across pools. Include full history and equal proportions of sufficient prose/JSON states, missing-information cases, possession changes, and nonterminal recovery states. Privileged gold paths can supervise offline, but labels must be defensible from the supplied public evidence: otherwise teach an available public information action. Include legal wrong-appliance alternatives so command legality is not confused with recipe correctness. No reference action may shape runtime options.

Use one reader LoRA attempt, at most four A10 GPU-hours, before considering RL; freeze the final reader across formats. Require at least 36/40 full-history wins, at least 36/40 sufficient-note wins separately by format, at most one destructive recipe-method error per control, and at least 90% justified information-action choices on a separately fixed 40-case missing-fact panel. These are proposed readiness thresholds, not established rates. If unsuccessful, return to design rather than expand training automatically. Writer training is a later decision. No CookingWorld capacity comparison begins until a development no-memory/paired-public-state diagnostic demonstrates that new episodes actually require retained facts and calibrated allowance changes matter. Exact new game IDs, supervision extraction, compatible training dependencies, and resulting cost would need freezing before approving this alternative; they are not silently supplied by the old failed gate.

## Strongest threats, unresolved items, and abandonment criteria

- **Narrow task:** random bindings omit navigation, planning, and tool grounding. A positive result supports this task and configuration; CookingWorld transfer is unestablished. If autonomous game completion is the required primary deliverable, choose Path A instead.
- **Overstrong guidance or trivial coding:** eight four-way assignments can be encoded compactly in principle. A model may learn a short code or the allowances may never affect it. This is not a Shannon-capacity experiment. Stop if the prespecified calibration cannot produce an informative range.
- **Unqualified reading of generated schemas:** passing canonical notes does not qualify every model-invented schema. Separate reader failures with supported notes from omissions and ambiguous memory; do not force all losses into forgetting.
- **Writer instruction intervention:** shared explicit retention guidance differs from unchanged v17 and from DSSR's plain summary. Results concern these frozen complete systems only. Pure representation evidence is limited to the equivalent-note diagnostic.
- **Small sample and gating:** development/validation selection can choose a useful regime and exaggerate anticipated effects. Keep the final families untouched, publish every attempted development setting, and treat wide final intervals as inconclusive.
- **Training leakage:** names, normalized update/assignment compositions, counterfactual siblings, and public-note variants must remain split together before preprocessing. Training only general mechanics is an intention that these checks must substantiate, not a guarantee from distinct seeds.
- **Delay interpretation:** more fillers also mean more rewrites and input tokens. No claim isolates elapsed time, pure storage decay, or a single internal failure cause.
- **Resources:** final evaluation remains conditional on measured pilot throughput. Missing dependencies, tokenizer cache, adapter compatibility, concrete provider price, and token lengths are currently unverified prerequisites. Their absence blocks their stage, not evidence-preserving software work.
- **Abandon or redesign** if sufficient-context reader qualification fails twice, diagnostic notes exceed the roomy allowance, sibling present-input leakage is found, both low-budget settings are at floor/ceiling or nonbinding in performance, V fails, or projected complete coverage exceeds the fixed allocation. A single failed format is a result to inspect, not a reason to rescue it or replace test families.

## Critique checklist

- [ ] Does the primary interaction compare complete systems honestly, with the equivalent-fact representation diagnostic kept separate?
- [ ] Is the stock or adapted reader qualified on sufficient, missing, and revoked evidence, without transferring DSSR's success rate?
- [ ] Are all episode facts confined to counted memory, with public history/references/evaluator metadata inaccessible to primary model paths?
- [ ] Are sibling current inputs/options identical, factual answers counterbalanced, and fact-specific delay counts correct?
- [ ] Are allowance changes causally assigned and calibration rules fixed, without claiming irreducible capacity loss from utilization or eviction?
- [ ] Is substantive writer guidance equal, JSON schema freedom explicit, and semantic rescue absent?
- [ ] Are train, development, qualification, protocol validation, and final families/compositions separated before preprocessing?
- [ ] Are writer prefixes, repairs, reader probes, errors, and uncertainty accounted for at their actual costs and independent-family level?
- [ ] Are sample-size limits, narrow external validity, training stop rules, and compute ceilings credible?
- [ ] Can the critique agent approve this bounded protocol or identify a concrete flaw before any implementation or new inference is authorized?
