# Copy this prompt into the laptop Codex session

Continue the Memory/CookingWorld research project from this laptop checkout.
The prior agent ran through SSH on a Windows/WSL PC. This session runs locally
on my laptop; use Modal for remote GPU execution. Resolve paths from this
checkout, not the old `/home/seb/64610-Memory` paths appearing in historical logs.
Do not assume access to the previous chat or PC. Read the transferred files.

Your task is to implement the smallest useful Modal launcher, validate it, run
one unchanged-policy JSON seed-1 cloud pilot, retrieve its evidence, and explain
the outcome and justified next changes. This prompt, when I submit it, authorizes
uploading the necessary project source to my Modal workspace, CPU preflight,
and that single paid GPU episode. Use one A10 GPU, 32 GiB host RAM, four CPU
cores, an explicit 60-minute execution timeout and a finite startup timeout.
Do not substitute an expensive GPU or submit extra GPU episodes without a new
instruction. If authentication or billing is missing, complete implementation
and checks that are possible, then identify that concrete missing setup.

Read first:

- `AGENTS.md` and `docs/modal-laptop-setup.md`.
- `handoff/README.md`. Verify the committed ZIP/checksum and its internal
  `handoff/transfer-manifest.json` before editing. Restore only its `artifacts/`
  entries into this checkout, preserving existing files and stopping on any
  conflicting content. Do not overlay archived source/docs onto this branch.
- `docs/memory-calibration-results-2026-11-16.md`.
- `docs/memory-calibration-retry-2026-11-16.md`.
- `docs/memory-calibration-host-diagnosis-2026-11-16.md`.
- `docs/codex-qwen-calibration-prompt.md` for the frozen experimental settings.
- `docs/memory-calibration-verification-2026-11-16.md`,
  `docs/memory-calibration-integration.md`, and
  `docs/memory-annotation-guide.md`.
- Actual callers and tests for `game_memory.pilot`, `run_episode`, `runner`,
  `transformers_model`, `colab_session`, and `summarize_diagnostics`.

## Existing state and provenance

The origin is `https://github.com/sebace05/64610-Memory.git`; the handoff branch
is `codex/modal-calibration-handoff`. Its committed source contains the v17/v30
implementation, tests and reports. Before this handoff was committed, original
Git HEAD was `739e72def5ef65d8e0a8fd24d879cdc401de2066` and these changes were
uncommitted. A checkout of that old commit alone is insufficient. Do not reset
to it. The committed ZIP preserves that earlier snapshot and Git-ignored
evidence; branch source/docs are authoritative for current setup instructions.

The frozen executable-source digest on Linux is
`f4c9b85a1594d02e3b2ac6ae225a4e82b9b0566ab6b545cc93d055d5cd860afb`.
It fingerprints `game_memory/*.py`, dependency files, AGENTS.md and the existing
protocol document. Check it inside the remote Linux image before inference.
Do not fabricate old Git metadata if `.git` is not present remotely; record
the original provenance alongside the actual remote metadata and digest.
The commit SHA/dirty flag will naturally differ after committing this branch;
compare the frozen executable digest, not the entire old source metadata dict.
Windows-local path separator differences can affect this digest implementation;
the transferred per-file hashes are platform-independent.

The integrated implementation previously passed **380 tests**, with no skips.
This is engineering evidence, not proof of research-model correctness. The
archive includes the historical reproduction fixtures referenced by tests;
restore its `artifacts/` payload before running those checks.

Primary local evidence root:
`artifacts/qwen-calibration-v17-v30-20261116T154805Z/`.
Latest existing baseline summary:
`calibration-summary-after-retry-2.json` within that root. Also inspect
`host-resource-diagnosis.json`. Existing ZIPs/checksums preserve earlier states.
Never aggregate all `artifacts/` recursively as one experiment; that tree also
contains historical policies and scripted fixtures.

The six planned local episodes currently have these outcomes:

| Strategy | Seed 0 | Seed 1 |
| --- | --- | --- |
| Full history | Success, 10 actions | Budget exhaustion after meal creation |
| Prose, 512 tokens | Success, 79 actions after a long inspection loop | Budget exhaustion after meal creation |
| JSON, 512 tokens | Budget exhaustion, knife take/put/inspection loop | No gameplay: two model-loading OOM kills |

An earlier interrupted prose seed-0 attempt is also retained separately. Across
the three completed bounded episodes, all 238 writes were nonempty and primary
accepted, with no syntax/size repairs, fallbacks, or generation-limit hits.
Largest stored memory was 203 of 512 tokens. Retokenization matched every saved
bounded rendering, including the interrupted attempt. Capacity was not an
observed binding constraint; recipe retention alone did not ensure useful state.

Confirmed local infrastructure problems: WSL configured for 12 GB RAM/8 GB swap;
both startup failures have kernel OOM and swap write errors. Windows C: was
100% full with about 15 MB free, and swap VHD files were found on C:. Another
model server also occupied RAM/swap. The full backing drive strongly explains
unreliable swap, but no successful-load resource history establishes the exact
transition from successful to failed launches. This is not a seed-specific
increase in Qwen's model requirements. Do not run cleanup or WSL commands on
this laptop based on those old PC diagnostics.

## Preserve the frozen policy during migration

- Model `Qwen/Qwen3-4B-Instruct-2507`; model/tokenizer revision
  `cdbee75f17c01a7cc42f958dc650907174af0554`.
