# Actor v31 finalization checkpoint

Both full-history development controls succeeded on Modal: seed 0 in 11 actions,
seed 1 in 9 actions, each score 1.0. Each prepared the meal and ate it on the
immediately following action. The preserved v30 seed-1 control had exhausted its
budget after meal creation, with 71 invalid attempts to prepare again.

## Changes

Actor v31 preserves v30 as a selectable baseline. A shared prompt priority now
asks actor, preparation review and unavailable-action repair to check for an
available prepared meal first, then assess unfinished recipe prerequisites.
Repair explicitly excludes the rejected unavailable proposal. Mechanical
legality validation now precedes preparation review for v31: unavailable prepare
proposals go directly to repair. Review outputs are still validated, and failed
repairs remain invalid attempts. Python never selects a useful action for the
model. The writer, environment, task settings and model configuration did not
change. v31 retains the format-neutral, current-evidence-only actor interface.

The new actor metadata identifies legal preparation review and shared
finalization/excluded-proposal repair. The default actor remains historical v1;
new runs must explicitly select `--actor-prompt v31`.

## Validation and scope

99 focused local actor/launcher checks passed. The full suite passed 394 tests
with zero skips in the remote image before inference. New behavior tests cover
unavailable preparation after meal creation, legal preparation review, invalid
review output, successful model repair, and refusal to replace failed repairs
with a programmed action. Existing v30 regression tests passed unchanged.

Protocol: `qwen-v31-modal-a10-finalization-controls-v1`.
Executable digest: `1cc6aec3a37373e057887185207439e5f9a3a57ae576d89ffe69ac41f3a93429`.
Uploaded snapshot: `ce63a4742287e9bcbfbe2a1d4482da7c2a767167a67f948d1a8c1d237daabaed`.
CPU reference: `artifacts/modal/modal-a10-cpu-20261116T190946Z-e400a701.json`.
GPU references:
`artifacts/modal/modal-a10-gpu-20261116T191725Z-120cd36b.json` (seed 0),
`artifacts/modal/modal-a10-gpu-20261116T191944Z-3d596c40.json` (seed 1).

Qwen3-4B-Instruct-2507 revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, greedy FP16, generation seed 0,
context 8192, actor cap 128. Train fold, one room, two ingredients, action budget
80 and reread price 2. Full history is exempt from the bounded-memory cap and
invokes no writer. Both remote audits passed and matched independent audits of
the downloaded traces. Model cache/results persist in the existing Modal volumes.

These two development successes support the bundled v31 finalization change.
They do not isolate which of its prompt/routing changes caused improvement or
establish robustness on held-out games. Rereads and unnecessary actions remain.
The next checkpoint is prose/JSON generous-memory calibration with v31 and the
unchanged v17 writer, using a fresh declared plan. No bounded episodes, writer
changes or additional GPU episodes were included in this checkpoint.

Detailed outcomes, inference accounting, runtime and exact evidence roots are in
`artifacts/modal-review/actor-v31-finalization-20261116/summary.json`.
The combined evidence ZIP is `artifacts/modal/actor-v31-finalization-20261116-evidence.zip`
with adjacent SHA-256. It includes raw traces/results, audits, uploaded source,
references and this report, excluding model weights, environments and credentials.
