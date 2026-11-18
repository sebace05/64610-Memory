# Evidence for the Modal handoff

**November 17 name/distractor ablation:**
[`name-ablation-20261117-evidence.zip`](name-ablation-20261117-evidence.zip)
contains the fixed 280-forward diagnostic, actual name tokenization, raw scores,
independent baseline checks/repeats, reports, usage and shutdown evidence. Read
[the results](../docs/name-ablation-results-2026-11-17.md) first. Validate the
adjacent SHA-256, ZIP CRCs and every entry against
`handoff/name-ablation-transfer-manifest.json` inside the ZIP. Restore only
`artifacts/` entries after path/hash checks; skip identical files and stop on
conflicts. Never overlay source or overwrite evidence. No weights/environments
are included. The App is verified stopped with zero tasks.

**November 17 writer calibration:**
[`writer-collection-20261117-evidence.zip`](writer-collection-20261117-evidence.zip)
contains the two interrupted writer attempts, successful C02/C03 family jobs,
CPU-only consolidation, frozen source/splits, raw writes/calls, exact notebook
exports, tokenizer recounts, audits, accounting and shutdown evidence. The
[results report](../docs/writer-collection-results-2026-11-17.md) records B=256.
The archive contains no model weights, environments or credentials.

Before restoration, verify the adjacent SHA-256, ZIP CRCs and every entry against
`handoff/writer-collection-transfer-manifest.json` inside the ZIP. Restore only
`artifacts/` entries after validating all paths and bytes; skip identical files
and stop on conflicts. Never overwrite evidence or overlay archived source onto
the live repository. New test-family facts remain sealed for held-out evaluation.
All five writer/consolidation Apps are verified stopped.

**November 17 reader diagnostic:**
[`reader-diagnostic-20261117-evidence.zip`](reader-diagnostic-20261117-evidence.zip)
contains the failed and corrected diagnostic attempts plus the prior
memory-probe-v1 evidence used for historical prompt verification. Read
[the results](../docs/reader-diagnostic-results-2026-11-17.md) first. The archive
contains source packages, manifests, raw requests/scores/answers, accounting,
authorization records, errors, audits, and shutdown inventories. It contains no
model weights or environments. GPU runs have standing user authorization.

Before restoring it, verify the adjacent SHA-256, ZIP CRCs, and every entry against
`handoff/reader-diagnostic-transfer-manifest.json` inside the archive. Restore only
the `artifacts/` entries: reject absolute/parent-traversal paths, validate the full
selection first, skip byte-identical existing files, and stop on any conflict.
Never overwrite evidence or overlay archived source onto the live repository.
The included per-file manifest describes this selected transfer; older preservation
ledgers may also reference CookingWorld files outside the selection.

The source and narrative are committed normally; raw artifacts stay Git-ignored
after restoration. Both diagnostic Apps were verified stopped with zero tasks.

## Historical November 16 handoff

**Laptop continuation, November 16:** the originally requested launcher is now
implemented and the single A10 JSON seed-1 pilot succeeded. See
[`docs/modal-calibration.md`](../docs/modal-calibration.md) for the current
workflow and [the pilot report](../docs/modal-pilot-2026-11-16.md) for results.
The archive and original handoff requirements below remain historical evidence.

Clone branch `codex/modal-calibration-handoff` for the current implementation
and instructions. Start with `docs/modal-laptop-setup.md`, then provide
`docs/codex-modal-handoff-prompt.md` to the laptop Codex agent.

`codex-modal-handoff-20261116.zip` is the original, verified pre-commit transfer
snapshot (about 2.7 MB). Its SHA-256 is in the adjacent `.zip.sha256` file.
It contains the actual formerly uncommitted source and the Git-ignored raw
calibration evidence, reports, earlier evidence ZIPs and historical test fixtures.
It contains no environments, model weights, Git internals or credentials.

The old `739e72d` commit and dirty status inside the archive are historical
provenance. The current branch's committed source/docs are authoritative;
do not overlay the archived source/docs onto them or reset to that old commit.
The experimental Python source remains at frozen Linux digest
`f4c9b85a1594d02e3b2ac6ae225a4e82b9b0566ab6b545cc93d055d5cd860afb`.
Committing naturally changes Git SHA/dirty metadata without changing that digest.

Before editing or running experiments, the receiving agent should:

1. Check the archive against its adjacent SHA-256 and run ZIP CRC validation.
2. Read `handoff/transfer-manifest.json` **inside the ZIP** and verify its
   per-file hashes against the archived bytes. These hashes describe the
   archived snapshot, not the branch's subsequently updated setup docs.
3. Restore only entries under `artifacts/` into the checkout, using the Python
   standard library. Validate the full selection before writing: skip identical
   existing files and stop on any conflicting content; never overwrite results.
   Reject absolute or parent-traversal paths. No additional extraction framework
   is necessary for this one-off restoration.
4. Confirm that the latest summary and historical fixtures exist at:
   `artifacts/qwen-calibration-v17-v30-20261116T154805Z/calibration-summary-after-retry-2.json`
   and `artifacts/reproduction-v29-v16-20261115/`.

Raw artifacts remain ignored by Git after extraction. Five local episodes
completed; JSON seed 1 never started because two separate model loads were OOM
killed. Both failed attempts and the original interrupted prose trace are
preserved. The source, outcomes, annotations and host-disk diagnosis are also
described in the committed `docs/memory-calibration-*.md` reports.

There is no implemented Modal launcher or deployment yet. The handoff prompt
asks the receiving agent to implement and validate the launcher, then run one
separately labeled cloud pilot with explicit authorization and fixed settings.
