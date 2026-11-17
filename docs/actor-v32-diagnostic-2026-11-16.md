# Actor v32: frozen prerequisite-decision diagnostic

This iteration implements an experimental primary instruction and prepares eight
isolated actor proposals. **No Qwen inference, GPU work, paid submissions, weight
downloads, pushes or deployments occurred.** v31 remains the production actor;
writer `p1-memory-v17` and renderer `p1-render-v2` are unchanged. Scripted correct
actions establish routing, not model capability. The candidate is not promoted.

## Candidate and preserved behavior

`v32` was unused. Its exact primary system instruction is:

> Prepare and eat the recipe meal using only supplied public evidence. 1. Read recipe ingredients and directions as requirements, not completed facts. 2. Establish currently carried items and completed operations from the supplied observation and context; do not treat requirements or plans as evidence of completion. 3. Cooking an ingredient does not mean a meal was successfully prepared. 4. Choose eating only if evidence supports an already prepared meal and the exact command is currently in allowed_actions. 5. Otherwise identify the next unfinished requirement and its missing prerequisites. Before preparing a meal, all required ingredients must be carried together with their required operations complete. Putting an item down removes it from carried items. Grilling uses toaster, roasting uses oven, frying uses stove; slicing and chopping require a carried knife. 6. Choose an exact currently allowed action that advances that requirement or obtains its prerequisite. 7. If needed facts are uncertain, choose an appropriate permitted information action. Respect budget_remaining: recipe rereads cost recheck_cost, other actions cost 1. Return only JSON with next_direction, missing_prerequisite, action.

This is a different decision procedure, not a controlled test of verbosity alone.
The instruction is a replacement, rather than a reminder appended to v31.
The public JSON, context labels, literal memory, action membership/order, schema,
optional-article normalization, preparation review and unavailable-action repair
instructions/triggers remain the v31 implementation. Repair limits, invalid
attempts and usage accounting remain unchanged. A malformed-response repair
retains the initial conversation (including the candidate primary instruction),
just as v31 retains its own primary instruction; its feedback is unchanged.
No semantic filtering, forced actions, reconstruction, loop breaking or writer
changes were introduced. The auditor still independently checks provenance.

## Frozen evidence and identities

Protocol: `actor-prerequisite-procedure-v32-eight-call-v1`.

- Maintenance source before this iteration: `c6be73b9eb415abedc39511938ded8f30593380216c0f31c37fe1ea04a3fe853`.
- New executable source: `ec7af9905d17fd7f98e6f73bfac1eb06b8f121858cd21f858373f13ae69478f7`.
- Frozen plan hash (canonical JSON excluding its own hash field): `b7c2dc0e59ea9aba2dab9ade8ddd03f9e495572d9c50568ea85c7e83dcb23b98`.
- Source-file manifest hash: `a187fd546cff555bac7829747348492c25155db1c6cf19ff63011398cb16b3d6`.

All identities refer to dirty source, not reproduction from Git HEAD. The
maintenance metadata, dirty actor/environment/pilot copies and initial tracked
patch are in `artifacts/actor-procedure-v32/maintenance-baseline/`. The executable
source/test archive is `artifacts/actor-procedure-v32/plan.source.zip`, with an
adjacent SHA-256. Its CRC was checked. It includes the executable modules, launch
helpers, tests and JSON test fixtures, excluding environments, credentials,
weights and historical gameplay archives. Full historical-fixture suite checks
also need the preserved artifact fixtures; the eight-call worker needs none.
Historical Modal/replay scripts and frozen digest constants were not changed.

Frozen plan: `artifacts/actor-procedure-v32/plan.json`.
Offline rubric: `artifacts/actor-procedure-v32/offline-rubric.json`.
The plan includes exact baseline/candidate messages, source paths, byte hashes,
request identifiers, source/runtime settings, eight-call maximum and limitations.
Preparation verifies the original trace hashes and request contents. For salt
cases it also verifies the saved diagnostic arm against the actually executed
request and records the adjacent real response as its reproduction target.

| Case | Exact baseline source | Offline target |
| --- | --- | --- |
| Prose salt | Latest `responses.jsonl`, request line 49, `history / actor-prose-premature-eat / same-view-public-history-v1` | legal `take salt` |
| JSON salt | Same file, request line 53, `history / actor-json-premature-eat / same-view-public-history-v1` | legal `take salt` |
| Slice control | Earlier `submitted-plan.json`, `actor-slice-control`, original trace request 27 | correct slicing |
| Eat control | Same plan, `actor-eat-control`, original trace request 41 | legal `eat meal` |

