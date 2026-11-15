# Friday MVP: the next checkpoint

Use one entry point: [qwen_colab.ipynb](../notebooks/qwen_colab.ipynb).
It runs **one separately labeled one-room/one-ingredient full-history test on seed 0**.
Qwen stays loaded for explicitly chosen follow-up runs in the same live runtime.
This Colab path and the steps for other users remain unchanged. Local development
has now verified the same pinned Qwen revision on the RTX 5070 Ti; see
[the local results and trace notes](mvp-results.md).

## What is actually verified

| Area | Evidence | Still unverified |
| --- | --- | --- |
| Simulator and runner | Automated real-Java tests; fixed replay/accounting checks. | The full suite does not establish useful model behavior by itself. |
| Qwen inference | RTX 5070 Ti, Qwen 4B pinned revision, FP16, enforced greedy decoding. Full-history v11 succeeded on two development seeds. | Broader capability and memory-strategy effects. |
| Actor | Two full-history two-ingredient games reached meal preparation and eating. | Some successful traces still deviate from global recipe order. |
| Memory | Prose/JSON writers have repair, fallback, rendering-limit, and isolation checks. The v29/v16 eight-cell local development replay completed without budget-exhaustion loops; prose won four cells and JSON lost four through gameplay choices. | Broader seeds and a frozen memory-strategy comparison. |
| Execution | Local real-Qwen manifests, Java handling, durable raw traces, and accounting reports. | Production-Qwen session reuse in Colab remains a separate workflow check. |

Local tests use scripted inference or tiny random weights where indicated.
The paired v11 results evaluate the actual checkpoint locally; earlier uploaded
traces remain evidence of their original Colab runs.

## Shared Colab workflow (unchanged)

