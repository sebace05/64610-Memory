# Modal full-history seed-1 control

The unchanged v30 control completed technically but lost through budget exhaustion:
score 0.8, 79 action attempts, 80 budget units spent, one recipe reread.

At action 8 / event 45, `prepare meal` returned "Adding the meal to your inventory."
Its allowed-action list included `eat meal`. Actions 9–79 were 71 invalid
attempts to prepare again, with no further simulator execution. The actor,
review and repair path kept returning preparation proposals despite the full
public history retaining meal creation. This reproduces the old seed-1
finalization failure on Modal. It cannot be attributed solely to bounded-memory
omissions; the next policy experiment should investigate finalization priorities
across actor, review and repair. An existing eat-meal instruction already exists,
so adding another copy alone is not a demonstrated fix.

No model-facing policy was changed. Qwen3-4B-Instruct-2507 revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, actor `full-history-v30`, greedy FP16,
generation seed 0, context 8192, actor cap 128, train game seed 1, one room,
two ingredients, budget 80 and reread price 2. Full history is exempt from the
512-token stored-memory limit and invokes no Qwen writer. The final history
was independently retokenized remotely without applying a bounded-memory cap.

The requested A10 resolved to NVIDIA A10; the earlier JSON pilot resolved to
A10G. Both use Python 3.12.10, Torch 2.8.0/CUDA 12.8, Transformers 4.57.6 and
Modal 1.6.4. These single observations do not establish a format advantage.

Runtime: model load 6.28 seconds, episode 394.97 seconds, synchronized generation
392.35 seconds. Usage: 682,347 input and 8,972 output tokens across 79 action,
76 repair and 81 review calls; no writer calls. All usage reconciles.

Updated remote preflight passed 390 tests with zero skips. The frozen executable
digest remains `f4c9b85a1594d02e3b2ac6ae225a4e82b9b0566ab6b545cc93d055d5cd860afb`.
Uploaded launcher/test snapshot:
`9b91b9c38d91c0f7338115bb7ffad56e90629738d8b33c456bb948c14c8b0e82`.
Only launcher selection/auditing was extended; original JSON evidence and its
reservation remain intact. The new control has its own reservation and protocol
`qwen-v30-modal-a10-full-history-control-v1`.

GPU reference: `artifacts/modal/modal-a10-gpu-20261116T185416Z-bc4b88b2.json`.
CPU reference: `artifacts/modal/modal-a10-cpu-20261116T184643Z-953d345f.json`.
App: `ap-9SYtti1fFx7fS9ZbGovcmA`.
Raw results persist in `memory-research-results/modal-a10-gpu-20261116T185416Z-bc4b88b2`.
Verified downloaded evidence:
`artifacts/modal-downloads/modal-a10-gpu-20261116T185416Z-bc4b88b2-405908ab/modal-a10-gpu-20261116T185416Z-bc4b88b2/`.
Remote condition audit passed and matched a fresh audit of the downloaded trace.
This was one authorized control; no additional GPU episodes were launched.

Reconnect with `python3 scripts/modal_calibration.py status REFERENCE` or
`python3 scripts/modal_calibration.py fetch REFERENCE`, using the GPU reference
above. The evidence ZIP is `artifacts/modal/full-history-seed1-20261116-evidence.zip`
with adjacent SHA-256. Raw traces and exact uploaded source are included; model
weights, environments and credentials are excluded.
