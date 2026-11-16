# New-session prompt: begin T7 Qwen calibration

You are working in `/home/seb/64610-Memory`. Start and complete the **initial T7
calibration checkpoint** using the implemented v17 memory writers and v30 actor.
Perform the runs and inspect the evidence; do not stop at a plan or commands for
the user to execute.

This prompt authorizes real-Qwen GPU inference for the checkpoint below, the
needed preflight checks, and downloading the exact pinned checkpoint only if it
is not already cached. It supersedes the earlier development prompt's prohibition
on GPU runs for this assigned calibration work. It does not authorize a memory-
pressure sweep, the development comparison, held-out evaluation, hybrid runs,
training, or live prompt/code tuning.

**Read first**

- `AGENTS.md`.
- `docs/memory-calibration-verification-2026-11-16.md`.
- `docs/memory-calibration-integration.md`.
- `docs/memory-constraints-design-and-task-plan.md`, especially calibration and
  evidence requirements.
- `docs/memory-annotation-guide.md`.
- All four `docs/dev-handoffs/memory-calibration/{A,B,C,D}.md` notes.
- The actual CLI, memory, actor, runner, and audit code before launching.

T1–T6 are complete; all four roles handed off READY. Independent checks passed
380 tests and two additional v17/v30 real-simulator/scripted-inference checks.
That is engineering evidence, not proof that the production Qwen writers work.

**Objective and scope**

First establish whether the new actor can solve the current task with full
public history. Then determine whether prose and JSON can support successful
gameplay using Qwen-written memory with ample space, without Python filling in
recipe, inventory, or progress facts.

Plan **two full-history controls, followed by four bounded-memory episodes**:

| Phase | Strategy | Seeds | Stored-memory allowance |
| --- | --- | --- | --- |
| A: capability | `full_history` | 0, 1 | Exempt from the bound; diagnostic only |
| B: generous-memory behavior | `prose` | 0, 1 | 512 Qwen tokens |
| B: generous-memory behavior | `structured` | 0, 1 | 512 Qwen tokens |

512 is a deliberately generous **calibration setting**, not a frozen high-budget
treatment for the future study. The writer generation cap is 1024 tokens so that
the older 512-token output cap is less likely to truncate a replacement near the
stored-memory allowance. Both limits must be recorded and held fixed throughout
this checkpoint. Check for actual output-limit hits and size rejections before
calling the allowance nonbinding. Do not describe any finite limit as unlimited.

Full-history controls do not invoke a memory writer and may exceed 512 stored
tokens. Record that exemption and keep them separate from bounded-memory results.

**Fixed settings**

- Model: `Qwen/Qwen3-4B-Instruct-2507`.
- Immutable model/tokenizer revision:
  `cdbee75f17c01a7cc42f958dc650907174af0554`.
- Device: RTX 5070 Ti, CUDA, `float16`; no quantization or alternative model.
- Greedy decoding, generation seed 0, context limit 8192.
- Actor explicitly selected with `--actor-prompt v30`. The global default is
  still v1, so relying on defaults would test the wrong policy.
- Bounded writer: `p1-memory-v17`; rendering `p1-render-v2`; syntax/size-only
  validation, one repair, exact previous-state fallback, no factual assistance.
- Game: `train` fold, one room, two ingredients, zero distractors, no doors,
  unlimited inventory, one free initial recipe.
- Game action budget: 80; recipe reread price: 2.
- Actor output cap: 128; memory output cap: 1024.
- Bounded stored memory: 512 tokens. No tighter allowances in this checkpoint.
- Protocol ID: `qwen-calibration-v17-v30-capability-roomy-v1`.

Record all defaults explicitly in the calibration plan and actual manifests.
Do not change settings between strategies or seeds to obtain success.

**1. Check and preserve the actual tested implementation**

The implementation is currently uncommitted. Git HEAD is
`739e72def5ef65d8e0a8fd24d879cdc401de2066`, but that old commit alone does not
contain the new behavior. Do not reset, pull, stash, or check out HEAD to obtain
a supposedly clean experiment.

The independently tested executable digest is:

```text
f4c9b85a1594d02e3b2ac6ae225a4e82b9b0566ab6b545cc93d055d5cd860afb
```

Read `source_metadata()` and both memory metadata dictionaries; verify v17/v30
and that digest. If source differs, identify the changes before proceeding.
For changes that retain the agreed behavior, recheck the integrated source and
rerun relevant/full checks, then record the new digest and why it differs. If
unreviewed model-facing behavior or version identities have changed, stop with
the concrete mismatch instead of silently calibrating another policy.

