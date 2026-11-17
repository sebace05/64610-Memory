# Modal calibration launcher

Historical checkpoint instructions. For the current v31/v17 configuration and
maintenance source boundary, see [the workflow guide](workflow-maintenance-2026-11-16.md).
Restore the saved snapshot for frozen launchers; current maintenance source does
not share their historical digest.

Use `python3 scripts/modal_calibration.py` from the repository root. The laptop
uses the user's working Modal 1.6.4 installation. The broken laptop `.venv` is
not required. All project commands run in `/opt/memory/.venv` on Modal.

The launcher implements only the frozen v17/v30 JSON seed-1 migration pilot
described in `codex-modal-handoff-prompt.md`. It does not schedule a comparison.
One A10, four CPUs and 32 GiB host RAM are requested, with a 600-second startup
limit and a 3,600-second GPU function limit. The episode subprocess has a
3,300-second limit to leave time for evidence persistence and offline auditing.
CPU preflight uses no GPU. No automatic application-level retries are enabled.

The first remote preflight on November 16 passed 389 tests without skips in
404.69 seconds. Its reference is
`artifacts/modal/modal-a10-cpu-20261116T182256Z-7d073670.json`. The one GPU pilot
completed successfully: score 1.0 in 11 actions. Its reference is
`artifacts/modal/modal-a10-gpu-20261116T183246Z-0e520586.json`.
See [the pilot report](modal-pilot-2026-11-16.md) for measured outcomes,
trace findings, source provenance and evidence paths.

Both remote jobs use uploaded snapshot
`60e7d33508ac9ca617fb78d10501b62802220e0b6919246bcf73cbeb730a1993`
and image `im-lUVTCGHpNdXdw1DYmPurBg`. After GPU submission, the laptop's fetch
helper was corrected to precreate its recursive-download directory and verify
the downloaded source ZIP. That isolated retrieval fix passed all ten local
launcher checks. It does not change the already-submitted remote worker or
the frozen executable-source digest. Remote source ZIPs preserve the exact
executed launcher/tests; use those for provenance.

## Submit and reconnect

```sh
python3 scripts/modal_calibration.py submit cpu
```

Submission prints and saves a reference under `artifacts/modal/`. It records
the active workspace/profile, source snapshot, exact policy, image/app/function
IDs and function-call ID. Substitute its actual path below:

```sh
python3 scripts/modal_calibration.py status artifacts/modal/CPU_REFERENCE.json
python3 scripts/modal_calibration.py logs artifacts/modal/CPU_REFERENCE.json
python3 scripts/modal_calibration.py fetch artifacts/modal/CPU_REFERENCE.json
```

Only after CPU status is `completed`, with the full suite and no skips:

```sh
python3 scripts/modal_calibration.py submit gpu --preflight artifacts/modal/CPU_REFERENCE.json
```

GPU submission requires a successful preflight of exactly the same uploaded
source snapshot. Keep launcher/source/tests fixed between preflight and GPU
submission. A local `artifacts/modal/gpu-pilot-reservation.json` prevents casually
submitting a second paid pilot. Preserve this reservation and all failed attempts;
another GPU episode requires a new instruction and review of the evidence.

Use the GPU reference with the same `status`, `logs` and `fetch` commands. Use
the reference's original Modal profile/workspace when reconnecting. Fetch always
chooses a fresh local directory under `artifacts/modal-downloads/` and checks
the downloaded plan, source manifest and source archive hashes. Modal nests the
remote run directory inside that fresh directory; the printed path is the
verified evidence root.

## Execution and evidence

Submission uses `App.run(detach=True)` and `Function.spawn`; the job and its
offline audit execute remotely. The laptop may disconnect after the submitted
reference has been written. Remote compute completion does not start a new Codex
turn; bring the saved reference to the next session for review.

Project source is uploaded through an explicit allowlist. Neither credentials,
Git internals, environments nor model weights are uploaded. Only the historical
trace fixtures required by CPU tests are included; they do not enter model inputs.

Volumes are `memory-research-cache` for Hugging Face files and
`memory-research-results` for evidence. Each invocation gets a fresh run root.
Before weights can load, the remote worker commits an immutable submitted plan
and an attempt marker. A replay refuses the existing run before loading a model
and writes a separate replay-rejection record. Functions are limited to one
container each; this launcher is for one sequential GPU owner.

Each run retains source hashes and an uploaded-source ZIP, runtime/package/Java
identity, subprocess output and actual exit-status records, plus a periodically
committed status file. GPU runs also save driver/GPU identity, GNU time peak-RAM
evidence, the immutable condition manifest, raw actor/writer traces, result/error
records, independent condition audit, cached-tokenizer recount and gameplay
inspection. A gameplay loss can complete successfully; an infrastructure or
audit failure has status `failed` and is never silently retried.

Cloud protocol: `qwen-calibration-v17-v30-modal-a10-pilot-v1`. Cloud evidence stays
separate from the old RTX six-cell checkpoint. Human review of actual gameplay
and memory is still required before any policy change or additional episodes.
