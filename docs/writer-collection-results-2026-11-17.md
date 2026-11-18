# Writer calibration GPU results — November 17, 2026

**Completed: select B=256.** All four calibration families passed raw-trace
audit. Their 64 literal P0/P12 snapshots were independently recounted using the
pinned Qwen tokenizer. The largest is 183 tokens, so the prespecified rule
(`128 iff every snapshot fits 128; otherwise 256`) selects **256**.

The selected corpus contains **448 primary writes + 2 repairs = 450 physical
calls**, with no fallbacks, empty snapshots, or reader inference. It includes
64 exact reader-input exports with evidence labels left unfilled. No R/V/E
notebook inference or fine-tuning occurred. Standing GPU authorization remains
in effect; there is no further team choice needed to finalize this allowance.

See the [collector implementation and recovery rules](writer-collection-v1.md),
[matched training protocol](matched-reader-training-v1.md), and
[verified evidence archive](../handoff/writer-collection-20261117-evidence.zip).

## Stored sizes and rewrites

Each family has four counterfactual worlds, two formats, and fourteen writes per
chain. P0 follows the assignment update/revocation; P12 follows twelve no-change
rewrites. The writer remains the unadapted pinned Qwen checkpoint and unchanged
`probe-writer-v1`/v17 acceptance, repair, and fallback policy.

| Family | Plain-text snapshot tokens | JSON snapshot tokens | Physical calls | P0/P12 texts changed, out of 8 chains |
|---|---:|---:|---:|---:|
| C00 | 44 | 60–61 | 112 | 0 |
| C01 | 44 | 60–183 | 112 | 2 |
| C02 | 43 | 60–87 | 112 | 0 |
| C03 | 43–52 | 54–102 | 114 | 2 |

There are 32 snapshots per format. Four of 32 chains changed bytes between P0 and
P12; that is a text-change count, not a factual-loss score. Both repairs were in
C03 plain-text chains at write index 7. Each primary output reached 1024 tokens
and was rejected as over budget; its single repair was accepted. All raw
candidates, measured counts, and routing events are retained.

## What the actual notebooks show

The condition named `prose` produced compact assignment lists, often `name=value`,
rather than paragraph prose. JSON used writer-selected nested schemas and
metadata. The later comparison therefore concerns these actual plain-text and
JSON notebooks; it should not claim to isolate narrative prose or identical
organization across formats.

Inspection of all saved snapshots found errors and irrelevant material that the
syntax/size validator correctly preserved:

- C00 plain text spells the nonqueried entity `gesor` as `gsor` already at P0,
  with the same error at P12. C01 changes `gefaz` to `ge fax` in plain text and
  `gefax` in JSON.
- C01 JSON includes conflicting/duplicated assignment sections, revision fields,
  and pulse metadata. In world 3 its `memory_token_count` field says `128`, while
  the actual note measures 165 tokens at P0 and 183 at P12. Model-written size
  claims are never used for validation or budget selection.
- C03 includes extra unknown-entity/pulse material in some plain-text notes and
  omits a nonqueried assignment from some JSON notes despite ample stored space.

These examples support retaining imperfect writer-produced notes for training
and labeling them by their supplied evidence. They do not establish reader
accuracy or general format superiority. B=256 is a development size choice,
not an established memory-pressure boundary. No stock-reader success threshold
was applied, and no reader predictions were used to select notes or budget.

## Preemptions, recovery, and accounting

