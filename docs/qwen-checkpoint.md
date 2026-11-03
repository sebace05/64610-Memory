# Friday MVP: the next checkpoint

Use one entry point: [qwen_colab.ipynb](../notebooks/qwen_colab.ipynb).
It runs **one separately labeled one-room/one-ingredient full-history test on seed 0**.
Qwen stays loaded for explicitly chosen follow-up runs in the same live runtime.
Do not start the memory pilot from an older notebook copy.

## What is actually verified

| Area | Evidence | Still unverified |
| --- | --- | --- |
| Simulator and runner | Automated real-Java tests; fixed replay/accounting checks. | Nothing here establishes model capability. |
| Qwen inference | Two larger-game T4/FP16 traces plus one audited small-game trace with complete accounting. | Useful completion across development games; all three audited runs lose. |
| Actor | Small-game v2-mechanics rereads, opens fridge, takes ingredient, then incorrectly roasts instead of grilling. The recipe remained in its input. | V3 adds only appliance semantics; actual Qwen improvement is unverified. |
| Memory | Existing prose/JSON writers have repair, fallback, rendering-limit, and isolation tests, including tiny local model integration. | Production Qwen/tokenizer integration and real bounded-memory episodes. |
| Execution | Shared manifest guards, Java handling, durable logs; a tiny local model runs two fresh games in the same loaded process. | Production-Qwen session reuse and the current notebook still require a Colab run. |

Local tests use scripted inference or tiny random weights where indicated.
They do not evaluate the actual 4B checkpoint. This workspace has no GPU.
The uploaded traces are evidence of runs performed in Colab, not runs performed here.

## Exact next action in Colab

1. Open [the current notebook in Colab](https://colab.research.google.com/github/sebace05/64610-Memory/blob/main/notebooks/qwen_colab.ipynb).
   `REPO_REF=None` resolves main once, checks out that immutable commit, and records
   it. Set a full SHA for a frozen protocol or exact replay. Reopen this link for
   code/configuration updates; a saved Colab copy retains its own configuration.
2. Select a **T4 GPU**. Keep Qwen revision
   `cdbee75f17c01a7cc42f958dc650907174af0554`, FP16, actor `v3`, budget 80,
   reread price 2, greedy decoding, context limit 8,192, and generation seed 0.
   The new condition sets `num_locations=1`, `num_ingredients=1`, and `FIRST_SEED=0`.
   The engine still generates the recipe; no scripted solution reaches the model.
   V3 only adds stove=fry, oven=roast, toaster=grill and the warning that legal
   cooking actions may ruin an ingredient. All other settings match the audited
   small-game failure. Choose **Runtime → Run all** and authorize Drive if prompted.
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

The earlier v2 run used about **203 seconds playing plus 101 seconds loading**.
Reuse targets that loading cost, not inference time; setup/download/idle time is
additional. Production-Qwen timings for the session path remain unmeasured.
The audited small-game run instead took 7.08 seconds playing and 101.72 seconds
loading, ending in terminal failure after 4 actions. One matched run is justified
to test the confirmed missing appliance instructions. No further jobs are scheduled automatically.

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

## The remaining MVP, behind the checkpoint

1. **Inspect gameplay.** A valid ending is not a useful-gameplay pass. Check
   exploration, carried ingredients, progress toward preparing/eating, and loops.
   If planning remains blocked, retain a reproducible diagnostic and choose the
   smallest evidence-backed next step. Do not fill a memory-results table with fixtures.
2. **Integrate two memories.** Connect existing `ProseMemory` and
   `StructuredMemory` to real inference. Verify the same 256-token rendered-memory
   limit, one repair/previous-valid-state fallback, writer/actor usage accounting,
   and isolation. No raw history, scores, scripted paths, or hidden simulator state
   belongs in bounded-agent inputs.
3. **Measure one bounded episode.** Its writer calls add cost; the full-history
   run cannot forecast that cost alone. Review its measured runtime and usage
   before launching the other seven episodes.
4. **Eight episodes only.** Two strategies × prices 2/5 × development seeds 0/1.
   Hold other settings fixed. Preserve every attempt in separate condition folders;
   keep infrastructure errors, incomplete attempts, and gameplay losses distinct.
5. **Evidence.** One compact table of completion, rereads, budget, tokens, and
   runtime; two trace windows grounded in visible evidence. Describe the result
   as preliminary. Two instances do not support strong statistical or causal claims.

Hybrid, the 120-episode study, dashboards, general scheduling/resume, and performance
optimization are deferred unless an issue specifically blocks this MVP.
Existing work is retained for later; it is not part of this notebook's run path.
