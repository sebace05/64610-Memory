# Reader diagnostic v1

Status: implementation and offline tests only. No new inference, downloads,
training, deployment, or continuation of memory-probe-v1 is authorized. Code:
[reader_diagnostic.py](../game_memory/reader_diagnostic.py). The matched training
comparison is specified separately in [its protocol](matched-reader-training-v1.md).

## Fixed cases and interventions

Use Q00 siblings 0–3 as the focal cases. Controls are Q01 siblings 0–1
(untouched-query) and Q02 siblings 2–3 (updated-query). These controls were correct
with both sufficient formats in the saved run. Across the four controls, gold
destinations are amber, blue, green, and violet. These are selected development
cases, not a fresh validation or test sample.

For each of eight worlds, render sufficient prose and JSON in seven conditions:

| Condition | Entity order | Answer-option order | Comparison |
|---|---|---|---|
| original | Exact historical prose order / canonical JSON order | Historical | Reproduce v1 input |
| matched_lexical | Lexical, identical across formats | Historical | Entity-order change from original |
| matched_reverse | Reverse lexical, identical across formats | Historical | Entity-order change from matched_lexical |
| options_rotate_1 through _4 | Matched lexical | Four cyclic rotations | Option-order changes from matched_lexical |

Every condition retains all eight assignments, revocation, query, reader system
instruction, public rules, and destination vocabulary. Gold answers do not choose
the permutation. The five option positions, including abstention, rotate together.
In Q00 this moves green from D through C, B, A, and E. Entity order and option
order never change together within an intended contrast. JSON order variants
deliberately preserve insertion order for this diagnostic; the production JSON
writer and its canonical sorter remain unchanged.

There are **112 logical prompts, 104 distinct prompts**. Original JSON equals
matched-lexical JSON and is reused only on exact complete-message identity.

## Historical evidence versus reconstruction

With `--historical-unit`, preparation checks the saved events/assessments SHA-256
values, invokes the existing real-evidence qualification audit, and requires every
original selected message to equal the recorded request. The original gate is
expected to fail; auditing it does not rerun it. Previously correct controls are
checked against their actual recorded responses. The package records
`hash_verified_historical_replay` and the source hashes.

Those files are Git-ignored. Without them, preparation uses the unchanged v1
generator and prompts and explicitly records
`reconstructed_v1_inputs_not_verified_historical_replay`; historical correctness
is unknown in the prepared rows. Reconstruction is useful for software preparation
but is not evidence that the original run was independently replayed. A missing
or altered explicitly supplied historical directory is an error, never an implicit
fallback to reconstruction. No historical files are edited.

## Three answer methods, one frozen model

1. **Restricted:** unchanged `TransformersModel.score_choices`, A–E argmax.
2. **Reference:** independently encode the chat prefix, validate labels, construct
   input IDs/mask, perform a second raw forward with `use_cache=False`, and select
   the largest final-position candidate logit. It does not call production
   scoring/selection helpers. It shares the frozen weights, tokenizer, and
   libraries, so agreement does not exclude every library/kernel bug. Preserve
   candidate logits, input-ID hash, and the unrestricted vocabulary's top token.
3. **Generated:** unchanged greedy generation on exactly the same messages,
   capped at 32 new tokens. After trimming whitespace, accept only uppercase
   A–E with an optional final period. All other outputs, including explanatory
   text or a bare destination, are unparseable. Preserve them verbatim and report
   parse failures separately; do not change extraction after viewing results.

Restricted/reference comparison requires identical label token IDs, rendered
prompt hashes, input lengths, selected labels, and candidate logits within
absolute tolerance 0.0625 (zero relative tolerance). Ties choose the first label.
Any discrepancy stops the attempt before its next generation; raw scores remain
available. This is an implementation-integrity check, not an accuracy threshold.
Differences from generated answers are diagnostic outcomes and do not fail it.

The existing cached A10/A10G runtime, pinned Qwen revision, FP16, seed 0,
context 8192, and chat template are retained. Cached-tokenizer checks precede
the single weight load. Reference scoring shares that load. There are no writer
calls, warm-ups, repairs, or hidden diagnostic inference calls.

