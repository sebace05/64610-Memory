# Codex implementation prompt for Modal S1 preparation

Implement and verify the minimal Modal transport for memory-probe-v1 Stage S1. Finish with concrete files, offline test evidence, an exact future launch command, and a handoff for the designer agent to review.

This request authorizes local implementation, CPU fixture tests, public documentation lookup, and preparation of the execution packet. It does **not** authorize submitting a Modal job, building an image remotely, loading a real tokenizer or model, installing or upgrading dependencies, fetching model assets, or running S1/S2. Prepare everything necessary for S1; stop before execution authorization.

Repository: `/Users/abdivu/Desktop/school/6.4610/64610-Memory`.

## 1. Read the accepted checkpoint

Read these before editing:

- `AGENTS.md` and `docs/memory-probe-v1.md`.
- `artifacts/memory-probe-v1/p1r2-20261117T192619Z/report.md`, `verification.json`, `package-verification.json`, preservation evidence, and saved test logs.
- `artifacts/memory-probe-v1/package-v2/manifest.json` and its file-hash ledger.
- `game_memory/memory_probe.py`, particularly `actual_preflight`, `run_stage`, `run_qualification`, `run_family`, the audit/gate functions, and completion/commit handling.
- `game_memory/transformers_model.py`, `game_memory/runner.py` (`_LoggedModel`), and `tests/test_memory_probe.py`.
- Historical pattern only: `artifacts/method-readout-modal-execution/20261117T032231Z-3fe0a360/transport.py`, `worker.py`, `plan.json`, and runtime evidence under its `final-download/` directory.

P1 revision 2 was reviewed and accepted. Its saved full-suite result is 437 passed, 25 skipped, exit 0. The skips are unverified optional checks, including the actual tokenizer check. The accepted fixes require exact assessment/write coverage, propagate incomplete-pilot errors without a budget decision, and verify complete repair requests and writer routing. Preserve all three.

The active package is **`artifacts/memory-probe-v1/package-v2/`**, never the superseded `package/` directory:

- Manifest digest: `f13e098e790f52159d5f34d5b1d608f8da1829a9b10ae84c4413beaebdba4fa6`.
- Source ZIP SHA-256: `341927b9d47cf8a651885169ff6677d9a94098e6f8a7a9e9c58cfbca42e36f55`.

Before implementation, independently verify the manifest digest, package file hashes, source archive contents, and current source hashes. The manifest digest uses the existing `memory_probe.digest` convention, excluding `manifest_sha256` itself. Do not substitute a different JSON serialization convention.

## 2. Keep the change narrowly scoped

Use the existing checkout. Add only:

- A small `game_memory/memory_probe_modal.py` module for worker orchestration and transport-specific helpers, with lazy optional imports.
- `tests/test_memory_probe_modal.py` for meaningful offline verification.
- A fresh `artifacts/memory-probe-v1/s1-preparation-<UTC>/` packet containing the thin Modal launcher, fixed plan, transport hashes, evidence, and review report.

Reusable logic belongs in the Python module; the artifact launcher should be thin. Keep package/model loading and execution independently testable using simple fixture substitution. Do not create a general launcher, scheduler, retry/resume framework, new logging framework, new configuration hierarchy, or new dependencies.

Do not edit any file covered by package-v2's source manifest, including `memory_probe.py`, `memory.py`, `transformers_model.py`, `runner.py`, existing tests, protocol documentation, and `AGENTS.md`. Do not regenerate splits, change prompts, adjust gates, or rebuild the study package. Hash the new transport files separately. Preserve both earlier packages and all historical evidence byte for byte.

If a concrete blocker requires changing frozen code, preserve your work and report the smallest necessary change for designer review. Do not silently invalidate package-v2 or fix unrelated code. Do not revert pre-existing user edits.

## 3. Prepare this exact Modal configuration

Use the prior successful image and existing volumes:

| Setting | Required value |
|---|---|
| Parent image | `im-lpkpC3RDMdArh7s8umL14J` |
| Cache volume | `memory-research-cache`, mounted read-only at `/cache` |
| Results volume | `memory-research-results`, writable at `/results` |
| GPU | One `A10`; accept the corresponding A10/A10G runtime name |
| CPU | 4 |
| Host memory | 32768 MiB |
| Startup timeout | 600 seconds |
| Function execution timeout | 7200 seconds |
| Soft deadline | Worker-entry monotonic time + 6900 seconds |
| Containers | Minimum 0, maximum 1; one input; no concurrency decorator |
| Configured retries | 0 |
| S1 model-request ceiling | 1070, including repairs and reader forwards |