Modal preempted the first worker during C02, after C00/C01 completed. A fresh
two-family recovery was also preempted during C02. In both cases the platform
replayed the input, and the exclusive output-directory guard refused before a
second model load. This is documented
[Modal preemption behavior](https://modal.com/docs/guide/preemption), distinct
from the configured zero scientific retries. The original interruptions,
subsequent `FileExistsError`s, and partial chains remain preserved.

Version 1.1 adds explicit recovery of completed, hash-pinned family units. Final
execution used separate C02/C03 jobs, one A10 each, followed by CPU-only
consolidation. Consolidation verified matching splits, checkpoint/settings,
writer/auditor dependencies, all source completion hashes, and literal copied
bytes. It recounted all 64 snapshots with the actual cached tokenizer and loaded
**zero model weights**. Completed C00/C01 were never regenerated. Incomplete C02
units from the interrupted attempts were retained unused; neither partial
family entered the budget decision.

| GPU attempt | Newly attempted calls | Completed responses | Collection wall seconds |
|---|---:|---:|---:|
| Original C00–C03, preempted | 324 | 323 | 885.648 |
| C02/C03 recovery, preempted | 50 | 49 | 127.631 |
| C02 single-family job | 112 | 112 | 279.287 |
| C03 single-family job | 114 | 114 | 349.894 |
| **Distinct total across attempts** | **600** | **598** | **1,642.460 summed** |

The two single-family jobs overlapped, so summed worker wall time is not elapsed
calendar time. Four cached FP16 weight loads took 22.936 seconds in total. The
CPU-only consolidation took 24.813 collection seconds (33.783 worker seconds),
with zero new inference requests. All five Apps are verified stopped with zero
tasks. No model or dependency downloads occurred.

| Scope | Known input tokens | Known output tokens | Synchronized generation seconds |
|---|---:|---:|---:|
| Selected complete corpus, 450 responses | 175,103 | 38,532 | 1,230.057 |
| All attempts, 598 completed responses | 230,614 | 48,954 | 1,567.066 |

Usage for the two interrupted requests is unknown, not zero-filled. The second
attempt's copied C00/C01 calls and consolidation copies are counted once in the
totals above. Generation timing excludes tokenization, transfer, and decode;
collection wall time includes loading, writing, commits, and audit work.

## Verification and reproduction

The full offline suite passed **559 tests, 26 skipped**, with one existing
TextWorldExpress Java cleanup warning. Focused collector/recovery checks passed
40 tests. Additional frozen transport checks passed: 10 recovery tests, 7
single-family tests, 2 tokenizer-only consolidation tests, and 4 physical-count
reconciliation tests. GPU traces exercise the actual cached backend and tokenizer.

The frozen consolidation launcher’s original collector incorrectly assumed 448
physical reused calls. Review caught this before that collector ran: repairs make
the actual total 450. A separate `read_only_collector.py` reconciles primary,
repair, response, and per-family physical counts. Its tests cover repairs; its
source hash and review note are preserved. No inference or scientific result was
changed to address this reporting check.

Scientific package digests:

```text
v1:   81d14435de8cd726f3f8b625b18b80161feafb106a168b18cccd4038e3326369
v1.1: 7eb254a9de27d8176c3d208c59c691e0b1b8e27b9a804e6ec79cb60660455a2d
```

After validating/restoring the evidence ZIP as described in
[handoff/README.md](../handoff/README.md), the final read-only report is:

```sh
.venv/bin/python -m game_memory.writer_collection report \
  artifacts/writer-collection-v1.1/consolidation-20261118T023742Z/collection-yc5m_dxy/download/calibration
```

The archive preserves both failed attempts, the two successful family jobs,
consolidation, source/split packages, manifests, raw calls/writes, independent
recounts, exports, audits, usage, errors, provider logs, and shutdown inventories.
Derived analysis and its script are under
`artifacts/writer-collection-v1.1/execution-20261118T024719Z/`.
These are completed/reserved attempt identities: do not relaunch them.

## Next stage

Use **B=256** to collect R00–R31 and V00–V07 with the frozen writer, preserving
family units independently. That produces 512 actual training and 128 actual
validation snapshots. Assign evidence-supported labels, including abstention for
missing/unresolved facts, then implement the protocol's reader-only LoRA and
checkpoint selection. Both readers must receive each identical frozen notebook.
The E00–E15 split stays sealed until development/training decisions are fixed.