- CUDA FP16, no quantization, greedy decoding, generation seed 0, context 8192.
- Actor **explicitly v30**; writer `p1-memory-v17`; render `p1-render-v2`.
- Actor cap 128; writer generation cap 1024; bounded stored memory 512 tokens.
- Train fold, one room, two ingredients, zero distractors, no doors, unlimited
  inventory, one free initial recipe. Action budget 80; reread price 2.
- First authorized cloud game: `structured`, game seed 1. Preserve all other
  experimental settings. Game seed and model generation seed are different.
- Pin the existing Python dependencies and Java 17. Record the exact Python,
  CUDA, driver, GPU and Modal SDK/container identities and loading/run timings.
- Use JVM settings
  `-XX:-UsePerfData -Xlog:os+container=off:stdout -Xlog:os+container=warning:stderr`
  and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.

Cloud A10 hardware differs from the original RTX 5070 Ti. Use a **new cloud run
root** and protocol `qwen-calibration-v17-v30-modal-a10-pilot-v1` for this policy.
Do not append cloud outputs to local manifests or mark the hardware-pinned
local six-cell checkpoint complete. The one cloud episode is migration evidence;
a complete cloud baseline would be a separately declared plan on one runtime.

`scripts/run_local_qwen.sh`, the older Colab notebook and parts of
`docs/qwen-checkpoint.md` retain historical defaults. Do not accidentally use
v1/v3, BF16, one ingredient, or the old 512-token writer generation cap.

## Implement only the migration this checkpoint needs

Put a thin launcher outside `game_memory/`, preferably
`scripts/modal_calibration.py`, so migration scaffolding does not silently change
the frozen executable-source digest. Reuse the existing CLI/runner/audits.
There is no Modal launcher in the transferred tree yet; implement and validate
it instead of assuming an example command already works.

1. Build a remote Linux image with Python 3.12, Java 17 and the pinned project
   dependencies. The laptop needs only the Modal client; install no local GPU
   stack or model weights. Honor project `.venv/bin/python` conventions remotely.
2. Upload an explicit source allowlist, not the whole checkout. Exclude local
   `.venv`, `.git`, credentials, Modal tokens, home dotfiles and generated result
   trees. Include the small historical fixtures if needed by CPU tests. Never
   inject offline annotations or diagnostic state into live model requests.
3. Run CPU/simulator tests in the remote image. Run the relevant meaningful
   launcher failure checks and the project suite; report skipped/unavailable
   checks honestly. Avoid tests that just match prompt/source strings.
4. Keep model cache and results in named persistent Modal volumes. Candidate
   names: `memory-research-cache` and `memory-research-results`. Use a fresh run
   ID and attempt directory. Persist the submitted plan and initial attempt
   marker **before** loading weights, and commit traces/statuses during execution
   and at completion/failure. Record actual subprocess exits, not inferred ones.
5. Set explicit startup/execution limits, one GPU container and one invocation
   at a time. No blind retries of OOMs, gameplay losses or partial attempts.
   Modal GPU preemption can replay an input: check the durable attempt marker
   before model loading so replay cannot silently overwrite or duplicate a run.
   Preserve interrupted attempts and stop visibly for review. No general
   batch/resume framework, parallel GPU sweep or persistent idle GPU server.
6. Put the episode execution and audit **inside the remote entrypoint**. Submit
   it detached, save the app/function IDs and run/volume paths locally before
   returning control, and support status/log/result retrieval after reconnecting.
   A laptop-side loop that submits one episode at a time is not unattended cloud
   execution if the laptop disappears halfway through.
7. Run one JSON seed-1 episode with the policy above. Let valid gameplay loops
   finish by normal game/action-budget termination. Stop on infrastructure
   errors. Save raw traces, results/error records, actual exit status, all
   actor/writer/review/repair usage, model-load/generation/episode/outer time,
   and host peak memory if the existing OS tools can measure it without changing
   model behavior.
8. Retrieve results to a fresh local artifact directory. Run condition audits,
   inspect real gameplay and Qwen memory, independently recount stored tokens,
   then write a concise evidence-backed report and ZIP/checksum. Explain
   whether the outcome is gameplay success/loss or infrastructure failure.

## Agent reporting and future policy work

Provide exact tested commands to submit, check status, fetch logs and download
results. Save a small local run-reference file containing those IDs/paths. A
future Codex session should be able to read it and review results without manual
log pasting. Running GPU work remotely does not itself trigger a new Codex turn;
do not promise an automatic message in this chat. Completion-triggered agent
analysis/notifications are a separate optional integration, not required now.

Existing candidate fixes remain **unimplemented hypotheses**: align actor,
review and repair priorities around eating a prepared meal before regathering
ingredients; preserve confirmed possession/completed progress across unrelated
writer observations; distinguish located/carried/prepared facts equally in prose
and JSON. The actor already contains an eat-meal instruction, so merely adding
another copy is not a demonstrated fix. Qwen must write the facts; do not restore
Python factual correction, semantic rejection, forced useful actions or hidden
history. Any later policy changes need new prompt versions, focused real-Qwen
checks and a fresh declared calibration, with controls inspected first.

Stop after the single migration episode and report. No hybrid, tighter-memory
sweep, held-out/120-game study, dashboards, extra GPU providers, automatic prompt
tuning or eight-game comparison in this assignment. Current AGENTS.md specifies
the eventual MVP as prose/JSON × two reread prices × two development seeds,
eight episodes; the older design document's allowance-axis proposal is not an
authorization to silently change that grid. Do not spawn subagents.