**Ceilings:** 104 production forwards + 104 reference forwards + 104 greedy
generations = **312 requests**; at most **3,328 generated tokens**, plus 208
accounted decision tokens. Tokenizer-only preflight performs no model forward.
Proposed GPU execution cap: 1,800 seconds, soft deadline 1,740 seconds checked
before each request, zero retries; a future launcher should cap startup at 600
seconds. The soft deadline cannot interrupt an in-flight operation. No runtime
estimate is claimed from these ceilings.

## Offline preparation and future worker command

From this checkout, without loading a tokenizer or model:

```sh
.venv/bin/python -m game_memory.reader_diagnostic prepare \
  --output-dir artifacts/reader-diagnostic-v1/package \
  --historical-unit artifacts/memory-probe-v1/s1-preparation-20261117T200538Z/collection-bdm5ddqa/download/stage/qualification
```

In a clean checkout, omit `--historical-unit` to obtain explicitly reconstructed
inputs. Preparation creates a fresh immutable directory with cases, manifest,
source hashes/archive, counts, and an authorization template. It refuses an
existing directory. The template's warning prefix is rejected as authorization.

**Proposed GPU worker entrypoint, NOT executed or authorized:** in an already
provisioned matching A10/A10G environment, with the existing read-only cache at
`/cache/huggingface` and a separately reviewed source/package transfer:

```sh
timeout --signal=TERM --kill-after=30s 1800s \
  /opt/memory/.venv/bin/python -m game_memory.reader_diagnostic run \
  --package /results/reader-diagnostic-v1/package \
  --output-dir /results/reader-diagnostic-v1/attempt-001 \
  --authorization /results/reader-diagnostic-v1/authorization.txt
```

The authorization must name the exact manifest digest and request ceiling; it
must be separately supplied after approval, not copied by this preparation task.
The caller must capture startup stdout/stderr and the original process/timeout
exit status in fresh files, collect all partial evidence, commit the results
volume, and verify shutdown of only that attempt's App. The worker fsyncs local
files; it does not itself perform a Modal volume commit. No new Modal deployment
wrapper is included. The old v1 S1 launcher is hardcoded to its ended study and
must not be used to submit this diagnostic. Transfer/transport review and
execution authorization remain prerequisites for a cloud launch.

Read-only reporting, with stdout kept outside the input directory:

```sh
.venv/bin/python -m game_memory.reader_diagnostic report PATH_TO_COLLECTED_ATTEMPT
```

The report contains query, gold destination, option mapping, selected letter and
destination, raw answer, parse status, format/order variant, original-correctness
provenance, request links/reuse, per-cell counts, measured usage, and timing.
Both forward methods count one decision token, not generated text. Incomplete
attempts stay incomplete; failures retain their underlying exit status and known
usage. Completed reports check hashes, coverage, labels, and request/response
mapping. Synthetic tests are explicitly marked as fixtures.

Inspect whether a prediction follows a letter or a destination under rotation,
whether matching entity order changes it, and whether generation agrees with
restricted scoring. These observations can motivate the final reader interface;
they do not identify Qwen's internal cause or establish general format accuracy.
First-token versus generated-answer differences have precedent in
[Wang et al. (2024)](https://aclanthology.org/2024.findings-acl.441/), not a proven
explanation of this run.

## Offline verification checkpoint

The November 17 full offline suite passed **518 tests with 26 skips** in 23.55 s
(exit 0), using `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q -rs`.
The suite ran outside the filesystem/network sandbox so the local Java gateway
could start. Skips include the new random-weight reference-forward check because
local torch is absent, existing optional model-adapter checks, and a Java 9+
logging regression. They remain unverified checks, not passes. No dependencies
were installed. Pure fixture tests cover order/fact invariance, exact historical
prompts when evidence is present, reconstruction provenance, extraction,
independent-score disagreement, partial failures, accounting, reporting, and
authorization rejection. Actual cached-Qwen preflight and diagnostic inference
remain unexecuted.