Set `HF_HOME=/cache/huggingface`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and `HF_HUB_DISABLE_TELEMETRY=1`. Use `local_files_only=True` and `trust_remote_code=False` for cached asset loading. Look up existing resources with creation disabled; a missing image/cache/volume is a prerequisite failure, not permission to create replacements or download assets.

Use the installed local Modal SDK. The historical launcher used 1.6.4; inspect the installed version and supported signatures without installing or upgrading it. Record the chosen SDK version. Official documentation may describe newer APIs: use the supported read-only mount API for the installed version rather than blindly changing the SDK. Read-only resource existence and remote runtime checks remain pending until a separately authorized launch; offline preparation must not hydrate remote resources or build an image.

Required inference runtime, from the successful image's recorded evidence:

```text
Python 3.12.10
torch 2.8.0
transformers 4.57.6
tokenizers 0.22.1
safetensors 0.6.2
huggingface-hub 0.36.0
CUDA 12.8
```

Check these inside the future worker before weights load. Use the image's validated Python environment; the historical worker used `/opt/memory/.venv/bin/python`. Resolve any interpreter/virtual-environment setup narrowly, without installing packages or accepting a different runtime. Execute `run_stage` and its real `results.commit` callback in the same worker process.

Prepare image construction from the parent plus only the frozen package and reviewed worker/transport code. Disable automatic inclusion of unrelated checkout source. Only construct the actual remote image after execution authorization. Record its derived image ID when it exists; do not invent that ID during preparation.

Keep run ID, stage, output paths, and stage-specific settings in the invocation plan passed at runtime. Do not bake an S1-only plan into the image: a later authorized S2 must be able to reuse the exact S1-derived image. Do not implement or launch S2 now.

## 4. Make launch deliberate and prevent repeated scientific work

Prepare a single explicit launch entry point. Importing its helpers, running tests, requesting help, or invoking it without execution authorization must not create an App, build an image, submit a call, or load real assets. The future launch command must name a separately supplied authorization file; this preparation task must not manufacture an approved authorization.

Before future submission, exclusively create and fsync a local reservation containing the fixed run ID, package digest, transport hashes, and plan hash. Refuse to submit the same reservation twice. Record App, function-call, and derived-image IDs immediately when available. Preserve partial identifiers if submission acknowledgement is interrupted.

The future remote invocation must also exclusively create its fixed run directory and persist an execution-entry record with a successful results-volume commit **before any real tokenizer/model loading**. Re-entry with that run ID must fail before scientific work, preserving earlier evidence. Do not choose a fresh remote ID on re-entry or overwrite existing records.

