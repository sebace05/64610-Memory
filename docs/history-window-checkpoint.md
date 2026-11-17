# Full public history versus a retained-history window

Protocol: **qwen-v31-history-window-checkpoint-v1**. This is the current development
checkpoint. Prose/JSON memory writers, the price comparison, v32 prompt probes,
hybrid, the 120-episode evaluator, optimization, dashboards and general batch/resume
are deferred. The historical notebooks, replay harnesses and source snapshots remain
available with their original configurations.

## Research question and controlled intervention

Can the existing pinned Qwen checkpoint complete the small game with v31 and full
public history, and what happens when only retention of those same records is
restricted? Neither condition invokes a memory writer or memory-repair generation.
The intervention is retention of public history, not summarization format, total
prompt size, fine-tuning or a test of general model reliability.

`full_history` is the unchanged `FullHistoryMemory` archive and metadata. It begins
as `[]`, appends `[INITIAL_OBSERVATION]` containing the reset observation and initial
free recipe, then appends the wrapper action and public observation after each
nonterminal action. Terminal actions skip another update. Every record contains
exactly `action` and `observation` strings. Both conditions serialize with
`json.dumps(records, ensure_ascii=False)`, preserving order, field insertion order,
whitespace and literal strings. No reasoning fields, scores, privileged inventory,
legal-action snapshots or reconstructed facts are added.

`history_window` uses `HistoryWindowMemory` version 1, policy
`oldest_complete_record_eviction_v1`. On each update it appends the new public
record, counts the complete serialized candidate with `model.count_tokens()`, and
removes oldest complete records until it fits **inclusively**. This is a contiguous
suffix of the previous retained records plus the new record, not an exact last-K-
token slice. Indivisible records can leave unused capacity. Nothing is pinned:
the initial recipe and initial room record can be lost. An oversized newest record
causes the entire window to become `[]`; an older record that would fit is not
kept instead. If even `[]` does not fit, the component fails visibly. Invalid counts
(including booleans) and tokenizer errors fail visibly. Dropped records are not
cached or resurrected, including when later free space increases.

The allowance includes the array, record braces, keys, action and observation
contents, quotes/escaping, separators and whitespace. The separately supplied
current AgentView (observation, goal, allowed_actions, budget_remaining,
recheck_cost), system instructions, context label and chat-template tokens are
outside it. This is **not a bound on the entire model context**. The current
observation remains duplicated in AgentView and the newest record when it fits.
The first actor turn still receives the complete initial observation through
AgentView even if the window immediately evicts its initial record. Ordinary
inventory/look queries and recipe rereads remain legal at the existing costs.

Both conditions use the **same v31 instructions and history label**:
`Visible interaction history (diagnostic):`. Identical views and retained strings
produce byte-identical primary, preparation-review and repair requests. There is
no prompt hint about truncation, forgotten facts, allowance or eviction. Metadata
truthfully distinguishes `full-history-v31` / `full_history` from
`history-window-v31` / `history_window`. Window mode supports only v31; historical
constructor behavior and the other actor versions remain available.

Logger-only `history_window_evicted_records:N` and
`history_window_retained_records:M` events describe each update and never enter
actor-visible history. Full history remains exempt from stored-memory limits;
both modes remain subject to the existing 8192-token context check. Overflow,
OOM or runtime failure stays an infrastructure error, without silent truncation.

## Existing evidence, not a new capability claim

The saved v31 full-history development games succeeded on seed 0 in 11 actions
and seed 1 in 9. The actual traces were reread and separately reaudited for this
implementation. Seed 0 reread the cookbook and examined the knife, then sliced
and roasted the apple before grilling chicken; this differs from the recipe's
listed global order. Seed 1 reread twice and took an unnecessary knife before
salt and meal preparation. Engine success is still the primary outcome; no new
order metric is imposed on game scoring. Those two wins do not establish the new
four-seed readiness gate or general reliability.

The latest v31/v17 prose/JSON calibration lost all four games while using at most
203 of 512 stored tokens. This does not show that 512 tokens were intrinsically
insufficient. Earlier v16 prose wins also used Python fact validation/fallback
updates removed in v17; they represent a different intervention. The window
checkpoint deliberately avoids that writer confound.

