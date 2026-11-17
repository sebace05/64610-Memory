# Matched reader-training protocol v1

November 17, 2026. **Proposed operational protocol; no training or inference
authorized.** This specifies a future driver; only the
[reader diagnostic](reader-diagnostic-v1.md) is implemented in this checkpoint.
Do not interpret the stage instructions below as existing training CLI commands.

**Primary question:** given the exact same notebook, does task-specific reader
training change how well Qwen uses model-written prose versus JSON? Use one common
stored-memory allowance, P12 as the primary endpoint, and P0 as the immediate
post-update comparison. Keep the writer frozen. Count ordinary stock-reader errors
in accuracy. The old 15/16 threshold does not gate this baseline; the v1 failure
and its evidence remain unchanged.

## 1. Freeze data and the answer interface

Finish the diagnostic before generating training data. Resolve any independent
scoring mismatch first. The proposed primary reader interface remains restricted
A–E scoring, enabling next-label training. If the diagnostic instead motivates a
generated-answer interface, amend and freeze this protocol before training; do not
select an interface using final-test accuracy. No perfect-accuracy gate is imposed.

Generate fresh families with the existing eight-entity/four-destination task,
independent updates/revocations, four counterfactual siblings, and twelve no-change
rewrites. Use protocol namespace `matched-reader-training-v1`, global seed 0, and
SHA-256-derived per-purpose streams. Allocate:

| Split | Family IDs | Families | Updated / untouched |
|---|---|---:|---:|
| Budget development | C00–C03 | 4 | 2 / 2 |
| Training | R00–R31 | 32 | 16 / 16 |
| Validation | V00–V07 | 8 | 4 / 4 |
| Held-out test | E00–E15 | 16 | 8 / 8 |

Keep all siblings, formats, probes, and derived examples within their family's
split. Require disjoint entity/pulse names and normalized assignment/update/query
compositions across these splits and against the old v1 families. Reuse v1's
construction checks; do not mutate its global protocol/splits or regenerate its
package. A new generator extension and frozen split manifest are future work.
Seal test facts and all test outputs until the budget, prompts, adaptation, and
checkpoint rules are fixed. Diagnostic Q00/Q01/Q02 cases enter none of these pools.

## 2. Choose one allowance and write notebooks once

Writer: unadapted `Qwen/Qwen3-4B-Instruct-2507`, revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, probe-writer-v1 instructions, v17
syntax/size validation, one repair, exact previous-valid-state fallback, greedy
generation, seed 0, cap 1024, context 8192, cached FP16 on A10/A10G. Retain errors,
empty states, imperfect content, repairs, and fallbacks. The writer sees no future
query, gold, options, scores, reader answer, or adapter.

Run C00–C03 at allowance 256 only: 32 chains × 14 writes = 448 primary writer
calls, at most 448 repairs. Measure all 64 P0/P12 snapshots with the actual pinned
tokenizer. **Choose B=128 if every snapshot fits 128; otherwise choose B=256.**
This rule uses rendered size alone and never uses which format wins or reader
accuracy. It selects a reasonably roomy main setting, not a proven capacity
boundary. Empty/fallback snapshots remain in the rule and their rates are reported.
Do not spend another budget sweep looking for a preferred result.

At the chosen B, run one writer chain for each world and format in R, V, and E.
Each chain has 14 writes and saves P0/P12. Freeze the literal text, counts,
public transcript, request links, and all hashes. Give the exact same snapshots to
both stock and adapted readers. Do not regenerate a notebook for the second
reader or for an inconvenient result. Stock and adapted inference have distinct
identities/caches. Write E notebooks only after all development/training decisions
are frozen. Full history and scripted controls never enter a primary writer path.

## 3. Label training/validation examples by supplied evidence

Retain all writer-produced R snapshots: 32 × 4 × 2 formats × 2 probes = **512**
examples, including every imperfect note. An annotator assigns a supported
destination or `insufficient information` using only the notebook and public task
rules, before seeing reader predictions. Store the full-public-history destination
separately for scoring, never as a hidden hint in the input.

| Notebook evidence for the query | Supervised reader target |
|---|---|
| One unambiguous current destination | That destination, even if the writer's note is factually wrong |
| Clear chronological replacement | Latest supported destination |
| Omitted assignment, null, revocation, or unresolved claim | Insufficient information |
| Incompatible current claims with no resolvable order | Insufficient information |

Teaching the reader to follow a self-consistent but wrong note is deliberate:
the reader is learning to use supplied evidence. Evaluation against the true
public-world answer still counts the resulting wrong prediction as a failure.
Do not train it to guess the hidden true answer when that answer is absent.
Record ambiguous annotations explicitly; resolve them before freezing targets,
without consulting model responses or dropping difficult examples.

Add one tagged scripted auxiliary example per R world/format: 256 examples.
Set mode `(family_index + world_index) % 4` to complete, target omitted, revoked
entity queried, or unresolved conflicting target claims, respectively. Thus each
format has 32 examples of each mode. Render complete/omitted/revoked notes from
public state using v1's `prose_note`/`json_note`; omission removes the main query
entity, and revocation changes the query to the revoked entity. For a conflict,
let d0 be the main world's destination and d1 the next destination in the fixed
amber/blue/green/violet cycle. In prose, omit the target from the ordinary note and
append: `Two unresolved current records give <target> as <d0> and <d1>. Neither
record is known to be later.` In JSON, replace the target's value by
`{"current_claims":["<d0>","<d1>"],"latest":null}` and apply the normal canonical
serializer. The conflict query remains the main entity; its label is abstention.
Complete examples use their supplied destination; all other auxiliary modes use
abstention. These are labeled synthetic controls, not writer-produced errors.
Total: **768 training examples,
384 per format**. Apply the same construction to V: 128 actual + 64 auxiliary =
**192 validation examples**, balanced by format. Report actual writer error and
abstention-target rates; synthetic examples do not establish observed writer drift.