Create one fresh timestamped root such as
`artifacts/qwen-calibration-v17-v30-<UTC timestamp>/`. Save:

- An immutable `calibration-plan.json` containing scope, settings, phase gates,
  source identity, expected seeds, and runtime/package identity.
- A snapshot of the **actual working-tree source**, including changed tracked
  files and untracked executable modules such as `analyze_memory_budget.py`.
  Include dependency files and the applicable policy/protocol documentation.
  Do not use only `git archive HEAD`: it would preserve the old implementation.
- Snapshot/file checksums and a dependency freeze. Do not package environments,
  model weights, home-directory dotfiles, or credentials.

Do not modify source while this checkpoint runs. Verify its digest before each
launch. Use the existing isolated checkout; do not create a worktree or commit
another session's work. Treat historical artifacts and role handoffs as read-only.

**2. Verify the runtime and GPU availability**

Use `.venv/bin/python`. Java 17 and the project dependencies are installed.
On this WSL2 machine, GPU status is available at:

```sh
/usr/lib/wsl/lib/nvidia-smi
```

Inspect active GPU jobs before loading another model. Do not kill another user's
process or assume an unavailable bare `nvidia-smi` command means CUDA is missing.
The agent sandbox may hide `/dev/dxg` or block Java/local sockets: use the tool's
normal escalation mechanism when necessary before declaring a host problem.
Do not install Linux NVIDIA drivers inside WSL or change the working dependencies.

Use the documented Java environment for checks/launches:

```sh
export JAVA_TOOL_OPTIONS='-XX:-UsePerfData -Xlog:os+container=off:stdout -Xlog:os+container=warning:stderr'
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
```

If source/dependencies match the verified state, do not repeat the full suite
merely to spend time. If a rerun is justified by changes or a real concern, use:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

Record checks and any sandbox failures honestly. Do not weaken tests or suppress
real errors. Run GPU episodes sequentially. Existing supported weight reuse is
allowed only with fresh episode state; do not build an optimization or batch
framework for six runs.

**3. Run capability controls first**

Run full-history seed 0, inspect its completed trace and audit, then run seed 1
under identical settings. Use the explicit v30 actor. Save both outcomes,
including losses; no replacement seeds or discarded attempts.

Check the actual chosen actions, public recipe, observations, meal preparation,
termination, context/output-limit errors, and inference accounting. Full-history
is a practical capability reference, not a guaranteed mathematical upper bound.

Before Phase B, determine whether these controls establish useful task capability.
If neither succeeds, stop after preserving/analyzing both controls and report the
capability failure; do not automatically reduce difficulty or tune prompts. If
one succeeds and the other loses, Phase B may still complete as descriptive
calibration, but explicitly carry that capability limitation into the verdict.
An infrastructure failure or broken audit stops subsequent launches pending
diagnosis; it is not a gameplay loss.

**4. Run the four generous-memory episodes without tuning**

Run prose seed 0 first and inspect/audit it before continuing. Then complete the
other predeclared bounded cells, inspecting the first JSON episode before its
second seed. All games use the same settings above. A valid gameplay loss or
loop must be preserved and allowed to end through normal game/action-budget
termination; do not interrupt it just because it looks unsuccessful.

Use separate condition directories for full history, prose-512, and
structured-512. Use single-seed invocations when inspection is required between
episodes. The existing pilot supports adding a different seed with identical
settings, and rejects duplicate or partial attempts.

Use the existing `game_memory.pilot` CLI so actual subprocess status and both
output streams are saved. A first-control launch has this shape; replace the
output path with the fresh root you created:

```sh
.venv/bin/python -m game_memory.pilot \
  --output-dir artifacts/YOUR_FRESH_CALIBRATION_ROOT/full-history \
  --protocol-id qwen-calibration-v17-v30-capability-roomy-v1 \
  --backend transformers --strategy full_history --actor-prompt v30 \
  --model-id Qwen/Qwen3-4B-Instruct-2507 \
  --model-revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --device cuda --dtype float16 --context-limit 8192 \
  --generation-seed 0 --action-max-new-tokens 128 \
  --memory-max-new-tokens 1024 --memory-token-limit 512 \
  --recheck-cost 2 --action-budget 80 \
  --num-locations 1 --num-ingredients 2 --game-fold train --seed 0
```