1. Open [the current notebook in Colab](https://colab.research.google.com/github/sebace05/64610-Memory/blob/main/notebooks/qwen_colab.ipynb).
   `REPO_REF=None` resolves main once, checks out that immutable commit, and records
   it. Set a full SHA for a frozen protocol or exact replay. Reopen this link for
   code/configuration updates; a saved Colab copy retains its own configuration.
2. Select a **T4 GPU**. Keep Qwen revision
   `cdbee75f17c01a7cc42f958dc650907174af0554`, FP16, actor `v3`, budget 80,
   reread price 2, greedy decoding, context limit 8,192, and generation seed 0.
   The new condition sets `num_locations=1`, `num_ingredients=1`, and `FIRST_SEED=0`.
   The engine still generates the recipe; no scripted solution reaches the model.
   Keep the successful v3 prompt unchanged. The adapter now passes
   `use_model_defaults=False`: Transformers 4.57 previously overrode its requested
   greedy configuration with checkpoint sampling defaults. Existing success/loss
   traces remain development evidence with that protocol deviation; do not pool
   them with corrected-policy runs. Choose **Runtime → Run all** and authorize Drive if prompted.
   It runs the following stages automatically, then stops after one episode.
3. Sections 1–3 preserve the pinned checkout, mount Drive, install
   isolated dependencies, and save CPU/Java/adapter checks plus a dependency freeze.
4. Run section 4. It validates hardware and records the attempt's immutable
   manifest without loading weights. Old data is never adopted or overwritten.
5. Section 5 reuses a matching live session or closes it before loading changed
   code/model settings. A new session loads Qwen in the isolated process and prints
   `ready: true` plus the measured model-loading time. Only the connection lives
   in the Colab notebook kernel; its preinstalled libraries stay separate.
6. Run section 6 once. It creates a fresh environment and history, using the
   already-loaded model/tokenizer. Then run section 7 and the ZIP-download cells.
   Return this ZIP for comparison with the already-audited small-game trace.
   If a run/audit fails, the final download cell can still package available logs.
7. When finished, run `session.close()` in a new cell and disconnect the GPU.

## Run the same checkpoint locally on an RTX 5070 Ti

This is an optional local path. It does not change the notebook or the steps other
users follow in Colab. It uses the same model revision, prompt, task, seed, and
greedy decoding; the local launcher selects BF16, while the shared T4 notebook
continues to select FP16. Each run gets a new local artifact directory by default.

From the repository root, install Java 17 (if needed), then create the project
environment and install the pinned model dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-model.txt
```

Use a CUDA-enabled PyTorch build compatible with your NVIDIA driver. The launcher
checks that PyTorch sees the RTX 5070 Ti and supports BF16 before recording a pilot
or loading model weights. Then run:

```sh
./scripts/run_local_qwen.sh
```

The first run downloads the pinned Qwen checkpoint from Hugging Face. Results and
logs are saved under `artifacts/local-qwen-<UTC timestamp>/`, which is ignored by
Git. To choose a directory explicitly, pass it as the first argument:

```sh
./scripts/run_local_qwen.sh artifacts/local-qwen-greedy-repeat
```

Use a fresh directory for each attempt; pilot manifests reject changed settings
or duplicate seeds. If BF16 is unavailable in the installed PyTorch build, set
`LOCAL_QWEN_DTYPE=float16` for an FP16 run. Its manifest records the actual dtype,
so keep it in its own directory. The local script does not run the Colab-only
session reuse flow; it launches one episode and exits.

The successful small-game run took **10.84 seconds playing plus 89.67 seconds
loading**, excluding setup/tests/idle time. Reuse targets loading cost; warm-run
timings and longer games still need measurement. One seed-0 repeat is justified
to confirm actual greedy gameplay after correcting the decoder. Do not change
the prompt or task at the same time. No further jobs are scheduled automatically.

## Fast development loop within one live runtime

After inspecting one result and choosing the next run, edit SETTINGS/FIRST_SEED,
rerun section 2 for a new PILOT_DIR, section 4, then sections 6–7 and download.
Skip installation/tests and model loading while code/dependencies/model settings
are unchanged. Every attempt remains a separate condition with fresh game state,
history, and inference accounting. Only model weights/tokenizer persist.

For a simpler repeat, choose **Run all** again. It creates a new attempt and
rechecks dependencies/tests; a compatible loaded model is reused. The section
selection above avoids repeating checks when only game settings change.
Colab still needs a connected GPU runtime and may request Google authorization;
this is not an unattended scheduler. This chat cannot start or control that runtime.

Changing model/revision/precision/generation settings requires a new loaded
session. Run all replaces it automatically. Repository code changes need a new
committed checkout and checks; the worker rejects stale code.
It does not hot-reload code into existing weights. An interrupted notebook read
closes the worker to avoid pairing a later request with an earlier response.

A Colab disconnect/reclaimed runtime loses the loaded process. Hugging Face's
local cache avoids repeated downloads while it exists; Drive preserves research
logs. Neither restores GPU memory or resumes an interrupted game. Do not pickle
the model or reuse a previous agent's history as a shortcut.

## What the smaller game can establish

The engine supports one room and one ingredient without custom rewards or hidden
solutions. A public-action mechanics fixture completes seed 0, including cooking,
preparation, and eating. This is a manual simulator check, not a Qwen result.
Reducing locations also changes generated ingredients/preparation, so this is a
new task configuration rather than a one-variable prompt comparison.

If Qwen succeeds, inspect the trace and check another preselected development
seed before increasing difficulty one step at a time. A one-ingredient game may
put too little pressure on memory for a useful prose/JSON comparison. Freeze a
single viable configuration for both strategies and both prices; preserve all
failed configurations and do not select seeds because they succeed. If even this
capability check fails, inspect that trace before changing prompts or policy.

## Saved evidence

Each new `PILOT_DIR` in Drive contains:

- `pilot-manifest.json`: code revision, actor settings, game settings, model
  revision, precision, and runtime/package identity. It is immutable.
- `checks-<id>/`: dependency check, Java version, pytest output, and full dependency freeze.
- `launch-<id>.log`: preparation command/output/status. `model-session.log` is a
  snapshot of the loaded worker log, including model settings, source, loading
  time, run arguments, output, and exit status. It can include earlier requests
  from the same session; episode traces/results in this folder identify this attempt.
- `<episode-id>/events.jsonl` and `result.json`: exact model inputs/outputs,
  observations, costs, outcome, token usage, generation time, model-loading time,
  and episode runtime. Gameplay losses remain distinct from infrastructure errors.
  `components.model.load_seconds` describes the original shared session load:
  count it once for the session, not once per reused episode. Episode runtime
  excludes this loading cost, just as in the earlier cold-launch path.
- `checkpoint-report.json`: independent log/accounting checks and behavioral metrics.

The final ZIP contains these files, not cached model weights. Old pilots stay in
their original folders. The Java/Py4J cgroup-warning fix is in the shared Python
launcher; no installed package or verification setting is patched.

## Completed local development MVP

The real-Qwen 5070 Ti pilot passed the environment and trace-integrity gate:
legal repeated inspections execute, charge budget, and remain in the raw trace.
All eight prose/JSON × prices 2/5 × seeds 0/1 episodes ran with fixed model and
actor settings, and all independent audits passed. Every run exhausted the
budget without completing the meal. See [mvp-results.md](mvp-results.md) for
the table and two trace annotations. Gameplay success was an outcome to measure,
not a condition for running the comparison.

Hybrid, the 120-episode study, dashboards, general scheduling/resume, and performance
optimization are deferred unless an issue specifically blocks this MVP.
Existing work is retained for later; it is not part of this notebook's run path.