Latest run root:
`artifacts/replay-downloads/replay-v2-a71df749b0ca-7e9c1a1c/replay-v2-a71df749b0ca/`.
Earlier control plan:
`artifacts/replay-downloads/replay-v1-f882d8fe7d57-9a00ec5e/replay-v1-f882d8fe7d57/submitted-plan.json`.

The salt requests retain **Visible interaction history (diagnostic; unbounded):**
exactly. They are the earlier experiment's variants, now used as saved baselines;
they are not replaced with bounded requests. The slice/eat controls retain their
original full-history label. Each pair differs only in the first system content.
All eight purposes are `action`; there is no environment, writer, review or repair
execution. Offline expected actions and scoring fields never enter model calls.

## Preparation, preflight and later execution

The preparation command used was:

```sh
.venv/bin/python -m game_memory.actor_diagnostic prepare \
  --latest-run artifacts/replay-downloads/replay-v2-a71df749b0ca-7e9c1a1c/replay-v2-a71df749b0ca \
  --controls-plan artifacts/replay-downloads/replay-v1-f882d8fe7d57-9a00ec5e/replay-v1-f882d8fe7d57/submitted-plan.json \
  --maintenance-identity artifacts/actor-procedure-v32/maintenance-baseline/source.json \
  --output artifacts/actor-procedure-v32/plan.json
```

This output exists and is immutable: do not rerun into that path. A subsequent
source/prompt change needs a new declared identity and fresh plan, not an overwrite.
The CPU-only tokenizer preflight command is:

```sh
.venv/bin/python -m game_memory.actor_diagnostic preflight \
  artifacts/actor-procedure-v32/plan.json \
  artifacts/actor-procedure-v32/tokenizer-preflight-pinned.json
```

It loads only the pinned cached tokenizer (`local_files_only=True`, no remote
code), requires Transformers 4.57.6/tokenizers 0.22.1, applies the chat template
once, reserves 128 output tokens, refuses overflow without truncation, and hashes
the template, prompt and token IDs. **Actual preflight is blocked locally.**
The `.venv` lacks Transformers, tokenizers, Torch and Hugging Face Hub, and the
local Hugging Face cache has no pinned Qwen tokenizer. The attempted local
preflight exited 1 with `ModuleNotFoundError: No module named 'transformers'`;
`tokenizer-preflight-local.json` records the blocker and `weights_loaded=false`.
No fake-tokenizer counts are represented as actual Qwen counts. No packages were
installed to compensate. A pinned cache-equipped environment must complete this
preflight before execution; do not use the blocked record as a passed preflight.

Only after separate inference authorization, in the pinned cache-equipped A10
worker environment restored from the source archive, the finite command is:

```sh
.venv/bin/python -m game_memory.actor_diagnostic execute \
  artifacts/actor-procedure-v32/plan.json \
  artifacts/actor-procedure-v32/execution-001 \
  --preflight artifacts/actor-procedure-v32/tokenizer-preflight-pinned.json
```

This command was **not run**. There is no cloud submission command in the new
entry point. One child worker has a 600-second limit and no retries/resume. It
checks source files/digest, repeats and compares the cached tokenizer preflight,
requires Python 3.12.10 and the recorded package versions, and rejects GPUs outside
A10/A10G. Qwen revision `cdbee75f17c01a7cc42f958dc650907174af0554`, CUDA FP16,
greedy generation, seed 0, context 8192, actor cap 128 and memory/repair cap 1024
remain fixed; no writer is invoked. Weight loading is local-cache-only.

The worker writes each exact request and fsyncs it before inference, retains
responses and all adapter usage/metadata, and stops visibly on infrastructure
errors. Partial traces remain. Output paths and worker markers are exclusive;
reusing an attempt fails. The wrapper preserves child stdout/stderr and actual
exit status, timeout and signal information. Complete execution is recorded
separately from the offline decision gate; text drift does not trigger extra calls.

## Java baseline and CPU validation

The new startup probe runs `java -version` with the same PATH and inherited
options used by Py4J. A failing JVM or stdout diagnostics now yields an actionable
error before starting the simulator's numeric-port protocol. It preserves the
JVM output and explains the need for a compatible isolated Java 17 runtime.
Production logging flags remain unchanged. The existing noisy-startup regression
now expects this earlier explicit error; its successful-startup assertion remains.

The default PATH has Oracle Java 8. Existing IntelliJ JBR 17.0.9 and Eclipse
Temurin 17.0.9 both run, but their macOS builds lack the Linux `os+container` tag.
With the preserved logging flags they emit stdout warnings even on exit 0.
An explicit PATH to JBR was tested without changing global configuration. The
available local Docker images (grading/dev and Alpine) contain no Java/Python
runtime; the grading image was inspected with networking disabled, read-only,
without pulling or installing anything. Thus a compatible logging/runtime
baseline is **not resolved** by the early error. The pinned Linux Java 17
experiment environment remains required.