## Fixed finite protocol and canonical commands

Use one unchanged source digest/revision and the same compatible cached inference
environment for both conditions. The existing pilot manifests record episode,
actor, memory, model, protocol and source identity; no new manifest/launcher system
is added. Use the fresh separate condition directories below, never a historical
result directory. Preserve manifests, partial attempts, failures and logs; changing
strategy, allowance or source cannot reuse a manifest.

Both commands fix Qwen/Qwen3-4B-Instruct-2507 revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, CUDA FP16, greedy decoding,
`num_beams=1`, `use_model_defaults=False`, generation seed 0, context 8192, actor
cap 128 and unused memory cap 1024. Game settings: train seeds 0/1/2/3, one
location, two ingredients, zero distractors, no doors, unlimited inventory,
budget 80, reread price 2, one existing initial free recipe observation. Both set
512 as the serialized allowance; full history retains its explicit exemption.
Do not tune this allowance using outcomes.

**Phase A — full-history baseline (prepared command, not executed here):**

```sh
.venv/bin/python -m game_memory.pilot \
  --output-dir artifacts/qwen-v31-history-window-checkpoint-v1/full_history \
  --protocol-id qwen-v31-history-window-checkpoint-v1 \
  --backend transformers --strategy full_history --actor-prompt v31 \
  --model-id Qwen/Qwen3-4B-Instruct-2507 \
  --model-revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --device cuda --dtype float16 --context-limit 8192 \
  --generation-seed 0 --action-max-new-tokens 128 --memory-max-new-tokens 1024 \
  --game-fold train --seeds 0 1 2 3 \
  --num-locations 1 --num-ingredients 2 --num-distractor-items 0 \
  --no-include-doors --no-limit-inventory-size \
  --action-budget 80 --recheck-cost 2 --memory-token-limit 512 \
  --local-files-only
```

Run the four specified seeds once. A gameplay loss is a completed observation:
finish the four-seed baseline unless infrastructure fails. The engineering
readiness gate requires **all four to complete technically, pass their applicable
audit, and successfully prepare and eat the meal**. Inspect all four complete
traces for unnecessary actions, rereads, invalid outputs, reviews/repairs and global
recipe-order deviations. This is a small development gate, not a reliability estimate.

If the gate fails, preserve all results, identify the first material divergence
in each failed game and **stop before Phase B**. Do not replace seeds, reduce
difficulty, increase budget, change prompts or start a tuning loop under this identity.

**Phase B — only after Phase A passes (not authorized or executed here):**

```sh
.venv/bin/python -m game_memory.pilot \
  --output-dir artifacts/qwen-v31-history-window-checkpoint-v1/history_window \
  --protocol-id qwen-v31-history-window-checkpoint-v1 \
  --backend transformers --strategy history_window --actor-prompt v31 \
  --model-id Qwen/Qwen3-4B-Instruct-2507 \
  --model-revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --device cuda --dtype float16 --context-limit 8192 \
  --generation-seed 0 --action-max-new-tokens 128 --memory-max-new-tokens 1024 \
  --game-fold train --seeds 0 1 2 3 \
  --num-locations 1 --num-ingredients 2 --num-distractor-items 0 \
  --no-include-doors --no-limit-inventory-size \
  --action-budget 80 --recheck-cost 2 --memory-token-limit 512 \
  --local-files-only
```

Maximum new real gameplay allocation is **eight episodes total**, four per phase,
with no automatic retries. Window gameplay losses are valid data and do not fail
implementation acceptance or justify forced recovery. Inspect whether any record
was evicted; if none was, report that the capacity intervention was nonbinding.
Do not shrink the allowance retrospectively. Infrastructure failures stop further
execution and remain errors, never mislabeled gameplay losses.

### Prepare-only, audit and tokenizer verification

Appending `--prepare-only` to either exact pilot command above validates/prepares
its existing manifest without loading model weights or performing gameplay. It
still checks the selected runtime and does not establish model capability. Keep
source and settings identical between preparation and execution. These real-runtime
manifest commands have not been run on this laptop.