For bounded episodes, change only strategy, corresponding condition directory,
and the planned seed. Explicitly use `prose` or `structured`. Before loading
weights, use the CLI's `--prepare-only` preflight if useful and inspect its
schema-2 manifest. Keep the outer tool process alive until the launcher finishes
so its exit status is captured; do not infer exit zero from `result.json` alone.

If an episode crashes or is interrupted, preserve its partial trace and logs.
Do not reuse its directory or silently replace it with a successful attempt.
Any technically justified retry gets a new labeled attempt directory.

**5. Verify real Qwen behavior from raw evidence**

Use `game_memory.summarize_diagnostics` separately for each condition. Save audit
reports without overwriting earlier evidence. Do not create a pretend two-budget
comparison manifest or call the factorial analyzer to claim an allowance effect:
only one bounded allowance is being tested here.

For every bounded game, inspect model responses and memory updates, especially
initialization, taking an ingredient, cooking/preparation, and the decision before
meal preparation or a terminal mistake. Report:

- Did Qwen write prose / valid JSON as instructed? Was the accepted memory useful
  and nonempty, rather than only technically accepted?
- Primary accepted writes, repaired writes, previous-state fallbacks, accepted
  empty writes, and total updates. Do the counts reconcile?
- Are required recipe facts, confirmed inventory, and progress preserved? Which
  facts are omitted, stale, contradicted, or invented? Cite event sequence IDs.
- When needed information is missing, does the actor recover it or guess? Does
  it reread despite correct information already being available?
- Did the actor ignore correct stored facts? Was the relevant fact instead
  present in the current observation, making that turn uninformative about memory?
- Actual stored/candidate sizes, over-budget rejections, and output-limit hits.
  Independently recount bounded stored memories with the pinned tokenizer when
  possible. Use its cached local snapshot path to avoid unnecessary Hub metadata
  requests; distinguish recorded counts from independently checked counts.
- Success, terminal failure, budget exhaustion, score, actions, rereads, and
  budget spent. A loss remains measured data.
- All actor/writer/review/repair calls and tokens, generation time, episode time,
  and model-loading time separately. Include rejected writer generations.

Apply public-evidence annotations offline. Never feed a checklist, full trace,
gold solution, or corrected facts into a bounded episode. Do not restore Python
fact helpers or introduce automatic useful actions to achieve successful runs.

**6. End with an evidence-backed checkpoint verdict**

Complete the six planned episodes when phase gates permit; do not ask permission
again for each routine authorized launch. If a gate blocks progress, preserve the
attempts and explain the specific evidence. Do not leave jobs running without
reporting them or silently schedule follow-up runs.

Write a calibration report under `docs/` and machine-readable summary under the
fresh artifact root. Include:

1. Source/protocol/runtime identities, the six planned cells, actual completion,
   and any missing/error/retry cases.
2. One table with outcomes, game metrics, memory provenance/content quality,
   measured tokens, generation time, and episode time.
3. At least one annotated prose trace and one JSON trace, including failures.
4. Separate verdicts on actor capability, useful model-written memory, gameplay
   success for each format, and whether 512 was actually generous.
5. A recommendation for the next T7 step: diagnose writer/reader behavior,
   expand a demonstrated binding limit in a new checkpoint, or begin a later
   pressure-calibration phase. Candidate tight limits are recommendations only.

Successful generous-memory behavior must involve genuinely model-written useful
memory and successful gameplay in both formats. Accepted empty memory or a high
acceptance percentage alone is not sufficient. Report every seed's result; do
not require equal success rates or hide failures to present parity. If one format
still fails with ample space, distinguish that writer/reader problem from a
demonstrated capacity problem. Useful outcomes include a clearly diagnosed failed
checkpoint; do not promise a success by changing the policy mid-run.

Preserve manifests, raw traces/results, audits, annotations, launch logs and exit
statuses, actual source snapshot, dependency freeze, summary and report in a ZIP
with a SHA-256 checksum. Exclude weights and environments. Verify ZIP integrity.
Artifacts are ignored by Git: clearly state the local package path and that it
needs durable shared storage. Do not upload or send it to an external service
without user instruction.

Stop after this capability/generous-memory report. Do not start the low-budget
sweep, pick final comparison allowances, edit prompts, or launch the 8/16-game
comparison under this assignment. Do not spawn subagents; this is one GPU owner
performing a sequential calibration checkpoint.