All project checks used `.venv/bin/python` (Python 3.12.1); no global-Python
fallback or GPU stack installation was used. Simulator tests required sandbox
escalation for local loopback access. Results on the final frozen source:

- Root intended collection: **460 tests**, no archive collection errors.
- Focused actor, diagnostic, environment, independent auditor, historical replay,
  Modal and digest checks: **198 passed**, no skips, in 12.72 seconds.
- Differential comparison with the dirty pre-iteration actor: **384** combinations
  (32 historical policies × two context modes × six scenarios, two turns each)
  matched exact messages, purposes, outputs and metadata. Permanent tests also
  pin v31 primary hashes and compare v31/v32 review/repair/failure paths.
- Required full command `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m
  pytest -q`: **435 passed, 24 skipped, one failed**, 25.87 seconds, exit 1.
  Failure: `test_cli_prepare_and_launch_guard_work_together`, now displaying the
  actionable Java 8 error instead of the Py4J parse error. One skip requires
  Java 9+ logging; the remaining 23 require missing Torch.
- Focused run with explicit JBR Java 17 PATH: **193 passed, one skipped, two
  failed**, 10.97 seconds. The pilot launch and noisy-Java regression cannot
  satisfy their successful-startup assertions because the macOS JVM lacks the
  required logging tag. These failures are retained, not skipped or called passes.

The full suite and pinned model-adapter/runtime checks do **not** pass locally.
Test logs, the differential script/output, preflight blocker and source identity
are retained under `artifacts/actor-procedure-v32/validation/` and the plan root.
Scripted tests exercise eight-call limits, hash/provenance rejection, byte-identical
user evidence, drift/action distinctions, non-informative baselines, incomplete
execution, preserved generation failures, failed preflight, token mismatches,
exclusive attempts and underlying child exit status. They do not establish Qwen
reasoning, retention or gameplay performance.

## Decision gates and subsequent work

Score syntax, legality, targeted semantic correctness, exact baseline text,
normalized baseline action agreement and control preservation separately.
Both salt candidates must choose legal `take salt`; an information action can be
understandable but is not this targeted fix. If either salt baseline no longer
reproduces premature eating, its paired result is non-informative for attribution.
Do not replace it or launch more calls. Preserve text drift visibly even if the
normalized action agrees. Syntax/legal output alone cannot promote v32.

If both salt failures reproduce, both candidates improve and both controls stay
correct, next propose exact baseline/candidate pairs on the original bounded salt
requests. Only after that gate, test original/reversed/rotated presentations of
the saved slicing failure with the existing slicing controls. These require new
authorization and identities; selected-request improvements are not gameplay wins.

If full-history salt decisions still fail, stop the instruction-tuning loop.
Propose a separate four-request fact-identification diagnostic: the two unchanged
salt histories plus the successful slice/eat histories as controls, asking for
requirements, confirmed possession and completed operations separately. Compare
those readouts offline with the already recorded action failures; never supply
corrected facts. Accurate readouts with wrong actions would suggest a decision
problem; inaccurate readouts would retain evidence interpretation as an
explanation. This is not a fine-tuning recommendation or a production schema change.

Writer fidelity is separate: freeze short writer-only sequences of saved pickup,
grilling and unrelated public observations; compare one versioned update
procedure with v17. Each arm receives **its own preceding model-written memory**,
never Python-filled facts. Keep model-managed prose/JSON and the shared allowance,
including plans. Score recipe retention, possession, accumulated operations,
unsupported completion and stale context values independently. These remain
writer diagnostics, not gameplay successes. Failed reminders and field ordering
are prior findings, not new interventions.

JSON repair is separate: compare compact/readable presentations of the same real
malformed candidates, changing only whitespace **outside strings**. Preserve
content, nesting, extra delimiter, message roles, system instruction and feedback.
Include the earlier successful synthetic extra-brace probe, clearly labeled as
synthetic rather than a successful saved real repair. Never parse and silently
repair the candidate before sending it. Score strict syntax and content retention
separately. No production repair code changed in this iteration.

Only after actor/bounded/robustness and component fidelity gates pass should a
separately authorized four-episode roomy prose/JSON × seeds 0/1 calibration be
proposed. Inspect complete gameplay and memory traces before returning to the
eight-cell memory-price MVP. Hybrid, held-out evaluation, sweeps, dashboards,
optimization and general batch/resume stay deferred. No such episodes are launched.

**TLDR:** implemented v32 and a frozen eight-call diagnostic; CPU wiring and
failure paths verified; Qwen behavior and actual tokenizer preflight unverified;
next experiment is the separately authorized four-case actor replay after pinned
runtime/cache preflight succeeds.
