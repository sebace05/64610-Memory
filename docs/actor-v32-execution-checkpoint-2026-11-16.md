# v32 execution-status checkpoint — November 16, 2026

The timeout/success reporting defect is corrected and verified with CPU fixtures.
**The Qwen experiment has not run.** Actor v32 remains experimental; production
is still actor v31, writer v17 and renderer v2. No instruction, public input,
review/repair policy, normalization, action order, usage accounting or scientific
criterion changed. No dependencies were installed, tokenizers/weights downloaded,
cloud jobs submitted, global configuration changed, push or deployment performed.

## Observed regression and correction

Before editing, a mocked raw child status `returncode=0, timed_out=true` reproduced
wrapper exit **0**. The corrected wrapper returns **124** for every timeout and
leaves `worker.status.json` unchanged. Ordinary child exit 7 remains outer exit 7;
signal -15 becomes nonzero outer exit 143 unless timed out, when it becomes 124.
Startup failure, missing/invalid child status and missing completion evidence
cannot produce success.

After a clean zero child exit, the wrapper now requires a completed worker status
with eight calls, a matching start marker, model metadata, eight complete frozen
request/response pairs, a matching saved assessment and reconciled input-token
counts. It writes the separate `execution-status.json` with the wrapper outcome.
The actual child record is never rewritten. A failed research gate does not
change the exit status of an otherwise complete, valid eight-call batch.

A real bounded child installed a SIGTERM handler and exited **0** when the actual
subprocess boundary timed out. Saved records show:

- `validation/fixtures/timeout_zero/attempt/worker.status.json`:
  `returncode=0`, `timed_out=true`, `interruption=null`.
- `validation/fixtures/timeout_zero/attempt/sigterm-handled.json`: child exit 0.
- `validation/fixtures/timeout_zero/attempt/execution-status.json`: exit **124**.
- `validation/timeout_zero.outer.status.json`: actual outer exit **124**.

The signal-only timeout retained raw child exit -15 and also returned 124. Both
children were reaped. A clean zero exit lacking completed-worker evidence returned
1. The `scientific_failure` fixture completed all eight calls, returned 0, and
retained `decision_gate_passed=false`. No retry or replacement call occurred.

## Immutable successor package

Directory: `artifacts/actor-procedure-v32-execution-v2/`.

- Protocol: `actor-prerequisite-procedure-v32-eight-call-execution-v2`.
- Dirty executable-source digest: `9523fb5b046c322dad720950e1567d42c2172fe44467e8bb88f49745d9e45eed`.
- Plan hash: `39d2da64ccab5c228ce5863c355e9dccc65a2d16627607a6120acb28fbf6c371`.
- Source-file manifest hash: `e314a02d0e82aaea81204246cf666a596d38b15ebeb0f4f3d10cf334f5310f10`.
- Source archive SHA-256: `4d6bebc866f6cacaa736c81a616bd7b29dd113b18b076607cdb9c4d152d04d7a`.

This is an execution-only successor; actor version remains **v32**. The predecessor
`artifacts/actor-procedure-v32/` was not overwritten. Initial and final inventories
match for all **18** files, including its blocked actual-tokenizer preflight.
Historical Modal/replay scripts and digest constants were not modified.

The package contains `plan.json`, `offline-rubric.json`, `source-manifest.json`,
`plan.source.zip`, its adjacent SHA-256, and validation records. The archive includes
the test-only subprocess harness. `validation/refreeze_package.py` records how the
successor was derived and uses exclusive writes; it is not a resume mechanism.
`validation/package-verification.json` records CRC, every archived/live source
hash, plan hash, rubric linkage, and the eight request hashes.

Programmatic comparison excluded only protocol/source/manifest/hash identity
fields and the new correction provenance. All remaining plan fields compare
equal, including complete case objects, historical response targets, offline
expected actions, runtime/model settings, caps, worker limits, limitations and
assessment criteria. All eight serialized message lists compare byte-for-byte
identically. The standalone rubric differs only in protocol and plan linkage.

