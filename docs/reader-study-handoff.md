# Reader study handoff

Repository: `sebace05/64610-Memory`. Branch: `codex/modal-calibration-handoff`.

Our question: does reader fine-tuning change how well Qwen uses model-written
plain-text versus JSON memory? Keep the writer frozen and give both readers
identical saved notes. The stock baseline is now complete; training has not run.

The task has eight entities, four destinations, an update and a revocation.
Each family has four related answer variants. P0 is after the update;
P12 is after twelve further rewrites.

Stock Qwen on the 64 saved C00–C03 writer notes, B=256:

| Memory | P0 accuracy | P12 accuracy |
|---|---:|---:|
| Plain text | 14/16 — 87.5% | 14/16 — 87.5% |
| JSON | 15/16 — 93.75% | 15/16 — 93.75% |

All six wrong answer instances concern `dopum` in C01, despite its correct fact
being explicit in the note. Other families score 4/4 in each cell. Every queried
fact survives to P12; other entities still have writer errors. Four development
families do not establish a general format ranking. Independent checks matched.

The largest note is 183 of 256 allowed tokens; `prose` produced assignment lists.
The earlier 160-family scripted-note study scored about 98% in both formats;
it used different families, notes and hardware. Numbered IDs did not justify
changing the generator. R/V/E collection and LoRA have not run.

Latest checks: **620 passed, 26 skipped**; transport: 10 passed. All completed
experiment Apps are stopped.

Read the [new baseline results](stock-memory-eval-results-2026-11-18.md),
[writer results](writer-collection-results-2026-11-17.md), and
[matched training protocol](matched-reader-training-v1.md). The baseline and
future adapted-reader comparison use actual **NVIDIA A10G**, fixed in
[v1.1 before inference](stock-memory-eval-v1.1.md). Earlier A10-only placements
made zero model calls. README's GPU authorization supersedes older wording.

Raw evidence is in committed ZIPs. Follow
[handoff/README.md](../handoff/README.md) to verify and restore only their
`artifacts/` contents. The writer inputs are `C00`–`C03`'s `reader-inputs.jsonl`
and `snapshots.jsonl` under:

```text
artifacts/writer-collection-v1.1/consolidation-20261118T023742Z/collection-yc5m_dxy/download/calibration/
```

Weights and credentials are not in Git; check your Modal workspace/cache access.

Copy this prompt into your agent:

```text
Continue on sebace05/64610-Memory, branch codex/modal-calibration-handoff.
Read docs/reader-study-handoff.md and its linked results/protocol first.

The C00–C03 stock baseline is completed. Next implement writer collection for
R00–R31 training and V00–V07 validation at B=256, using the frozen splits and
writer_collection.write_family. The current calibration CLI only runs C; reuse
its helpers for this next stage. Keep E00–E15 held out.

Generate each writer chain once; save literal P0/P12 notebooks and reader inputs.
Label notes by supplied evidence before reader predictions. Missing/unresolved
facts support insufficient information; total task accuracy still uses the true
task answer and counts ordinary errors. Preserve completed families.

Record stock validation performance before adaptation. Use the pinned
Qwen3-4B-Instruct-2507, FP16, actual A10G and existing A–E scorer. Keep identical notes for
both readers and the writer free of reader adapters. The planned adaptation is
supervised reader LoRA; its implementation remains future work.

Use fresh bounded runs, relevant offline tests with .venv/bin/python, and preserve
raw outputs, usage, timing and shutdown proof. GPU authorization is in README.
Push changes and a short progress/results report to this branch.
```
