# Critique of the research redesign proposal

November 17, 2026. Reviewed `research-redesign-proposal.md`, SHA-256 `6a7e22097c2e6afe5f886fdb1d009c770144c60989aa250068a1cfac61b4653e`, against the earlier repository critique and current component interfaces. References below identify proposal line numbers in that reviewed version.

## Decision

**Request revisions to the protocol; retain the controlled-task direction.** The proposal makes a substantial improvement over the earlier CookingWorld comparison: it defines a specific interaction, matches public evidence, groups counterfactual siblings correctly, qualifies a reader, and separates scripted sufficient notes from generated memory. It also correctly limits the primary claim to complete memory systems rather than JSON syntax alone.

One generator rule creates an avoidable answer shortcut. Calibration and annotation rules introduce additional restrictions that should be corrected before this becomes the implementation specification. These are small design changes; they do not justify returning to autonomous cooking or adding reinforcement learning.

## 1. High priority: the reassignment value is determined by the old value

**Location:** [counterfactual construction](research-redesign-proposal.md), line 63; conditional reader training, lines 129–134.

For every reassigned-query family, the old value is the next color after the final value in a fixed cycle. Consequently the following mapping holds throughout the proposed dataset:

| Old destination | New destination |
| --- | --- |
| amber | violet |
| blue | amber |
| green | blue |
| violet | green |

A reader that remembers the old value can reconstruct the new one without reading or retaining the new assignment. In full-history examples, it can identify which entity was updated but ignore the actual destination in the update. The optional supervised-training allocation would repeatedly expose this same relationship.

This is a possible shortcut, not an observed Qwen behavior. The quartet still establishes that some past information is needed: empty context cannot identify its factual answer. It does **not** establish that the new assignment must survive or be used. The shortcut weakens reader qualification for update semantics and the interpretation of stale-state errors.

**Smallest fix:** use the same initial target assignment across all four siblings and vary its explicit new assignment across the four destinations. Permit one explicit assignment that leaves the value unchanged, and call the event an assignment update. Across families, balance every old/new pair. This preserves four balanced answers and identical current query/options while removing the deterministic old-to-new rule.

If every update must change the value, use three siblings with the same old assignment and all three other destinations, and revise the chance bound, sample sizes, and costs accordingly. Randomizing the four-sibling ordering alone does not fix the dependency.

Add an offline generator check that each old value has multiple possible new values across the dataset. Include same-initial-state, different-update pairs in reader qualification. The new assignment must carry information not already recoverable from the initial state.

## 2. Medium priority: the calibration gate rules out a valid primary effect

**Location:** primary contrast, lines 9–16; calibration and validation, lines 154–165.

The primary hypothesis asks whether capacity changes the **difference between formats**. The gate additionally demands that smaller memory reduce the **average accuracy across formats** by at least 12.5 points. Those are different conditions.

For example, the following development results satisfy the high-budget and low-range gates:

| Format | 256 tokens | Low allowance |
| --- | ---: | ---: |
| Prose | 75% | 50% |
| JSON | 75% | 100% |

The primary interaction is **+50 percentage points**, but mean high minus mean low is zero. The proposed gate would shrink the allowance again or stop. The same restriction is repeated in validation.

Because selection occurs before the final held-out test, this is not automatically test-set leakage or an invalid held-out comparison. It does narrow the question to a selected regime with an average penalty and can discard crossover behavior that directly answers the stated question. Smaller allowances can improve a particular system by removing distracting or contradictory content; the protocol should allow that possibility.

**Smallest fix:** retain the reader and roomy-writer qualification gates, but remove the requirement that the mean accuracy gap have a particular sign and size. Calibrate the low allowance using a predefined compression or retention criterion that does not require a format ranking or average accuracy decline. Record rendered sizes, rejected candidates, retained facts, and performance separately. A null final interaction remains a valid outcome.

Alternatively, keep the current gate and explicitly narrow the primary question to a development-selected regime with an average capacity penalty. That is defensible but less general than the current opening question. In either case, preserve the finite adjustment rule and avoid requiring the primary interaction itself to appear during calibration.

## 3. Medium priority: there is no checkpoint before the irrelevant rewrites

**Location:** writer schedule and delay interpretation, lines 50–59; controls, lines 99–110; worked example, lines 221–228.

All factual information arrives during the first two writes. Every later observation explicitly says that assignments did not change. The best subsequent state transition can therefore be literal copying, with no further factual interpretation.

That makes this a useful recursive-rewrite stress test. It also makes a checkpoint immediately after the real update particularly valuable. Probes after four and twelve fillers cannot show whether a failure already existed immediately after compression/update or emerged during the supposedly irrelevant rewrites. Full-history and scripted sufficient-note controls do not supply that missing comparison for the actual generated state.

**Smallest fix:** replace the secondary four-filler probe with a zero-filler probe immediately after observation 1. Keep the twelve-filler primary endpoint. This preserves the number of writer chains and reader probes while distinguishing initial/update failure from later deterioration.

