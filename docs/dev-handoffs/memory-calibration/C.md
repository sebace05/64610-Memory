# Role C — READY

Contract: `memory-development-contract-v1`. Role C has stopped editing its files;
role D may begin integration. No contract amendments or component API changes.

Files and behavior:

- `game_memory/summarize_diagnostics.py`: retains independent per-condition audit
  and mixed-configuration rejection. Adds mutually exclusive primary/repaired/
  previous-state fallback outcomes, unknown legacy outcomes, additional accepted
  empty writes, per-update stored counts/utilization, syntax/size rejection
  reasons, measurable candidate sizes distinct from raw output tokens, narrow
  offline format-adherence flags, score, usage completeness, purpose accounting
  including failed calls, generation-limit hits, loading and unknown launch status.
  Checks header/result protocol agreement (legacy missing/missing is readable)
  and requires exactly one final outcome for v17 updates.
- `game_memory/analyze_memory_budget.py`: directly tested JSON-compatible analysis;
  validates shared comparison schema and serialized model/game config fields;
  audits each condition separately; checks exact schema-2 pilot identities,
  episode settings/model/runtime/source/protocol, folds and planned Cartesian
  coverage. Flags missing/partial/error/duplicate/unplanned/orphan/unaudited cells.
  Losses count as zero; invalid grids get no primary contrast. Computes numeric
  high-minus-low success by format/price and JSON-minus-prose interaction over
  matched seeds. Thin JSON/CSV/Markdown stdout CLI returns nonzero for invalid
  grids. CSV includes validity/issues and detailed evidence as JSON fields.
  `summarize_annotation` counts explicitly supplied human labels only.
- `tests/test_diagnostic_summary.py`, `tests/test_analyze_memory_budget.py`:
  hand-calculated synthetic provenance/grid/failure cases and backward-reading
  checks against preserved reproduction, with optional skips when artifacts
  are not distributed. No skips occurred here.
- `tests/fixtures/memory_annotations/development-seeds.json`,
  `docs/memory-annotation-guide.md`: seed-0/1 public-evidence recipe checklists,
  event IDs and exact quotes; reset/taking/preparation/pre-terminal checkpoints;
  explicit unreached preparation checkpoint for seed 1; supported, omitted,
  contradictory, invented and unknown examples. Empty notes get zero retention
  and undefined claim accuracy. Examples are labeled preserved v16 diagnostics,
  never v17 comparison evidence or online inputs.

Checks (project Python; no GPU/Java needed):

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_diagnostic_summary.py tests/test_analyze_memory_budget.py`
  — **34 passed in 0.39s**, exit 0; no skips/failures. Earlier focused runs also
  passed while coverage grew (26, 28, then 34 tests).
- `.venv/bin/python -m game_memory.analyze_memory_budget --help` — exit 0.
- `git diff --check -- game_memory/summarize_diagnostics.py tests/test_diagnostic_summary.py`
  — exit 0; final owned-file whitespace check also passed.
- Full suite deliberately left to D after combined code is stable.

Integration/interface compliance:

- Consumes D's section-5 schema unchanged. D's IN_PROGRESS note confirms producer
  implementation and protocol fields in headers/results. All new comparisons
  require protocol evidence; legacy per-condition reports remain backward-readable.
- No changes to writer/actor/runner/CLI/preflight or their owned tests/docs.
  No component methods, event strings, prompts or rendering identifiers changed.
- Detailed syntax reasons remain recorded; unknown historical semantic reasons
  are separate from syntax counts. v16 prose programmed fallbacks remain unknown
  under the new previous-state outcome classification rather than reclassified.
- Candidate sizes use recorded accepted memory counts or explicit over-budget
  counts only. Invalid JSON rendered size is null. No tokenizer recount/loading.
- Launcher exit status remains null unless separately investigated; episode
  completion never implies exit zero. Underlying logs/artifacts are untouched.

Limits:

Synthetic tests establish evidence accounting, identity boundaries and contrast
arithmetic, not useful Qwen writing/reading, gameplay competence, factual-label
reliability, binding memory pressure or a format advantage. Annotation judgments
are manual examples with evidence, not an automatic fact oracle. Prose adherence
is intentionally narrow: obvious JSON-shaped outputs can be flagged; other
cases remain unknown. Malformed logs remain explicit audit issues; contrasts
are withheld rather than estimating from the surviving subset. No live comparison
manifest, selected allowances or sample size was invented.

No GPU job, real-model inference/tuning, model/tokenizer download, historical
artifact modification, worktree, subagent, staging or commit occurred.