AST comparisons also verify that `assess`, `run_proposals`, `worker`,
`tokenization`, `cached_preflight` and `prepare` are unchanged. Actor, writer,
renderer, environment, model adapter, runner and independent auditor source bytes
match the predecessor archive. The production worker's runtime checks were not
relaxed and no production fake-model mode was added.

The four cases retain their original order:

1. Prose salt: latest replay **request line 49**, executed full-public-history arm
   `history / actor-prose-premature-eat / same-view-public-history-v1`.
2. JSON salt: latest replay **request line 53**, corresponding JSON history arm.
3. Earlier `actor-slice-control`: original trace request **27**.
4. Earlier `actor-eat-control`: original trace request **41**.

The salt arms trace back to bounded requests 23/31, but those bounded messages are
**not** the selected baselines. Their literal unbounded diagnostic labels remain.
The two salt states are related trajectories of the same recipe/seed, not
independent task instances. This experiment tests a replacement procedure on
selected decisions; it does not isolate verbosity, individual sentences or an
internal reasoning stage, and does not estimate general gameplay capability.

## Explicit implementation verification

`tests/actor_diagnostic_fixture.py` is a test-only harness. It redirects the child
command through dependency injection while retaining the real production
`main` orchestration, `run_command` timeout/exit-status boundary, `run_proposals`
logging, `assess` scoring and completion check. Its child runs a scripted model
and tokenizer instead of calling the production worker. It does not call or
bypass checks inside the real worker; that function is unchanged. No GPU, model
weights, tokenizer dependency or simulator is needed for these fixtures.

Every fixture root and model record is explicitly labeled **integration_fixture**,
**scripted_model**, **not_Qwen_inference**. Fake tokenizer records are named
`scripted-tokenizer-fixture.json` under validation; their hashes/counts are not
passed actual Qwen preflight evidence. Expected answers produce test-only scripted
responses, while generate receives only the exact frozen role/content messages.

The standalone command actually executed was:

```sh
.venv/bin/python artifacts/actor-procedure-v32-execution-v2/validation/verify_fixtures.py
```

Its saved verifier reopens every artifact rather than trusting command success.
It independently checks case/arm ordering, alternating ledger events, role/content
fields, hashes, unchanged paired user evidence, request visibility before generate,
usage sums, semantic rows, baseline text/action distinctions and decision gates.
`validation/independent-fixture-verification.json` records all **15** scenarios:

| Fixture | Outer exit | Saved observation |
| --- | ---: | --- |
| Success | 0 | Eight pairs; independently reconciled ledger and gate |
| Scientific failure | 0 | Completed batch, failed research gate |
| Baseline already fixed | 0 | Salt pair non-informative for attribution |
| Legal wrong action | 0 | Legal, targeted semantic criterion fails |
| Information action | 0 | Legal inventory does not meet take-salt criterion |
| Wording drift | 0 | Exact text fails, normalized action agrees |
| Control alternative | 0 | Legal alternative misses selected control criterion |
| Failure on call 2 | 1 | Request/response/request, no retry; incomplete assessment rejected |
| Token mismatch | 1 | First response retained, execution stopped |
| Fabricated provenance | 1 | Assessment rejected; original untampered ledger also preserved |
| Timeout, child handles SIGTERM | 124 | Raw child exit 0 and timeout both retained |
| Timeout, default SIGTERM | 124 | Raw child exit -15 retained |
| Clean exit without evidence | 1 | Child exit 0 is insufficient |
| Startup failure | 1 | Raw null return code and FileNotFoundError preserved |
| Failed preflight | 1 | Neither child nor model creation reached |

For each complete fixture, eight responses sum to **160 scripted input tokens,
32 scripted output tokens and 2.0 scripted elapsed seconds**. These are fixture
values, not tokenizer measurements or model performance. Success-path reuse was
refused, and a before/after inventory verified the existing attempt was untouched.

