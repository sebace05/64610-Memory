# Writer collection v1.1

This implements the first data-collection stage of the
[matched reader-training protocol](matched-reader-training-v1.md). Standing GPU
authorization is recorded in the [README](../README.md). The protocol document's
original implementation/authorization status is historical; its scientific rules
remain fixed. No reader training driver is implemented here.

`game_memory.writer_collection` freezes 60 fresh families under namespace
`matched-reader-training-v1`, seed 0: C00–C03 for budget development, R00–R31 for
training, V00–V07 for validation, and E00–E15 for held-out testing. Preparation
checks disjoint entity/pulse names and normalized compositions against the old
v1 families and across new splits. It freezes every split and an allowlisted
source archive. Test facts are sealed, not printed or used for development.

The new family builder takes explicit RNGs. This small copy of v1's construction
is necessary because v1 hardcodes its namespace/allocation; a parity test checks
identical inputs yield identical families. Frozen v1 code and evidence are unchanged.

## Commands and scope

Run from the repository root, with a fresh destination:

```sh
.venv/bin/python -m game_memory.writer_collection prepare \
  --output-dir artifacts/writer-collection-v1/package
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_writer_collection.py
```

Preparation and reporting import no inference libraries. For an already verified
cached A10/A10G environment, the GPU entrypoint is:

```sh
/opt/memory/.venv/bin/python -m game_memory.writer_collection calibrate \
  --package FROZEN_PACKAGE --output-dir FRESH_RESULTS
.venv/bin/python -m game_memory.writer_collection report COLLECTED_RESULTS
```

The Modal pilot uses a frozen attempt-specific packet, the existing pinned image,
a read-only model cache, and the existing results volume. It calls `calibrate`
with `results.commit` so each family is durable before the next starts. The
packet's launcher supports `verify`, `launch`, `status`, `collect`, and `shutdown`.
It records a submission reservation before SDK/App construction and refuses
resubmission. Query the saved call after a client timeout. Preserve failed or
partial outputs and use a new, versioned attempt for any changed implementation.

The only GPU collection implemented by this checkpoint is **C00–C03 at B=256**:
four worlds × two formats × fourteen writes per family, or 448 primary requests
and at most 448 repairs. One cached FP16 Qwen weight load, one A10/A10G, zero
automatic retries; startup ceiling 600 seconds, function ceiling 7200 seconds,
soft collection deadline 6900 seconds, physical request ceiling 896. No model
downloads, reader scoring, R/V/E writing, or fine-tuning occurs in this pilot.

The writer remains the pinned unadapted Qwen checkpoint, `probe-writer-v1`, greedy
cap 1024, context 8192, seed 0. It uses v17 syntax/size checks, one repair and exact
previous-valid-state fallback. No semantic correction or hidden-world labels
enter writer prompts. The backend checks every actual prompt for overflow.

## Outputs and decision

Each family keeps raw `events.jsonl`, all 112 writes, empty assessments, usage,
completion hashes, and 16 P0/P12 snapshots. Each snapshot contains the literal
rendered notebook, hash, measured token count, identity and originating write
index. The old auditor independently reconstructs primary/repair acceptance and
fallback routing. The new auditor requires complete writer/snapshot coverage and
checks each exported byte/count against the source write.

`reader-inputs.jsonl` exports the exact reader messages for each snapshot and
query/options, with notebook/prompt hashes and `supported_label: null`. It invokes
no reader and supplies no supervision from the hidden true answer. Later both
stock and adapted readers must consume these same frozen inputs. Annotation by
notebook evidence remains required before training; a label must not be guessed
from the public-world answer when a note is incomplete or contradictory.

After all four families pass audit, independently recount all **64** snapshots
with the cached pinned tokenizer. Choose **B=128 iff every snapshot fits 128;
otherwise B=256**. Empty/fallback states stay in this rule and are reported.
No accuracy or factual-quality result selects the allowance. A partial run or
recount mismatch yields no budget decision. Fixture runs are explicitly marked
synthetic and cannot establish Qwen behavior.

Reporting reconciles raw requests/responses, measured tokens, generation time,
collection wall time, repairs, fallbacks, empty states and the fixed budget rule.
It establishes neither reader accuracy nor factual retention. The next stages
are R/V notebook collection at the selected B, evidence-based labeling, and a
separate reader-only LoRA implementation. E data remain sealed until the
development and training decisions are frozen.

## Recovery after the observed Modal preemption

The first writer pilot was preempted during C02 after completing C00 and C01.
Modal replayed the input despite `retries=0`; the exclusive output guard refused
that replay before source/model work. Both the interruption and replay error are
preserved. [Modal documents this platform behavior](https://modal.com/docs/guide/preemption).
The original attempt and its settings remain immutable.

Version 1.1 adds only explicit recovery of **completed** family units into a new
attempt. A frozen transport plan lists each source directory, original scientific
manifest digest and completion-file hash. Before weights, re-audit each source and
require the identical calibration split, model/writer settings, and unchanged
writer/auditor dependencies. Copy the entire unit byte-for-byte; never read from
or append to an incomplete chain. Save lineage, then generate only missing whole
families, with a reduced request ceiling of 224 per missing family. Recount all
64 final snapshots using the actual pinned tokenizer before applying the same rule.

The recovered corpus contains 448 primary writer requests across its source
attempts; copied calls are not new inference. Status/reporting distinguish reused
requests from newly attempted GPU calls. Account for the interrupted source's
unused partial C02 calls separately in the execution report. Recovery neither
chooses notes by quality nor reruns a completed family. No automatic scientific
retry or resubmission of an existing attempt is enabled.
