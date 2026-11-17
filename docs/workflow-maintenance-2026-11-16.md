# Current development workflow and maintenance boundary

The current research configuration is actor `s2-action-v31`, writer
`p1-memory-v17`, renderer `p1-render-v2`, Qwen/Qwen3-4B-Instruct-2507 revision
`cdbee75f17c01a7cc42f958dc650907174af0554`. CUDA FP16, greedy decoding,
generation seed 0, context 8192, actor output cap 128, writer/repair cap 1024.
The roomy calibration used train-fold development seeds 0/1, one room, two
ingredients, unlimited inventory, budget 80, stored allowance 512 and reread
price 2, for prose and structured JSON. Keep these controls fixed within a pilot.
Prices 2/5 in the earlier MVP are a different comparison; do not merge identities.

## One explicit launch path

Use `game_memory.pilot` to log and launch `game_memory.run_episode`. Real
inference now requires `--actor-prompt`; fake fixtures retain their v1 default.
The Python actor constructor retains its historical v1 default for callers.
The older Colab notebook deliberately selects v3 and remains a historical
one-room/one-ingredient checkpoint, rather than the current configuration.

For a future authorized run in the pinned GPU environment, the configuration is:

```sh
.venv/bin/python -m game_memory.pilot \
  --output-dir artifacts/NEW_REVIEWED_IDENTITY/prose-p2 \
  --backend transformers --pilot --prepare-only \
  --protocol-id NEW_REVIEWED_IDENTITY \
  --actor-prompt v31 --strategy prose --seeds 0 1 \
  --model-id Qwen/Qwen3-4B-Instruct-2507 \
  --model-revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --device cuda --dtype float16 --context-limit 8192 \
  --generation-seed 0 --action-max-new-tokens 128 --memory-max-new-tokens 1024 \
  --num-locations 1 --num-ingredients 2 --game-fold train \
  --action-budget 80 --memory-token-limit 512 --recheck-cost 2
```

This is a configuration template, not a new frozen identity or authorization to
run inference. `--prepare-only` validates runtime and writes a manifest without
loading weights. Declare a fresh identity and review the source before any future
execution; use a separate condition directory for structured JSON. Never reuse a
historical manifest with maintenance source. No cloud jobs were submitted here.

## Maintenance changes

Root pytest discovery now targets `tests/` and excludes `artifacts/`, `.venv/`
and `.git/`. Archives remain untouched. Before editing, root collection produced
111 collection errors and 403 collected tests; this differs from the previously
reported 105 errors. With configuration, the original intended suite collected
405 tests cleanly. Additional maintenance tests increase that count.

The Modal upload allowlist now includes `pytest.ini`; source snapshots capture it
and the shared source digest includes it. CPU preflight explicitly collects and
runs `tests/`, checks subprocess success and JUnit failures/errors, requires a
nonempty suite, and rejects every skip. The arbitrary 380-test floor is removed.
The mandatory v31 provenance regression remains. A local suite with optional
packages skipped is therefore insufficient for remote preflight.

Actor cleanup removes the uncalled `_repeats_known_information`, its word-overlap
helper, dead feedback branch, and inspection cache/update machinery. Searches of
callers, tests, notebooks and documentation found no callers of that guard.
Historical immediate-repeat exclusion (v19–v21) remains. Repeated policy groups
are explicit named sets. Shared repair identifier constants live in
`components.py`; the auditor independently checks fields, latest memory,
same-turn recorded proposals and inference accounting. It does not use actor
capability sets to decide whether evidence is valid.

All 32 historical/current policy choices remain available: v1–v31 and
v2-mechanics. v1 is the fixture baseline, v3 the Colab checkpoint, v29 the
v16 comparison, v30 the migration/full-history comparison, and v31 current.
Intermediate versions remain for compatibility with existing regression tests
and documented development comparisons. No unsupported claim of commit-based
reproduction was used to retire them. Further retirement needs a caller and
provenance inventory, rather than a numeric cutoff.

## Exact historical reproduction

Use the preserved source, tests and launcher together, outside this checkout:

- v31 full-history controls: uploaded snapshot
  `ce63a4742287e9bcbfbe2a1d4482da7c2a767167a67f948d1a8c1d237daabaed`;
  executable digest `1cc6aec3a37373e057887185207439e5f9a3a57ae576d89ffe69ac41f3a93429`.
- Original bounded v31/v17: source staging snapshot
  `artifacts/modal/source-staging/0850c519629af699e1aec65451ca1200e9f3df1a187b117b8cb839b8ac839207/`.
- Audit-only addendum: source staging snapshot
  `artifacts/modal/source-staging/119ef30d5263b2a01d1b8389281ee2e753dfdcd7b6af0ec8f8b4e43c3a1327c2/`,
  executable digest `4842d1833f630ac961a39025eb1f8ad6a4ba2bfed51eb87605644dc0951728ce`.
  Its `game_memory/actor.py` matches the pre-maintenance dirty actor byte for byte
  (SHA-256 `6c6b291f4272eac5b5c4a66a35fdeaf5cf06cc62c0b8c47b02ba9ae4bad7b840`).