Logs and statuses are in `validation/*.outer.log` and `validation/fixtures/`.
The call-2 partial trace and token-mismatch response remain available. The
provenance test preserves `responses-before-tamper.jsonl` alongside its explicitly
corrupted fixture ledger. These results establish execution/evidence/scoring
machinery with fixtures, **not actual tokenizer compatibility or Qwen ability**.

## Newly run CPU checks and remaining blockers

All project commands used `.venv/bin/python`; no global-Python fallback or
installation was used. Simulator tests needed local-loopback sandbox escalation.

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest --collect-only -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_actor.py tests/test_actor_diagnostic.py tests/test_environment.py tests/test_diagnostic_summary.py tests/test_modal_calibration.py tests/test_replay_diagnostics.py tests/test_replay_failures.py tests/test_evaluate_3x2.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

Fresh results: **485 collected**; **223 focused passed**, zero skips, 18.10 seconds;
full suite **460 passed, 24 skipped, one failed, one warning**, 31.71 seconds,
exit 1. Failure: `test_cli_prepare_and_launch_guard_work_together`; default Java 8
rejects the preserved Java 17 logging options. The simulator cleanup warning is
an unraisable `TextWorldExpressEnv.__del__` exception reported during the repeated
inspection test. Neither was suppressed. The missing Torch checks and Java 9+
logging regression remain skipped. Logs and exact commands/results are saved in
`validation/test-results.json`, `collection.log`, `focused-tests.log`, and
`full-suite.log`. The focused diagnostic file alone passed **43** tests.

Transformers, tokenizers, Torch and Hugging Face Hub are still absent locally.
The pinned Qwen tokenizer was previously absent from the configured/default
cache; no tokenizer/cache download was attempted. The predecessor's actual
blocked preflight remains unchanged. No actual successor tokenizer preflight or
production worker execution has been performed. Fixture preflight hashes must
never be substituted for the actual pinned-tokenizer record.

## Later runtime path and exact commands — not executed

Subject to availability and separate authorization, reuse the previously recorded
pinned Linux inference environment and its existing Hugging Face cache. Restore
`plan.source.zip` into a clean source directory in that environment, preserve its
existing pinned `.venv`, and copy the successor plan to the path below. Check the
archive SHA, source manifest and source digest before execution. Do not relabel
an old image/source digest as this successor or change dependencies opportunistically.

The real CPU tokenizer preflight, before any model loading, is:

```sh
.venv/bin/python -m game_memory.actor_diagnostic preflight \
  artifacts/actor-procedure-v32-execution-v2/plan.json \
  artifacts/actor-procedure-v32-execution-v2/tokenizer-preflight-pinned.json
```

It must use the cached pinned tokenizer, record template/prompt/token-ID hashes,
reserve 128 output tokens against context 8192 without truncation, and produce
eight matching request records. The worker repeats that preflight and compares
it, verifies source files, and enforces the recorded Python/packages and A10/A10G
runtime before model creation. Loading remains local-cache-only. Qwen revision,
CUDA FP16, greedy generation, seed 0, caps and one finite 600-second worker with
no retries are unchanged. Writer/repair cap 1024 remains recorded, but no writer,
action review, action repair or game is invoked.

Only after actual preflight and separate inference authorization:

```sh
.venv/bin/python -m game_memory.actor_diagnostic execute \
  artifacts/actor-procedure-v32-execution-v2/plan.json \
  artifacts/actor-procedure-v32-execution-v2/execution-001 \
  --preflight artifacts/actor-procedure-v32-execution-v2/tokenizer-preflight-pinned.json
```

This execution was **not performed**. There is no cloud submission in this task.
Do not repair macOS Java as a prerequisite for isolated proposals: this worker
does not start the simulator. Java remains a separate gameplay prerequisite.
Java 8 rejects the flags; recorded macOS Java 17 builds lack the Linux
`os+container` tag. Clearer errors diagnose these problems without resolving them.
Keep the intended logging options and experiment environment unchanged.