At the long-delay point, a carry-forward control can retain that actual post-update memory through all explicit no-change observations. It adds no facts and needs no hidden state. With the proposed reader layout, its input is identical to the zero-filler read of that memory, so that measured result can be referenced as the control without another reader call, provided the identity and accounting are explicit.

This control would support a practical conclusion: whether repeated generative rewriting damages a state that could simply have been preserved. It would not establish general superiority of copying when observations contain real changes. Keep that scope explicit.

## 4. Medium priority: annotation selection confounds query type and answer color

**Location:** sibling ordering, line 116; even/odd query strata, line 150; annotation selection, line 183.

The proposal orders sibling destinations as amber, blue, green, violet, makes even families reassigned-query cases and odd families untouched-query cases, then annotates sibling `family_index % 4`.

For the 32 final families, the selected annotation families are therefore:

| Query type | Amber | Blue | Green | Violet |
| --- | ---: | ---: | ---: | ---: |
| Reassigned | 8 | 0 | 8 | 0 |
| Untouched | 0 | 8 | 0 | 8 |

Each selected family contributes four format/budget snapshots. The 128 annotations consequently never inspect reassigned blue/violet answers or untouched amber/green answers. A color-specific reading or encoding issue would be mixed with the apparent update-versus-retention mechanism.

The proposal limits unsupported-answer reporting to the annotated sample, which is appropriate. That qualification does not make this deterministic imbalance useful.

**Smallest fix:** choose the annotation sibling from its own seeded stream, independently of query type, and balance destinations within each stratum. With 16 families per stratum, assign each of four sibling destinations four times using a prespecified shuffle. Select double-coded cases with the same principle. The annotation workload stays unchanged.

## 5. Lower priority: tie final effort to an effect size worth resolving

**Location:** final inference and uncertainty, lines 165–177.

The arithmetic is correct: the final grid has 7168 primary writer calls, at most 7168 writer repairs, 1024 primary reader calls, and 1024 reference-reader calls. The independent sample size is 32 families, as the proposal acknowledges. The 14 GPU-hour allocation is explicitly a ceiling, not a measured runtime prediction.

Before approving the final eight-hour allocation, state a minimum interaction size worth distinguishing and make a sensitivity calculation at the family level. As an illustration only, the ordinary normal-approximation 95% half-width `1.96 × SD(D_f) / sqrt(32)` is about 8.7 points for family-level SD 0.25 and 17.3 points for SD 0.5. These are arithmetic scenarios, not estimated variability, bootstrap intervals, or a power analysis for the proposed data.

Use the measured pilot to assess throughput and investigate plausible variability without selecting a favorable effect. If precision is inadequate for the research goal, revise the allocation before opening the test set. Also resample within the fixed 16/16 query strata and combine them with equal weights; that preserves the population mixture the design explicitly fixes.

Some controls also repeat identical reader inputs. Sufficient notes and empty memory do not change between the proposed delay positions. State whether repeated calls serve an explicit repeatability check; otherwise record identical-input reuse and its actual inference cost. This is a smaller issue than the writer workload.

## Scope and implementation corrections

The new probe needs independent checks linking actual reader scores to selected labels and accepted writer output to stored memory. Those are essential to its evidence contract. A separate repair of every legacy v31 review/repair path need not become a prerequisite if the probe never calls those paths. The earlier auditor findings remain real; the immediate requirement is trustworthy evidence for the path being used. This narrows the implementation burden without weakening verification.

Keep the optional reader-adaptation branch conditional. A generator shortcut should be fixed before deciding the reader needs training. If training is used, retain the proposal's separation between the adapted reader and unadapted writer, and qualify on unseen compositions. No result here establishes that training, another base model, or CookingWorld transfer is necessary.

The high-budget qualification, independent family grouping, missing-information labels, query exclusion from writer inputs, and separation of technical failures from model outcomes should remain. The omission of a recent-history window is defensible for the stated primary comparison; it is not a missing mandatory control.

## Requested revision

Return a focused amendment to the existing proposal:

1. Remove the deterministic old-to-new relationship and update quartet examples, qualification cases, and offline checks.
2. Align calibration with the stated interaction, or explicitly narrow the research question to the selected regime.
3. Replace the four-filler secondary probe with an immediate post-update probe and define the carry-forward comparison.
4. Balance the annotation sample across query type and answer destination.
5. Preserve stratification in uncertainty estimates and make final precision/resource approval depend on a stated scientific target.

Update the affected call counts, gates, and worked example once. No broader benchmark search or additional training method is needed for this revision.

## Verification and limits

This review read the complete proposal and relevant current memory, scoring, and logging interfaces. Standard-library arithmetic checks reproduced the destination dependency, annotation imbalance, crossover-gate counterexample, and final call counts. No pretrained inference, tokenizer measurement, training, cloud work, or program changes were performed. The proposal and historical evidence were not edited. Software suites were not rerun for this document-only review.

The proposal is not disproven as a complete memory-system experiment. Its primary endpoint could still yield useful results. The requested revisions remove avoidable shortcuts and make those results easier to interpret before paying for them.
