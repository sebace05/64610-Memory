# Stock reader on saved writer notes v1

Frozen before inference. Evaluate the existing 64 C00–C03 B=256 snapshots with
stock Qwen3-4B-Instruct-2507. Keep every literal exported reader prompt and note;
do not regenerate notes, change names, train weights, or use R/V/E families.
P0 is immediately after the update/revocation; P12 follows twelve no-change
rewrites. This is a four-family development baseline, not held-out evaluation.

Use the completed writer v1.1 consolidation, scientific manifest
`7eb254a9de27d8176c3d208c59c691e0b1b8e27b9a804e6ec79cb60660455a2d`,
completion SHA-256
`54757eb5509fd97b7c39f6c6178ff8d9c27ab3162a04f750625e5265107d6376`.
The existing writer auditor verifies raw writes, routing, literal snapshots and
exports before the new package copies them as read-only provenance.

Before viewing reader predictions, annotate all 64 notes from supplied text and
public rules. Save the query, notebook hash, supported destination, exact evidence
quotes and rationale separately from the untouched exports. An unambiguous
assignment supports its stated destination even if it is wrong in the world.
Missing, revoked or unresolved assignments support insufficient information.
The original true task answer is a separate scoring target and never an input
hint. Annotation is manual evidence review; substring checks verify quote
provenance but do not automatically establish semantic correctness.

All queried bindings in these 64 notes were reviewed and found explicit and
unambiguous before inference. Duplicated C01 JSON queried bindings agree; its
conflicts concern a different entity. Other spelling/omission errors remain in
the supplied notes. These labels therefore test the reader on the queried facts,
not factual correctness of every entity. Annotation SHA-256:
`a028c988c9288a74770afa8c28c6cc3d51178c16dda4845fca153308c08c82a1`.

Use unchanged restricted A–E scoring, the pinned model/tokenizer revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, FP16, seed 0, context 8192, and
actual NVIDIA A10. Reject a different device before tokenizer/weights. Use the
existing cached runtime only. No downloads, writing or autoregressive generation.
Standing GPU authorization is in README.

Run 64 primary forwards in the original family/export order. Preserve repeated
inputs as separate physical forwards, so P0/P12 predictions are observed rather
than reused. After all primary cases, run 64 independent reference forwards over
the same inputs, then 64 production repeats. Hard ceiling **192 forwards**, one
cached weight load, one A10, startup 600 s, execution 900 s, soft deadline 600 s,
zero configured retries. Each primary family and the check unit is durably
committed. Never resubmit a reserved attempt. Stop on independent scoring
disagreement; preserve raw evidence and the failing exit status. Repeat
differences remain reported observations.

Report all four format/probe task accuracies out of 16, agreement with evidence
labels, queried-evidence correctness, per-family counts, JSON-minus-plain-text
gaps and P0/P12 changes. Inspect every wrong answer. Count ordinary wrong answers
and abstentions in total accuracy. Separate errors on correct queried evidence
from writer-evidence errors; retain cases where both disagree. Technical failure
means an incomplete study, not zero-filled accuracy. Do not apply the old 15/16
gate or select notes based on reader success.

With four development families, report counts and family results descriptively;
do not infer population format superiority or trigger training from a threshold.
The actual `prose` notes are assignment lists, JSON schemas vary, and B=256 is
roomy (maximum observed note: 183 tokens). Record exact prompts/logits, tokenizer
checks, input/decision tokens, synchronized forward time, study/worker wall time,
and verified App shutdown. Reader usage excludes earlier copied writer calls.

Implementation reuses the writer auditor, reader prompts, logged inference,
independent scoring, and base-rate unit audit/budget helpers. Preparation and
reporting are CPU-only. Run tests using `.venv/bin/python`; read-only reporting
is `python -m game_memory.stock_memory_eval report RUN` (redirect outside RUN).