## Conditional development sequence — proposed only

**A. Eight-call actor replay.** Hypothesis: the unchanged v32 replacement procedure
improves these prerequisite/completion decisions. Intervention: only the paired
primary system replacement; controls: exact saved baselines, slicing and eating.
Observe syntax, legality, targeted actions, exact baseline text and normalized
agreement separately. Both failure baselines must reproduce premature eating,
both salt candidates must choose legal take salt, and both controls must preserve
their selected actions. Do not promote on syntax or legality alone.

- Both salts improve and controls pass: next propose baseline/candidate pairs on
  the original bounded salt inputs. If those pass, propose original/reversed/
  rotated presentations of the saved method-selection failure with existing slice
  controls. Each step needs a fresh authorized identity and a regression gate.
- Only one salt improves: report trajectory sensitivity; stop tuning on the other.
- Neither improves: stop adding instructions and move to separate fact readouts.
- A control misses its selected criterion: do not promote. Inspect whether the
  alternative is harmful or useful; a narrow miss is not automatically proof of
  general gameplay regression.
- A baseline changes actions: mark its pair non-informative; no replacement calls.
- Wording-only drift: preserve failed exact reproduction and score action agreement
  separately. An information action can be understandable but is not this salt fix.

**B. Fact identification if actor errors remain.** Hypothesis: requirements or
state interpretation may contribute to the failed proposals. Ask separately for
required ingredients, confirmed possession, completed ingredient operations and
whether meal preparation occurred, using the same two salt histories and saved
slice/eat histories as controls. Score only against public evidence offline;
never feed corrected readouts back to the actor. Wrong requirements retain
reading/interpretation as a candidate; correct requirements with wrong possession
or progress retain state interpretation; accurate readouts beside wrong actions
strengthen action selection as an explanation. Stop before claiming causality:
changing the elicitation task does not directly measure an internal reasoning stage.

**C. Writer fidelity, separately versioned.** Hypothesis: a single update procedure
may preserve supported facts across unrelated feedback. Freeze short saved public
pickup/preparation/unrelated-observation sequences. Compare v17 with one candidate,
using prior successful recipe/grilling updates as narrow controls. Each arm must
carry its own preceding model-written memory, without Python-filled facts. Keep
prose/model-managed JSON and the shared allowance, including plans. Observe
possession, accumulated operations, recipe retention, unsupported completion and
stale context separately. Gate on those separate fidelity criteria and stop on
regressions; do not repeat reminder additions or field ordering as new explanations.
No writer changes were implemented here.

**D. JSON repair separately from semantics.** Hypothesis: presentation may affect
repair of these particular malformed candidates. Compare compact/readable forms,
changing only whitespace outside strings while retaining content, nesting, extra
delimiter, roles, system instruction and feedback. Use the labeled successful
synthetic extra-brace probe as a control. Require strict syntax and content
preservation independently; stop if either is lost. Never silently repair input
or substitute corrected output, and do not infer universal inability from failure
of this formatting intervention. No production repair change was implemented.

**E. Gameplay only after component gates.** Hypothesis: component improvements may
transfer to complete roomy gameplay. Propose a separately authorized four-episode
prose/JSON × seeds 0/1 calibration with fixed model, budget, allowance and reread
price. Controls are the fixed paired development conditions and prior raw evidence,
not a held-out success estimate. Inspect complete gameplay and memory traces;
stop on fidelity/prerequisite failures before returning to the eight-cell
memory-price MVP. No episodes, fine-tuning, larger models, held-out evaluation,
hybrid work, sweeps, dashboards, optimization or general batch/resume are authorized
or implemented by this checkpoint.

**TLDR:** execution-status correction implemented; orchestration, retained evidence
and scoring verified with CPU fixtures; actual tokenizer/runtime and Qwen behavior
remain unverified; the single next action is actual cached-tokenizer preflight in
the existing pinned Linux environment when separately authorized and available.
