# V31-preserving minimal core

The active program runs CookingWorld with `full_history`, model-written `prose`,
or model-written `structured` JSON memory. New real inference requires separate
execution authorization. This cleanup runs only software checks. Linux/A10 is the
current known execution target; the CLI contains no cloud-service integration.

## Data flow and budgets

`run_episode` prepares an immutable manifest with `prepare_pilot`, loads a real
model once per invocation, and creates fresh environment and memory state for each
seed. The environment supplies an `AgentView`: current observation, goal, ordered
allowed actions, remaining action budget, and recipe-reread cost. Reset includes
one free public recipe reading. The v31 actor sees only that view and the literal
rendered memory, in a fresh request each turn. It normalizes optional articles,
validates legality, and can request a preparation review and one repair. Python
does not choose a better action or correct remembered cooking facts.

The environment executes the chosen action and owns costs and termination. An
ordinary action costs one budget unit; a legal cookbook read/examination costs
`recheck_cost`. Invalid attempts are charged under the existing environment rules.
After each nonterminal action, a writer sees only prior rendered memory, selected
action, latest public observation, and public task context. Terminal actions skip
the memory update. No hidden inventory, engine history, scores, diagnostics, or
scripted solution is supplied to actor or writer.

Memory is supplied text, not an update to model weights. Prose preserves literal
text and whitespace. Structured memory uses a model-chosen JSON object with syntax
validation and compact, sorted, Unicode-preserving rendering. Both writers retain
p1-memory-v17 instructions, one repair, and exact previous-valid-state fallback.
Empty output is legal. No predefined recipe schema or semantic correction exists.
Generated prose versus generated JSON compares both writing and later use; it
does not isolate reading equivalent facts.

The stored-memory allowance counts the whole actor-visible rendering, including
JSON keys/punctuation or stored plans. It excludes the current view, system
instructions, labels, and chat template. `full_history` instead preserves all
actual initial and nonterminal public action/observation records, invokes no
writer, and is exempt from that allowance. Every mode remains subject to the
complete model context limit: overflow is an infrastructure error, without
truncation. `action_max_new_tokens` and `memory_max_new_tokens` cap generated
outputs separately from stored memory and game-budget units.

## One gameplay command and read-only reporting

Canonical gameplay: `.venv/bin/python -m game_memory.run_episode ...`.
Append `--prepare-only` to validate and preserve the manifest without loading
weights or playing. Preparation checks the runtime for real backends; it is not a
capability test. Every invocation uses manifest guards: changing settings/source,
reusing a completed seed, or encountering partial/missing traces requires a fresh
directory. No automatic retries or general resume workflow exists. Ordinary
losses continue to later declared seeds; infrastructure errors stop the loop.
`--seed` and `--seeds` are mutually exclusive and duplicates are rejected.

Real execution requires explicit `--output-dir` and nonempty `--protocol-id`.
The caller must capture startup stdout, stderr, and the original process exit
status, including failures before an episode exists. For example, after separate
authorization, redirect the exact command into fresh startup files and preserve
`status=$?` immediately; do not pipe through a command that masks its exit status.
Per-episode traces already log requests before inference, raw responses, failures,
writer acceptance/repair/fallback, token usage by purpose, generation time and
end-to-end episode time. Unique episode directories preserve partial attempts.

Read-only reporting (run independently for each condition directory):

```sh
.venv/bin/python -m game_memory.summarize_diagnostics PATH_TO_CONDITION
```

The JSON report includes turn rows, observations, actions, reviews/repairs,
rereads, writer provenance and recorded sizes, usage and timing. Missing evidence
stays unknown. Recorded token counts are not independent retokenization. A game
loss is an observation, not a logging failure. Fixtures are excluded by default;
`--include-fixtures` checks software wiring only, with synthetic token counters,
and cannot establish Qwen capability. Capture report stdout outside the input
condition; reporting never writes input files.

## Prepared future real commands — NOT authorized or executed

All three commands below are prepared only. Use separate fresh directories and
identical other settings. For preparation, append `--prepare-only` to the exact
chosen command. For authorized execution, capture startup streams and status as
described above. These settings do not change library defaults and do not imply
that 512 tokens creates memory pressure.

**full_history: prepared, not authorized or executed.**