This guard addresses the distinction between configured function retries and platform crash rescheduling; `retries=0` alone is not an exactly-once guarantee. Use a simple exclusive record and commit, not a distributed locking system. See [Modal failures and retries](https://modal.com/docs/guide/retries).

Prepare status/collection commands that use the saved call ID. A future client timeout or uncertain submission acknowledgement means unknown state: inspect that call and existing records, never submit a replacement automatically. No retries, resume mode, or additional model worker.

## 5. Implement the future worker sequence using the existing API

The frozen module exposes Python functions. Do not invent a `run-stage` CLI command or reimplement the experiment loop.

The future worker must perform this sequence:

1. Start its deadline clock at worker entry, reserve the remote run, and commit the entry record. Verify the invocation plan and transport/package hashes. Extract `source.zip` into a fresh temporary directory, verify every archived source file, and import the experiment from that verified extraction. Confirm module origins so an older package in the parent image cannot shadow the frozen source.
2. Verify the pinned runtime and cached model configuration, tokenizer assets, and nonempty weight-shard inventory for revision `cdbee75f17c01a7cc42f958dc650907174af0554`. Record inventory and source/cache identity. Missing or incompatible assets must stop the worker before a weight load.
3. Load the **cached tokenizer only**, then call `memory_probe.actual_preflight` with context 8192, writer cap 1024, the cached configuration's vocabulary size, and evidence explicitly labelled as actual cached-tokenizer evidence. Do not use `len(tokenizer)` as an unexamined replacement for the model vocabulary size.
4. Save and commit the preflight before weights. Require `passed is True`, not merely absence of an exception. Verify 76 distinct Q0 prompts, label validity at their actual chat-template prefixes, full reader context bounds, every frozen sufficient note at most 256 actual tokens, and initial writer prompt bounds. The existing helper performs these checks; retain its output, template hash, token counts, and package identity. It may count notes and render prompts from all frozen splits, but must perform no test-family inference. Character counts and synthetic counters are not tokenizer evidence.
5. Only after successful preflight, construct **one** `TransformersModel` with explicit configuration: Qwen/Qwen3-4B-Instruct-2507, the pinned revision above, CUDA, float16, context 8192, generation seed 0, memory generation cap 1024, and local files only. Preserve the adapter's greedy generation and restricted-label reader. Record model identity and weight-load seconds. Add no warm-up or diagnostic inference calls.
6. Call `memory_probe.run_stage("s1", package_path, fresh_stage_output, model, commit=results.commit, deadline=worker_entry+6900, ...)` using the actual supported signature. The two dev families run in their existing order only after Q0 passes. All real calls must retain the existing `_LoggedModel` accounting and raw traces. The transport must not add model calls or alter evidence, candidate logits, prompts, memories, or gold labels.
7. Save a final outcome, timings, known usage, and any original exception/traceback. Commit in `finally`. Preserve the original failure if cleanup also fails; record a secondary cleanup error where possible. A transport error must not become an empty successful result.

The soft deadline prevents new work and new requests; it does not promise to interrupt an in-flight CUDA operation. Keep the 7200-second Modal hard limit. Do not extend either limit after a timeout.

Preserve the experiment's completion order: close/flush/fsync unit files, write/fsync their hashed completion record, successfully commit the results volume, then start the next unit. Use the existing callback path. A later final commit is additional protection, not a substitute for unit commits. See [Modal Volume commit](https://modal.com/docs/sdk/py/latest/Volume#commit).

## 6. Preserve gates, counts, and outcome meanings

The frozen experiment functions remain authoritative:

- Q0 covers 96 logical assessments using 76 physical reader requests. Full history, sufficient prose, and sufficient JSON must each score at least 15/16; both missing-fact conditions must each score at least 15/16 abstentions; no-memory factual accuracy is at most 4/16; outside-memory sibling inputs match; zero technical failures.
- An audited Q0 performance failure is `valid_research_stop`, successful execution, and no pilot. Corrupt or incomplete qualification evidence is an error, not a valid research stop.
- A passing Q0 permits D00 and then D01, both formats, allowances 64/256, both probes. Each completed family has 224 primary memory updates/requests, at most 224 repair requests, and at most 49 physical reader requests. Carry-forward assessments require no extra inference.
- The S1 ceiling is `76 + 448 + 448 + 98 = 1070` physical requests. Prevent an additional request beyond the ceiling without changing model-visible behavior. Preserve physical/logical/reuse distinctions.
- Pilot stop: both formats at most 2/8 at P12/B256. Otherwise select 128 only if pooled P12/B64 correctness is below 4/16; select 64 otherwise. Incomplete or unauditable pilot: error, no budget decision.

Prepare three distinct final classifications: completed pilot with its audited decision, valid research stop, and infrastructure/timeout/incomplete failure. Propagate errors to a nonzero launch/worker status; valid performance stops may exit zero. Do not tune prompts, change budgets, train, switch models, retry, or continue into test families in response to any outcome.

## 7. Prepare collection and review evidence

Prepare a small collection/verification path for the same future call and run ID. It must preserve raw logs and error records, verify downloaded completion hashes, invoke the existing audits with real evidence required, and independently recompute Q0 and pilot decisions from raw assessments. A partial run may be collected but cannot receive a complete verdict or a budget decision.

Prepare reconciliation of physical requests, logical assessments, reuse sources, repairs/fallbacks, actual input/output tokens, generation/forward time, model-load time, and end-to-end worker/family time. Count actual calls once. Do not estimate missing usage as zero. Record per-cell pilot P0/P12 results and reference controls.

After a future run, collect evidence and verify this App has stopped with zero tasks. Any shutdown operation must target only this experiment's saved App ID. Leave unrelated Apps and volumes alone.

For the eventual review, compute `L = actual model-load seconds`, `R = max(D00 whole-family seconds, D01 whole-family seconds)` excluding load, and `T(n) = max(600, ceil(1.5 * (L + n*R) + 300))` for n=8 and n=4 only when both pilot families completed. If B_low is 128, disclose that 128-token runtime was not piloted. These are planning estimates for later review, not authorization for S2 or new performance claims.

## 8. Verify offline before finishing

Use `.venv/bin/python`. No real Modal calls or real tokenizer/model loads in tests. Reuse the existing fixture style and monkeypatch simple boundaries. New transport tests must have zero skips and establish:

- Bad package/source/plan hashes, wrong runtime, missing cached assets, failed/false preflight, or exhausted deadline stop before a weight load or request.
- Import/help/no-authorization paths do not submit, build, or load anything. A duplicate reservation or committed remote-entry record prevents repeated work.
- Successful preflight is durably committed before the one model construction. A Q0 performance failure runs no dev family; infrastructure/audit failures propagate.
- The real `run_stage` callback path is preserved using fixtures: commits occur before later units; a commit failure stops progress; errors and incomplete pilots retain their reason and no budget decision.
- The request ceiling refuses request 1071; the fake model's prompt/output/metadata delegation remains unchanged below the limit.
- Collection rejects altered completion hashes and partial coverage. Unknown client state never calls submit/spawn again. CPU evidence remains visibly synthetic.

Test behavior and failure cases; do not add tests that merely repeat constants. A fixture can verify callback ordering, not actual Modal durability. Reuse accepted P1 tests instead of copying their entire audit suite.

Run and save exact commands, logs, exit statuses, and skips for:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q -rs tests/test_memory_probe_modal.py tests/test_memory_probe.py tests/test_memory.py tests/test_runner.py tests/test_transformers_model.py tests/test_memory_integration.py tests/test_choice_actor.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q -rs
.venv/bin/python -m game_memory.memory_probe verify-source --package artifacts/memory-probe-v1/package-v2
```

Both pytest commands must exit zero; list optional skips without treating them as verification. Record a before/after preservation comparison. Verify both old packages and existing evidence are unchanged and package-v2 still matches. Do not weaken existing tests or install dependencies to eliminate skips.

## 9. Freeze the preparation packet and hand it back

After implementation and successful offline checks, freeze the new transport files and plan with SHA-256 hashes. This is a separate transport manifest; do not overwrite or regenerate the study manifest. Do not include credentials. Keep the plan fixed, with a concrete unique future run ID, output paths, expected package digest, runtime/resource limits, and permitted S1 stage. Runtime-assigned App/call/derived-image IDs should be explicitly unassigned until execution.

Include an `authorization-template.txt` visibly marked **TEMPLATE — NOT EXECUTION AUTHORIZATION**, with this proposed future user authorization:

> I authorize memory-probe-v1 S1 using package-v2 manifest f13e098e790f52159d5f34d5b1d608f8da1829a9b10ae84c4413beaebdba4fa6: one Modal A10 worker, at most one Qwen weight load from the existing read-only cache, actual cached-tokenizer preflight before loading, Q0 qualification, then D00-D01 only if Q0 passes; startup cap 600 seconds, execution cap 7200 seconds, soft deadline 6900 seconds, zero configured retries, at most 1070 model requests. No test-family inference, model/dependency downloads, installations, or S2. Collect and verify this run's evidence and shut down its App afterward. Do not retry or resubmit an interrupted run.

Do not copy that template into an approved authorization file. Stop with a concise report containing changed files, test results, package/transport verification, exact future launch/status/collect/shutdown commands, and remaining unverified remote prerequisites. Commands must be concrete except for the future separately supplied authorization and runtime-assigned IDs; do not execute them.

Finally, write a self-contained `designer-review-prompt.md` in the preparation packet and link it in your reply. Fill it with the actual paths and hashes you created. Ask the designer to review the implementation and evidence, identify concrete file/line defects or confirm readiness for separately authorized S1, and distinguish offline verification from unexecuted real tokenizer/model/Modal behavior. Instruct the designer to review only and launch nothing. Explicitly report that this task performed no remote builds, submissions, real tokenizer/model loads, installs, model-asset downloads, commits, or pushes.