## 4. One reader-adaptation method and selection rule

Use [LoRA](https://arxiv.org/abs/2106.09685) only on every reader `q_proj`/`v_proj`:
rank 8, alpha 16, dropout 0, frozen original weights and all other parameters.
Initialize the input low-rank matrix with seed-0 Kaiming uniform and the output
matrix at zero; use scale alpha/rank. Train full-vocabulary next-label
cross-entropy at the first assistant position, masking the entire prompt. Require
prefix-stable single-token A–E labels and no prompt truncation.

Use AdamW, learning rate 0.0001, betas (0.9, 0.999), epsilon 1e-8, weight decay
0, no scheduler, two epochs, microbatch 1, accumulation 16, max gradient norm 1,
seed 0, and a separately seeded shuffle per epoch. Use FP16 base computation,
FP32 trainable adapter/optimizer state, and dynamic loss scaling; unscale before
clipping. Abort on nonfinite values or overflow rather than silently dropping
examples. The existing torch installation can implement low-rank modules and the
training loop; no dependency installation or training framework is part of this
task. Hardware/memory compatibility remains unverified until an authorized check.

Save adapters after epoch 1 and epoch 2 (48 and 96 optimizer updates). Score all
192 validation examples after each epoch. Select the checkpoint with higher
equal-weighted prose/JSON evidence-target accuracy; ties select epoch 1. Freeze
that adapter and its hashes once. Report both validation results, per-format and
abstention metrics, loss, updates, measured tokens/times, and resource use. No
hyperparameter search, third epoch, repeated seed selection, or format-specific
adapter. This compares two checkpoints in one adaptation run; it does not measure
training-seed variability.

Verify adapter/base isolation before test: writer inference must load the original
base without reader adapters. Use separate reader and writer execution processes;
do not depend on an unverified toggle in a shared live model. Finite epoch loss and
successful adapter serialization are integrity checks, not stock-accuracy gates.

## 5. Matched held-out evaluation and interpretation

For each of the 16 E families, score all four siblings in both formats at P0 and
P12 with each reader. At P12 report the **four absolute accuracies** stock/prose,
stock/JSON, adapted/prose, adapted/JSON, each over 64 worlds. At P0 report the same
cells and P0-to-P12 changes. Carry forward P0 text at P12 by exact-input result
reuse within each reader, with explicit references and no extra inference.

Also score full history, no memory, sufficient prose, and sufficient JSON at P12
with each reader. They diagnose reading/organization and information demand; full
history is not an upper bound. Keep unparseable outputs, wrong labels, abstentions,
and all ordinary model mistakes in denominators. Technical failure or incomplete
evidence yields an incomplete study, not a zero-filled accuracy or a successful
gate. Do not select test worlds on stock-reader success.

For each family f average its four siblings and compute at P12:

```text
D_f = (A[adapted,JSON] - A[adapted,prose])
    - (A[stock,JSON]   - A[stock,prose])
```

Primary estimate: average of the updated-query and untouched-query stratum means.
Report all 16 D_f values and a stratified family percentile bootstrap, 10,000
resamples, seed 0, eight families with replacement within each stratum. Preserve
pairing for all cells/readers. This is a small exploratory study, conditional on
one training run; bootstrap coverage and broad population reliability are not
established. Additional compute should first add independently frozen test
families under a new allocation, rather than a second primary budget.

Before seeing test predictions, choose one sibling per test family from a seeded
annotation stream, balancing destinations twice within each eight-family stratum.
Annotate both formats at P0 and P12: 64 notebooks. Judge factual retention and the
supported reader answer blind to reader identity/predictions. Then inspect every
wrong P12 reader answer within this fixed sample: distinguish missing, incorrect,
stale, or unresolved notebook evidence from a supported fact the reader misuses.
If a fact was already absent at P0, do not attribute its absence to the twelve
later rewrites. Report inspected error counts and coverage; do not extrapolate
the sample's mechanism frequencies to all failures without qualification.

## 6. Stage limits and remaining implementation

| Stage | Fixed work ceiling |
|---|---|
| Reader diagnostic | 312 requests, one cached load, 1,800 s execution |
| Budget development | 448 primary + at most 448 repair generations |
| R/V/E notebook writing | 6,272 primary + at most 6,272 repair generations |
| Reader adaptation | 1,536 training-example forward/backward presentations; 96 optimizer updates |
| Checkpoint validation | 384 next-label scoring forwards |
| Final evaluation | At most 1,024 scoring forwards: 512 primary + 512 controls |

Writer totals are at most **13,440 generations**, each capped at 1,024 tokens;
this is a worst-case ceiling, not a throughput prediction. Annotation and data
construction add no inference. Exact-input reuse may lower physical reader
requests, but every logical assessment remains accounted for. Before authorizing
R/V/E writing or adaptation, measure C-family generation/chain time and actual
input/output tokens; freeze worker counts, stage wall-time caps, and cache/output
paths from those measurements. Do not infer writer runtime from Q0 reader speed.

The diagnostic CLI is runnable after its separate authorization. Split generation,
writer-only snapshot export, auxiliary templates/annotation storage, training,
adapter loading, and matched evaluation drivers are not implemented in this task;
they must implement the rules above and pass integrity checks before execution.
Resolve the answer interface after the diagnostic and select B by the fixed C
rule. Any change to this protocol, resource ceilings, or implementation receives a
new frozen manifest. No new task training or GPU work has run at this checkpoint.
