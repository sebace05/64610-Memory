# Reader study handoff

Repository: `sebace05/64610-Memory`. Branch: `codex/modal-calibration-handoff`.
Results and raw evidence are pushed through commit `7cb464c`.

Our question: does reader fine-tuning change how well Qwen uses model-written
plain-text versus JSON memory? Keep the writer frozen and give both readers
identical saved notes. We are checking the stock reader before training.

The task has eight entities, four destinations, an update and a revocation.
Each family has four related answer variants. P0 is after the update;
P12 is after twelve further rewrites.

The completed study tested 160 fresh development families with correct, complete
notes. Earlier Q00 ablations showed name-specific effects, but no general fix.

| Names | Plain text accuracy | JSON accuracy |
|---|---:|---:|
| Current names | 97.97% | 98.28% |
| Numbered IDs | 99.53% | 98.28% |

IDs fixed 11 JSON errors and introduced 11 others. Overall benefit: 0.78 percentage
points, 95% interval −0.39 to +2.11. The frozen 2-point rule calls this
**inconclusive**; keep the generator. Every wrong answer had the correct fact in
its note; independent scoring checks matched exactly.

Writer calibration saved **64 notes from C00–C03**, both formats at P0/P12.
The chosen allowance is **B=256 tokens**, largest note 183. Some notes contain
spelling errors, omissions or conflicting claims. `prose` produced assignment
lists. Scoring these notes, R/V/E collection and LoRA have not run.

Latest checks: **599 passed, 26 skipped**; transport: 10 passed. All completed
experiment Apps are stopped.

Read the [base-rate results](reader-base-rate-results-2026-11-17.md),
[writer results](writer-collection-results-2026-11-17.md), and
[matched training protocol](matched-reader-training-v1.md). README's standing
GPU authorization supersedes older authorization wording.

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

Implement and test stock-reader scoring of the 64 saved C00–C03 snapshots.
Reuse game_memory/writer_collection.py's exports/audit, memory_probe.py's prompts,
transformers_model.py's A–E scoring and the diagnostic/Modal helpers. Use the
pinned Qwen3-4B-Instruct-2507, FP16, actual NVIDIA A10 and unchanged reader inputs.

Before viewing predictions, separately label each note's supported destination
or insufficient information for missing/unresolved claims. Preserve the exports.
Report total task accuracy and agreement with note evidence for both formats
at P0/P12. Count all ordinary errors; inspect writer mistakes versus reader
mistakes. This is exploratory: four families. The old 15/16 gate does not apply.

Keep the generator. Leave held-out E families unused. Use a fresh, bounded run,
not a completed launcher. Run relevant tests with .venv/bin/python. Save scores,
usage, timing and shutdown evidence. GPU authorization is in README; check
workspace/cache access rather than assuming old machine paths work.

Push changes and a short report to this branch. Recommend whether LoRA is worth
doing next using the matched-training protocol.
```
