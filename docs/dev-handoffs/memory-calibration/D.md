# Role D — READY

Contract: memory-development-contract-v1. Owns pilot/CLI/source identity,
compatibility callers/tests, and integration documentation. No A/B/C files edited.

Implemented schema-2 pilot manifests with exact `memory` metadata and nonempty
`protocol_id`; `prepare_pilot(..., *, memory_metadata, protocol_id)` matches the
contract. CLI selects memory before weights, accepts `--protocol-id`, and retains
explicit generic fixture/full-history/bounded identities when omitted. Results
and episode headers now also record protocol_id. `runner.source_metadata()` adds
source_digest; `runner.source_digest` is the moved existing digest helper,
re-exported by evaluate_3x2. Deferred evaluator caller uses deferred-3x2-v1.
All expected result identities are independently checked before weights.

C coordination: schema-2 producer is implemented; source, actor, memory, model,
runtime, episode, backend, protocol_id fields follow section 5 unchanged. No
extra comparison API or live grid created. Comparison schema documented in
`docs/memory-calibration-integration.md`; C consumes declared JSON directly.

Checks:
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 JAVA_TOOL_OPTIONS='-XX:-UsePerfData -Xlog:os+container=off:stdout -Xlog:os+container=warning:stderr' .venv/bin/python -m pytest -q tests/test_pilot.py tests/test_runner.py tests/test_evaluate_3x2.py tests/test_transformers_model.py`
  with local gateway sandbox escalation: **77 passed in 32.92s**, exit 0, no skips.
- After adding explicit v30 preflight and final CLI identity assertions:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_pilot.py -k 'not cli_prepare_and_launch_guard and not model_initialization_failure' tests/test_evaluate_3x2.py`: **29 passed, 2 deselected in 0.15s**, exit 0.
  Same gateway-enabled environment, `.venv/bin/python -m pytest -q tests/test_transformers_model.py -k real_inference_cli`: **3 passed, 24 deselected in 7.21s**, exit 0.
- Focused restricted run of pilot/evaluator: 28 passed, 1 failed from Java gateway
  stdout pollution (hsperfdata lock warning), exit 1.
- Three restricted gateway runs interrupted after stalls, exit 130. No checks
  weakened. Successful focused suite used local gateway sandbox escalation
  and JAVA_TOOL_OPTIONS disabling JVM performance-data lock files.
- `git diff --check`: passed.

A/B/C reported READY and stopped editing before final integration. Role D has
now stopped implementation edits. No integration dependencies remain.
No GPU job, Qwen inference, downloads, tuning, or historical artifact edits.

Review: public component interfaces, inference purpose labels, memory update events,
turn order, independent memory bound, and error/terminal accounting are unchanged.
Only runner identity fields/optional protocol keyword were added. Source helper
retains the existing algorithm; executable and dependency mutation tests pass.
Prose/JSON v17 metadata and explicit v30 selection align with A/B handoffs.
Fake/scripted and tiny random CPU-model tests do not establish actual Qwen
usefulness, memory pressure, success rates, or comparative effects. Allowances,
sample size, and all T7 calibration remain separately gated.

Final integration:

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 JAVA_TOOL_OPTIONS='-XX:-UsePerfData -Xlog:os+container=off:stdout -Xlog:os+container=warning:stderr' .venv/bin/python -m pytest -q`
  with local Java gateway sandbox escalation: **380 passed in 49.29s**, exit 0,
  no skips or failures. This is the required full suite with an environment-only
  JVM workaround for concurrent temporary performance-data locks.
- `git diff --check`: passed, exit 0.
- Files changed by D: game_memory/pilot.py, game_memory/run_episode.py,
  game_memory/runner.py (identity only), game_memory/evaluate_3x2.py (shared helper
  and caller compatibility only), tests/test_pilot.py, tests/test_runner.py,
  tests/test_transformers_model.py, tests/test_evaluate_3x2.py,
  docs/memory-calibration-integration.md, and this note.
- Reviewed A/B/C READY handoffs and combined metadata/manifest/event boundaries.
  No cross-owner patches were necessary. Existing old artifacts remain intact.

Calibration-readiness: T1–T6 engineering checks pass. T7 remains separately
authorized work; no GPU job, real-Qwen run/tuning, model download, live comparison
manifest, allowance freeze, or historical artifact modification occurred. CPU
random miniature-model tests are test fixtures, not research-model evidence.