```sh
.venv/bin/python -m game_memory.run_episode \
  --backend transformers --strategy full_history --actor-prompt v31 \
  --output-dir artifacts/qwen-v31-minimal-core-v1/full_history \
  --protocol-id qwen-v31-minimal-core-v1 \
  --model-id Qwen/Qwen3-4B-Instruct-2507 \
  --model-revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --device cuda --dtype float16 --generation-seed 0 --context-limit 8192 \
  --action-max-new-tokens 128 --memory-max-new-tokens 1024 --local-files-only \
  --game-fold train --seed 0 --num-locations 1 --num-ingredients 2 \
  --num-distractor-items 0 --no-include-doors --no-limit-inventory-size \
  --action-budget 80 --recheck-cost 2 --memory-token-limit 512
```

**prose: prepared, not authorized or executed.**

```sh
.venv/bin/python -m game_memory.run_episode \
  --backend transformers --strategy prose --actor-prompt v31 \
  --output-dir artifacts/qwen-v31-minimal-core-v1/prose \
  --protocol-id qwen-v31-minimal-core-v1 \
  --model-id Qwen/Qwen3-4B-Instruct-2507 \
  --model-revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --device cuda --dtype float16 --generation-seed 0 --context-limit 8192 \
  --action-max-new-tokens 128 --memory-max-new-tokens 1024 --local-files-only \
  --game-fold train --seed 0 --num-locations 1 --num-ingredients 2 \
  --num-distractor-items 0 --no-include-doors --no-limit-inventory-size \
  --action-budget 80 --recheck-cost 2 --memory-token-limit 512
```

**structured: prepared, not authorized or executed.**

```sh
.venv/bin/python -m game_memory.run_episode \
  --backend transformers --strategy structured --actor-prompt v31 \
  --output-dir artifacts/qwen-v31-minimal-core-v1/structured \
  --protocol-id qwen-v31-minimal-core-v1 \
  --model-id Qwen/Qwen3-4B-Instruct-2507 \
  --model-revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --device cuda --dtype float16 --generation-seed 0 --context-limit 8192 \
  --action-max-new-tokens 128 --memory-max-new-tokens 1024 --local-files-only \
  --game-fold train --seed 0 --num-locations 1 --num-ingredients 2 \
  --num-distractor-items 0 --no-include-doors --no-limit-inventory-size \
  --action-budget 80 --recheck-cost 2 --memory-token-limit 512
```

## Configuration and interpretation

The pinned model and tokenizer share revision
`cdbee75f17c01a7cc42f958dc650907174af0554` of
`Qwen/Qwen3-4B-Instruct-2507`. The unchanged backend uses greedy decoding,
`do_sample=False`, `num_beams=1`, and `use_model_defaults=False`, with the configured
generation seed. Dependencies remain pinned in `requirements-model.txt`.
Repeatability is distinct from correct action selection. This cleanup makes no
claim of bitwise reproducibility across hardware/software. Deterministic-kernel
changes are outside scope and require verification in the intended runtime.

First establish useful baseline/memory behavior under fixed roomy settings and
inspect complete gameplay. Then vary the stored-memory allowance while keeping
other settings fixed. Investigate reread cost later. Keep development seeds
separate from future held-out seeds. Preserve gameplay losses as observations.
The old failed four-seed history-window gate remains exactly as recorded; do not
reinterpret it or execute its Phase B. This cleanup declares no replacement
scientific readiness threshold and establishes no memory effect or accuracy gain.

## Historical workflows and restoration

Older guides and notebooks are historical, unchanged, and require their archived
source rather than compatibility shims. The dirty starting implementation,
including retired launchers, diagnostic probes, hybrid/window policies, and
fixed-grid evaluators, is preserved in
`artifacts/minimal-core-cleanup-v1/attempt-20261116-232112/source-before.zip`.
SHA-256: `e7bb7b42ad4b29a41e446ef29403cc16070cbe78639641112cd151a5e9d03d93`.
The adjacent per-file inventory and verification record support restoration.
Existing research evidence remains in place. The historical
[history-window checkpoint](history-window-checkpoint.md) is not the active guide.
The separate pilot/inspection CLIs, cloud/local launchers, retired policies and
strategies are intentionally unsupported. `--pilot` is removed: protection is
mandatory. Startup log capture now belongs to the caller.

## Experimental action interface

[Legal-choice-v1](legal-choice-v1.md) is an opt-in, full-history-only untrained
label-scoring interface with one forward pass and no reviews/repairs. V31 remains
the default. Offline software verification does not authorize real execution or
establish cooking capability.
