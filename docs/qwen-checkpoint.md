# Friday MVP: the next checkpoint

Use one entry point: [qwen_colab.ipynb](../notebooks/qwen_colab.ipynb).
It runs **one full-history diagnostic on development seed 1**, then stops.
Do not start the memory pilot from an older notebook copy.

## What is actually verified

| Area | Evidence | Still unverified |
| --- | --- | --- |
| Simulator and runner | Automated real-Java tests; fixed replay/accounting checks. | Nothing here establishes model capability. |
| Qwen inference | Two supplied T4/FP16 seed-0 traces, with clean source/model revisions and complete accounting. | Useful completion across development games. Both supplied runs lose by budget exhaustion. |
| Actor v2 | Fewer unavailable requests and rereads, and higher score on seed 0. | It still discards ingredients and loops on a shelf. See [the trace comparison](actor-policy.md). |
| Memory | Existing prose/JSON writers have repair, fallback, rendering-limit, and isolation tests, including tiny local model integration. | Production Qwen/tokenizer integration and real bounded-memory episodes. |
| Execution | Shared manifest guards, Java handling, durable launch logs; recorded v1/v2 prompts replay identically. | The refactored notebook still requires a Colab run. |

Local tests use scripted inference or tiny random weights where indicated.
They do not evaluate the actual 4B checkpoint. This workspace has no GPU.
The uploaded traces are evidence of runs performed in Colab, not runs performed here.

## Exact next action in Colab

1. Open the current notebook as a fresh copy, rather than only changing a code SHA
   in an older copy. Use the supplied ready-to-run copy, or set `REPO_REF` to the
   implementation commit provided with this milestone.
2. Select a **T4 GPU**. Keep the `SETTINGS` dictionary unchanged: Qwen revision
   `cdbee75f17c01a7cc42f958dc650907174af0554`, FP16, actor v2, budget 80,
   reread price 2, greedy decoding, context limit 8,192, and generation seed 0.
   `FIRST_SEED = 1` selects another development instance; seed 0 is already audited.
3. Run sections 1–3. The checkout is preserved, Drive is mounted, dependencies are
   installed in the isolated environment, and CPU/Java/adapter tests run before weights load.
4. Run section 4. It checks GPU support and records the manifest without loading
   Qwen weights. Repeating identical preparation is safe. Changed settings or
   older manifest formats require a new pilot directory; existing files are not overwritten.
5. Run section 5 **once**. This is the only model episode in the notebook.
6. Run the audit and download cells. Return the checkpoint ZIP for analysis.
   Stop here; no additional episodes run automatically. Disconnect the GPU when finished.

The earlier v2 run used about **203 seconds of episode time plus 101 seconds of
model loading**. Setup, downloading, and idle allocation add to billed GPU time;
seed 1 may differ. This is a reference from one run, not a cost guarantee. The
reason for one further run is to check whether the seed-0 planning failure repeats
without starting an open-ended prompt search.

## Saved evidence

Each new `PILOT_DIR` in Drive contains:

- `pilot-manifest.json`: code revision, actor settings, game settings, model
  revision, precision, and runtime/package identity. It is immutable.
- `checks-<id>/`: dependency check, Java version, pytest output, and full dependency freeze.
- `launch-<id>.log`: exact command, stdout/stderr, and exit status, including
  failures before an episode exists. Every attempt gets a new log.
- `<episode-id>/events.jsonl` and `result.json`: exact model inputs/outputs,
  observations, costs, outcome, token usage, generation time, model-loading time,
  and episode runtime. Gameplay losses remain distinct from infrastructure errors.
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