Audit each condition independently:

```sh
.venv/bin/python -m game_memory.summarize_diagnostics artifacts/qwen-v31-history-window-checkpoint-v1/full_history
.venv/bin/python -m game_memory.summarize_diagnostics artifacts/qwen-v31-history-window-checkpoint-v1/history_window
```

Do not audit the common root to combine conditions: the existing mixed-identity
rejection is intentional. A small human-readable matched-seed comparison can be
assembled from the two reports if real gameplay is authorized. Report condition,
seed, status/error, success/termination, attempts, rereads/budget, invalid actions,
review/repair calls, input/output tokens, generation/episode time, maximum stored
tokens and evicted-record counts. Add a successful baseline trace annotation and
one informative window outcome, keeping missing-evidence versus decision-error
attribution uncertain where the trace cannot distinguish them.

The auditor checks window structure, the exact new public record, a contiguous
suffix of previously retained records, logger counts, budgets, latest actor inputs,
public-view whitelist and values, same-turn rejected proposals and inference
accounting. It derives these expectations from public trace events, **not** from
calling `HistoryWindowMemory.update()`. Requests and responses for any memory
writer/repair are forbidden in both history conditions, including failed requests.
Window metrics report update/max-token/eviction/empty-window counts and zero writer
calls, without labeling deterministic retention as unknown Qwen acceptances.
Its `token_count_method=recorded_trace_no_recount` is not independent retokenization.

The tokenizer-only verification, when the exact pinned tokenizer is cached, is:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q -rs tests/test_history_window.py::test_pinned_cached_tokenizer_recounts_unicode_and_eviction_without_weights
```

It includes escaping/Unicode and forced eviction, independently encodes every
stored rendering, and loads no model weights. It uses cached files only. Missing
pinned tokenizer/dependencies mean **unexecuted actual-tokenizer verification**,
not substitution with fixture word/character counts. No paid jobs or weight
downloads are authorized by this guide. Do not route this checkpoint through the
historical `scripts/modal_calibration.py` or replace its frozen digest constants.

## Implementation and interpretation limits

The small new strategy lives beside the unchanged full archive in `diagnostics.py`.
`actor.py` adds only context-mode selection/metadata with matched v31 history
messages. `runner.py` and `run_episode.py` wire the strategy and existing allowance,
fixture labels and context validation; the environment interaction loop is
unchanged. Existing GameConfig controls are exposed in the CLI to state distractors,
doors and inventory explicitly; their defaults and gameplay are unchanged.
`summarize_diagnostics.py` adds an independent public-history suffix audit and
window metrics, preserving generated-memory checks and mixed-condition rejection.
`pilot.py`, the model backend, game environment, generated writers, old notebooks,
replay harnesses and deferred evaluator were not changed for this checkpoint.

The laptop's Java 8 can run direct scripted simulator tests but rejects the pilot's
preserved Java 17 logging options. Previously recorded macOS Java 17 builds lack
the Linux os+container logging tag. Sandbox loopback restrictions also require
explicit local simulator access. No flags/assertions are removed to obtain a green
suite. Compatible Linux Java 17 and pinned model libraries/cache remain required
for real gameplay. Real Qwen runs have not been authorized in this handoff.

A binding window measures restriction of retained public records. Eviction alone
does not establish that a later failure was caused by that missing record; the
current view or legal information actions may still supply it. A wrong action
despite adequate available evidence is a different observation. No eviction means
no observed binding capacity intervention. This checkpoint makes no claim about
prose/JSON superiority, general reliability, fine-tuning, or a total-context bound.
Stop here; further prompts, writers, formats, prices or grids need a separate
research decision.


## Implementation validation and frozen source

The implementation was frozen after local verification with executable digest
`64c3520c626457a07f14f499e79b3947c4c4115f401cce93bba232b341756d84`. The base Git commit is
`18ade457aef86bf907c0877db9432d318095bfbc` with **dirty source**; the commit alone
does not reproduce this implementation. The exact executable/dependency/AGENTS
snapshot and SHA-256 are in
`artifacts/history-window-implementation-review/source-snapshot.zip` and its
adjacent checksum. Existing `runner.source_metadata()` produced `source.json`;
this is evidence, not a new experiment manifest system. Confirm this same digest
and fixed settings for both real condition manifests before Phase B. The future
real-condition directories have not been created or populated with gameplay.

Fresh CPU results on this source:

- Root collection: **544 tests**, no artifact/archive collection errors.
- Focused retention, actor, diagnostic, runner, generated-memory and auditor tests:
  **357 passed, one skipped, one warning**, 31.24 seconds.
- Full required command: **518 passed, 25 skipped, one failed, one warning**,
  45.81 seconds, exit 1. Failure remains
  `test_cli_prepare_and_launch_guard_work_together`: Java 8 rejects the preserved
  logging flags. The warning is an unraisable simulator cleanup BrokenPipeError
  in `test_repeated_inspections_reach_budget_with_trace`; it was not hidden.
- Actual pinned-tokenizer verification: **unexecuted**, explicitly skipped because
  Transformers is absent. Torch, tokenizers and Hugging Face Hub are also absent.
  The remaining optional model tests and Java 9+ logging regression still skip.
- Real-Qwen gameplay: **not run**, no inference/cloud authorization supplied.

Exact focused command:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q -ra tests/test_history_window.py tests/test_actor.py tests/test_diagnostics.py tests/test_diagnostic_summary.py tests/test_runner.py tests/test_memory_integration.py tests/test_memory.py
```