Uploaded-source ZIPs and source-file manifests in the downloaded runs are the
authority; the v31 dirty archive is not claimed to be reproduced by Git HEAD.
See [the calibration report](v31-v17-roomy-calibration-2026-11-16.md) for the
original failed audit, corrected audit and source/protocol split. Neither was
rewritten. The combined diagnostic package is
`artifacts/modal/saved-request-diagnostics-v2-evidence.zip` with adjacent SHA-256.

`modal_calibration.py` retains its frozen digest, historical resources, fixture
counts and protocol constants. Maintenance source intentionally differs; submit
now refuses that mismatch locally before accessing Modal. Do not replace the
constant to bypass this guard. A future executable launcher needs a separately
declared identity. The two replay harnesses remain frozen diagnostic workflows;
the second's zero-call packaging failure and four-call interruption recovery are
historical attempt handling, not general resume support. Their base images and
layered source must be restored together. No general scheduler was added.

## Next behavioral checkpoint (separate work)

The latest diagnostic used 31 calls across attempts (0, 4, 27), with 12/13 exact
saved baseline responses. The remaining response added “the” to next_direction
while keeping the correct slice action; exact reproduction failed visibly.
One ordering control spans workers. Reversed/rotated actions fixed one wrong-cut
request, writer reordering preserved one dropped recipe, and same-view unbounded
history fixed slicing. Both salt cases still proposed unavailable eating.
Real JSON repairs still failed in both roles; a newly constructed synthetic
extra-brace control succeeded. These results establish neither a general writer
fix nor bounded gameplay success. Reminder additions and field order tests have
already been performed and should not be presented as new experiments.

Start with the two saved salt-state requests. Freeze a minimal procedure prompt
that explicitly distinguishes ingredient preparation, carried ingredients and
successful meal preparation; compare each exact baseline against that single
change, with the existing successful eating and slicing requests as controls.
Keep all public evidence fixed and score action legality separately from semantic
correctness. This tests prerequisite/completion decisions that public history
alone did not resolve. It requires a new prompt version and experiment identity.

Then isolate writer fidelity with the saved confirmed chicken-pickup and grilling
updates: retain possession and accumulated completed operations across the next
unrelated observation, while separating recipe requirements, observations, plans
and completion claims. Use the already successful recipe/grilling updates as
narrow controls; score stale budget values separately. Test one update procedure
change, without rerunning field ordering as a new explanation.

For method robustness, apply that candidate only to the existing original,
reversed and rotated action presentations and the existing slice controls.
For JSON repair, compare each real malformed candidate with a synthetic candidate
matched in content and length, changing only the extra delimiter, with a valid
candidate as a no-change control. This distinguishes syntax difficulty from the
unmatched content/context of the earlier synthetic probe. Keep offline expected
answers outside messages. Selected-request success would still require fresh
gameplay validation before a bounded comparison. No deterministic rescue, hidden
state, semantic memory rejection, larger sweep or model change is justified here.

## Local validation of this maintenance change

All checks used `.venv/bin/python` (Python 3.12.1); no global-Python fallback,
package installation, GPU job, model download, push or deployment was used.
Final root `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest
--collect-only -q` collected **422 tests**, with no archive collection errors.

Focused actor/auditor/Modal/replay/digest/explicit-selection checks passed
**140 tests** in 3.23 seconds with simulator loopback access outside the sandbox.
The subsequently added direct-script frozen-source refusal check also passed;
all **18 Modal launcher tests** passed after that addition. It verifies refusal
before Modal import/cloud access, including when launched directly by filename.

An offline differential check loaded the exact pre-maintenance dirty actor and
compared requests, purposes, outputs and metadata against the refactor for all
32 policies × two context modes × six response scenarios, two turns each:
**384 combinations matched exactly**. Scenarios include primary acceptance,
prepare review, repair-to-review, malformed failure, article normalization and
ingredient eating. Existing behavioral tests remain the independent assertions;
this finite comparison is not a proof over all possible outputs.

The full command `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest
-q -ra` completed outside the sandbox before the final direct-script test was
added: **396 passed, 24 skipped, one failed** in 19.11 seconds (421 tests).
The failure is `test_cli_prepare_and_launch_guard_work_together`: the pilot's
Java 17 logging options are rejected by the installed Java 8, producing an empty
Py4J port response and an initialization error. Directly invoking Java with
`-Xlog:os+container=off:stdout` confirms “Unrecognized option.” One skip targets
Java 9+ logging; the other 23 require absent Torch. The pinned remote runtime,
model adapter and full Java 17 suite therefore remain unverified here.

Initial sandbox runs blocked in Py4J `launch_gateway` while reading the port;
they were interrupted with their partial output retained. An outside-sandbox
run also exposed a test leaking launcher Java options into subsequent tests;
that prepare-only test now isolates `os.environ` using pytest's monkeypatch.
Production Java options and test assertions remain unchanged. Intermediate
failed runs were not called passes. The completed full run still exits 1;
preflight would correctly reject this laptop result.

Logs, raw-evidence inspection, the differential script and pre-maintenance actor
are retained in `artifacts/maintenance-review/20261116-focused-simplification/`.
The raw diagnostic attempts remain 0/4/27 calls, with baseline drift preserved.
No inference was performed to validate this maintenance change. Passing CPU
checks or shorter code does not demonstrate that Qwen plays correctly.
