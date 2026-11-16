# Role A handoff

Status: READY

Contract: memory-development-contract-v1. Role A has stopped editing its files.
No conflicting v17 implementation was present at the initial version check.

Files changed:

- `game_memory/memory.py`: p1-memory-v17/version 17. Shared substantive
  prose/JSON instructions let the model retain, compress, or omit useful supported
  recipe, inventory, and progress information. Only syntax and exact rendered
  size govern acceptance. One logged model repair; exact previous serialized
  state on failure, including empty initialization. Removed v16 semantic checks,
  calculated factual repair hints, and public-fact fallback builders.
- `tests/test_memory.py`: explicitly retired the v16 semantic-policy tests;
  added acceptance of omission, factual error, deliberate emptiness, no initial
  recipe injection, exact noncanonical predecessor fallback, and metadata checks.
  Existing syntax, Unicode, numeric fidelity, bounds, isolation, error propagation,
  repair, and logged accounting checks remain.
- `tests/test_memory_integration.py`: added real-simulator/fake-model checks for
  accepted empty and failed initial writes, empty actor context, accounting for
  both failed attempts, and no write after a terminal action.
- `docs/p1-memory.md`: describes the implemented policy and retirement boundary.

Validation:

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_memory.py tests/test_memory_integration.py -x`
  with sandbox escalation for the local Java gateway: **132 passed in 7.19s**,
  exit 0; no skips or failures.
- Two earlier restricted invocations of the same focused files (without `-x`)
  stalled in simulator execution; the second showed one failure marker without
  a completed traceback. Both were interrupted, exit 130. The gateway-enabled
  run above completed all tests successfully; no checks were weakened.
- `git diff --check -- game_memory/memory.py tests/test_memory.py tests/test_memory_integration.py docs/p1-memory.md docs/dev-handoffs/memory-calibration/A.md`: passed.

Compliance and integration:

- Public interfaces unchanged. Metadata declares
  `syntax_and_size_one_repair_previous_state_v1`, `semantic_validation: none`,
  `fallback: previous_valid_memory`, `max_repairs: 1`, `is_fake: false`, real
  implementation names, and unchanged `p1-render-v2`/JSON policy.
- Existing event names and detailed syntax/numeric reasons retained; no semantic
  rejection or public-evidence fallback events remain. Exactly one final outcome
  per successful update; canonicalization is additional. No truncation.
- Hybrid syntax/rendering compatibility retained, with no new hybrid features.
- Other roles' concurrent edits were observed and left untouched. No dependency
  blocks Role A. Role D owns full-suite/integrated readiness checks after all
  roles are READY. The deferred evaluation protocol's historical memory identity
  may require D's compatibility handling; no protocol/defaults changed here.

Limits: controlled character counters and scripted inference establish wiring
and boundaries, not Qwen tokenization, useful memory, gameplay effectiveness,
binding allowances, or comparative superiority. No GPU job, real-model inference,
model download, tuning, allowance selection, or old-artifact modification occurred.