Full command:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

Local loopback access outside the sandbox was required for Java simulator checks.
A fresh runtime probe confirmed that neither default Java 8 nor the existing
macOS JBR 17 supports the preserved flags without failure/stdout diagnostics.
No Java portability patch, dependency installation, global configuration change,
weight download, paid job, push or deployment was performed.

Saved evidence in `artifacts/history-window-implementation-review/` includes raw
scripted traces and separate audits, historical full-history reaudits, test logs,
command verification, runtime checks and preservation checks. The two new local
scripted simulator fixtures each complete nine physical actions with one v31
preparation-review call and zero writer calls. Their 20-unit **whitespace fixture
counter** was deliberately small for eviction verification; it is not Qwen's
512-token experiment or an estimate of Qwen capacity/performance. Both results
are `integration_fixture`, with `real_model_capability_tested=false` in their audits.
The window fixture logs eight evicted records across seven updates; its initial
window is empty while the actor still receives the full initial AgentView.

Historical actor comparison covered **396** policy/context/scenario combinations,
two turns each: exact messages, generation purposes, returned actions and metadata
match the pre-change dirty actor. Full-history v31 prompt-hash regressions passed.
The FullHistoryMemory class and runner interaction loop have unchanged ASTs. Hash
checks confirm all **252** files in the two prior frozen v32 packages remain
unchanged. No historical evidence or failed attempt was removed or replaced.

Changed files and purpose:

| File | Necessary change |
| --- | --- |
| `game_memory/diagnostics.py` | Small stateless complete-record window beside unchanged full archive |
| `game_memory/actor.py` | Optional context mode, truthful identities, identical history prompts |
| `game_memory/runner.py` | Strategy/context validation; existing bound applies to window |
| `game_memory/run_episode.py` | Strategy selection before fake writer; explicit existing game controls |
| `game_memory/summarize_diagnostics.py` | Independent suffix/public-evidence audit, zero-writer checks and window metrics |
| `tests/test_history_window.py` | Retention, failure, parity, isolation, simulator, CLI, manifests, negative audits and cached-tokenizer verification |
| `AGENTS.md`, `README.md`, this guide | Canonical checkpoint, fixed commands, gates and interpretation |

No scientific departure was made. Explicit distractor/door/inventory CLI flags
were added solely to make the prescribed existing GameConfig controls visible
in both commands; defaults and simulator behavior remain unchanged. Source/data
preservation, matched messages, meaningful failure handling and independent audits
are verified locally. Actual tokenizer compatibility, the new four-seed baseline
gate and any effect of 512-token retention remain unverified.
