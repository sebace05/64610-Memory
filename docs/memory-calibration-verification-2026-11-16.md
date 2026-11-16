# Independent T1–T6 verification — November 16, 2026

**Result: the engineering gate is complete. A, B, C, and D have handed off READY,
and no implementation blocker was found for beginning T7 calibration.**
Calibration has not been launched by this verification. Successful production
Qwen writing, gameplay, and binding memory limits remain unverified under the new
policy; they are the purpose of T7.

**Roles and tasks**

| Role / task | Verified result | Evidence |
| --- | --- | --- |
| A / T1: shared memory policy | Complete. v17 accepts syntax-valid, within-limit model content, including omissions/errors/empty writes; one repair; exact previous-state fallback; no programmed recipe/inventory/progress correction. | Reviewed `memory.py`, its tests and integration tests, live metadata, and [A's READY handoff](dev-handoffs/memory-calibration/A.md). |
| B / T2: shared actor | Complete. Explicit v30 selection, missing-information recovery guidance, available legal rereads/repeats, model-based reviews, and no inspection-cache use in the new path. Historical defaults preserved. | Reviewed actor diff, isolation/review tests, live metadata, and [B's READY handoff](dev-handoffs/memory-calibration/B.md). |
| D / T3: preflight identity | Complete. Schema-2 manifests include memory/protocol/source identity before weights; existing-result identities checked; source digest and protocol appear in episode evidence. All searched callers adapted. | Reviewed pilot/CLI/runner/evaluator diffs and preflight mismatch/no-weight-allocation tests. |
| C / T4: evidence and analysis | Complete. Independent condition audits, writer provenance/empty/fallback/size metrics, exact declared-grid validation, missing/error/duplicate-cell handling, and matched allowance contrasts. | Reviewed analysis and diagnostic code, synthetic arithmetic/failure tests, and [C's READY handoff](dev-handoffs/memory-calibration/C.md). |
| C / T5: annotation fixtures | Complete. Public-evidence checklists for seeds 0/1, event references/quotes, and separate retention/claim-accuracy assessments. No live semantic intervention. | Reviewed [annotation guide](memory-annotation-guide.md), fixtures, and tests checking their public evidence. |
| D / T6: integrated checks | Complete. D recorded a 380-test pass; this review independently repeated the full suite and added two combined v17/v30 simulator wiring checks. | [D's READY handoff](dev-handoffs/memory-calibration/D.md), results below, and [integration gate](memory-calibration-integration.md). |

All four handoffs state that implementation edits have stopped. No component
interface, simulator, model-adapter, or dependency-file changes were found.
Runner changes are source/protocol identity additions, preserving its execution,
memory-bound, and inference-accounting responsibilities.

**Independent checks performed**

The prescribed full suite initially stalled in the restricted local Java gateway
environment. It was interrupted with exit 130; its output included a failure
marker but no completed failure traceback. It is not reported as a passing run.

The full suite was rerun with local gateway access and D's documented JVM
environment settings, without changing tests or code:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
JAVA_TOOL_OPTIONS='-XX:-UsePerfData -Xlog:os+container=off:stdout -Xlog:os+container=warning:stderr' \
.venv/bin/python -m pytest -q
```

Result: **380 passed in 48.69 seconds, exit 0**, no skips or failures.
`git diff --check` also passed.

The suite covers v30 actor behavior and v30 preflight, and production memory
strategies through the adapter/runner. To check the exact new writer/actor
combination explicitly, this review additionally ran both production memory
strategies with actor v30 through the real Java simulator using the existing
scripted writer fixture. Both checks passed and independently audited their
trace accounting. Each exercised a repaired write, a previous-state fallback,
and primary accepted writes; all inference remained scripted.

Those two checks are labeled `integration_fixture`, never research-model
evidence. Their raw traces and summary are preserved in
[artifacts/t1-t6-verification-3zlnm4bm](../artifacts/t1-t6-verification-3zlnm4bm/).
No GPU, pinned production checkpoint, model/tokenizer download, or prompt tuning
was used in this verification.

Live metadata matches the shared contract:

- Memory: `p1-memory-v17`, version 17,
  `syntax_and_size_one_repair_previous_state_v1`,
  `semantic_validation: none`, `fallback: previous_valid_memory`.
- Actor: `s2-action-v30`, with the declared format-neutral Qwen review and
  unavailable-action repair policies.
- Rendering remains `p1-render-v2`.

**Source and preservation**

Git HEAD is still `739e72def5ef65d8e0a8fd24d879cdc401de2066`; the new implementation
is in the working tree and is not committed. The tested executable source digest is:

```text
f4c9b85a1594d02e3b2ac6ae225a4e82b9b0566ab6b545cc93d055d5cd860afb
```

The original reproduction ZIP checksum is valid. Every one of its 42 archived
files was compared with the current corresponding file; **none changed**.
This preserves the v16/v29 baseline, including its raw traces and recorded
launcher-status limitation.

Freeze/archive the actual tested implementation and its protocol before running
calibration; the old Git SHA alone does not identify these uncommitted changes.
This verification added only this report and clearly labeled fixture evidence;
it did not edit implementation files or another role's handoff.

**Next: T7 calibration**

1. Fix the calibration settings and preserve the implementation/source snapshot.
   Select v30 explicitly; the global actor default remains historical v1.
2. Recheck full-history capability with the new shared actor.
3. Run prose and JSON with generous memory on the two preselected development
   seeds. Inspect real Qwen memory content, acceptance, factual quality, recovery,
   gameplay, and generation-limit hits.
4. Only then explore smaller allowances and, if necessary, separately versioned
   task difficulty. Choose common tight/generous levels from calibration evidence.
5. Freeze the subsequent comparison. The allowance values and 8-versus-16-game
   decision have not been silently selected by this implementation or review.

The existing 313-test baseline and current 380-test pass are engineering evidence,
not evidence of new-policy gameplay success. Calibration remains necessary even
though T1–T6 and the A–D implementation assignments are complete.
