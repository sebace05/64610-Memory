# Shared Codex development prompt: Qwen memory calibration

Use this same prompt for every session, assigning exactly one role: **A, B, C,
or D**. The role assignment goes in the session's opening message. Implement
only that role. This is shared contract `memory-development-contract-v1`.

You are working in `/home/seb/64610-Memory`. Implement the assigned part of the
pre-calibration development described below. Make the changes and run meaningful
checks; do not stop at proposing an implementation.

**Read first**

- `AGENTS.md`.
- `docs/memory-constraints-design-and-task-plan.md`, especially sections 3–5
  and 9–11.
- `docs/reproduction-2026-11-15.md`.
- The real callers, implementation, and tests of your assigned files.

The reproduced baseline used memory v16 and actor v29. All 30 prose memory
updates came from programmed fact fallbacks, while JSON accepted 34/36 model
writes. We are preparing a fair, model-written prose/JSON calibration. Useful
Qwen-written memory and successful gameplay must be assessed before tightening
the allowance. Do not try to reproduce the old win rate by restoring fact helpers.

This assignment authorizes implementation and automated checks corresponding
to T1–T6. It does **not** authorize real-Qwen runs, model downloads, GPU jobs,
calibration, prompt tuning with live inference, or a development/evaluation grid.
The user has not yet frozen the tight/generous allowances or chosen an 8-versus-
16-game comparison. Do not turn candidate values into experiment defaults.

**Shared working rules**

All sessions use the same checkout and filesystem. Edit only your role's files.
Do not switch branches, create worktrees, stage/commit another session's work,
reset/revert concurrent edits, or remove untracked reports/artifacts. Do not
spawn subagents for this assignment. Coordinate necessary interface changes
through the integration owner rather than changing this contract independently.

Reuse the current architecture, standard library, model adapter, and logging.
No new dependencies, dashboard, training, retrieval backend, generic scheduling,
resume machinery, or performance refactor. Keep hybrid outside the new study;
preserve its existing syntax/rendering compatibility without developing it.

Use `.venv/bin/python`. Run focused tests for your ownership while development
is concurrent. The integration owner runs the full suite after the combined
code is stable. Treat a test failure caused by another unfinished workstream as
an integration dependency: report evidence, and do not weaken or edit its checks.

## 1. Public component interfaces: keep these unchanged

Use the existing definitions in `components.py` and `contracts.py`:

```python
MemoryContext(goal, budget_remaining, recheck_cost, memory_token_limit)
MemoryUpdate(memory: str, events: tuple[str, ...] = ())

MemoryStrategy.empty() -> str
MemoryStrategy.render(memory: str) -> str
MemoryStrategy.update(previous_memory, action, observation, context, model) -> MemoryUpdate

Actor.choose_action(view: AgentView, memory: str, model: Model) -> str
Model.generate(messages, *, purpose: str) -> Generation
Model.count_tokens(text: str) -> int
```

No new persistent facts, plans, or hidden history may be stored outside the
serialized memory. All persistent content must appear in `render()` and count
against the allowance. The actor also receives the current public `AgentView`;
this is a stored-memory constraint, not a limit on the entire action prompt.

The memory writer gets only the existing previous-memory/action/observation/
public-context payload. The actor gets only the current public view and supplied
memory. No scores, environment handles, cached recipes, trace history, evaluator
annotations, or gold paths may be introduced. All inference passes through the
supplied logged model, including reviews and repairs.

Do not change these interfaces without the integration owner's agreement.

## 2. Shared memory behavior and identifiers — Role A owns implementation

Reserve `p1-memory-v17` for this policy; metadata `version` is 17. Before editing,
verify that another session has not already introduced that version. If it has,
coordinate rather than silently reuse or increment it independently.

Prose and structured JSON must use the same substantive writer instructions:
retain useful supported recipe, inventory, and progress information; update it
from the latest evidence; compress or omit information to fit. Qwen chooses the
facts and compression. An omitted fact is a measurable writer outcome.

Only the format instructions differ:

- Prose: concise natural-language sentences or bullet notes, rendered verbatim.
  No required task headings, fixed inventory/progress template, or mandatory
  complete-recipe retention.
- Structured: one model-managed JSON object. Preserve existing strict parsing,
  duplicate-key/numeric/Unicode safeguards, and compact canonical rendering.
  Do not impose a predefined recipe/inventory schema.

The common update algorithm is:

1. Validate the previous state and its rendered size as currently required.
2. Generate one candidate with `purpose="memory"`.
3. Check representation syntax and exact rendered token count. Do not check
   recipe retention, inventory truth, or progress truth as acceptance conditions.
4. On syntax/size rejection, allow one `purpose="memory_repair"` call with the
   same evidence, rejected candidate, format instructions, and syntax/size reason.
   Do not calculate or supply corrected facts in Python.
5. Accept a valid, within-limit candidate. Empty prose and `{}` are valid outputs.
6. If both attempts fail, return the supplied previous valid serialized state
   unchanged. At initialization this is `empty()`. Never insert the initial
   recipe or construct a public-fact replacement memory.

Never truncate generated memory to fit. Model/tokenizer/transport errors remain
infrastructure errors and propagate through the runner; they are not fallback.
Do not hide or reinterpret a failed generation's usage.

Required memory metadata, alongside existing identity/JSON fields:

```text
prompt_version: p1-memory-v17
version: 17
update_policy: syntax_and_size_one_repair_previous_state_v1
semantic_validation: none
fallback: previous_valid_memory
max_repairs: 1
render_version: p1-render-v2
```

Keep `p1-render-v2` because rendering is unchanged. Any required rendering change
needs an explicit coordinated revision, not reuse of this identifier. Keep
`is_fake: false`, strategy names `prose`/`structured`, and real implementation
identities. Do not add a runtime v16/v17 switch: the baseline source snapshot
and pinned commit preserve v16 unless a documented comparison requires more.

Keep these existing logger-only event names and meanings:

```text
memory_accepted
memory_repair_accepted
memory_rejected:<syntax-or-size-reason>
memory_repair_rejected:<syntax-or-size-reason>
memory_json_canonicalized
memory_repair_json_canonicalized
memory_fallback:previous_valid_memory
```

Canonicalization is an additional event, not another update. Exactly one final
acceptance or fallback outcome should describe each successful update. New v17
updates must not emit semantic rejection reasons such as `recipe_dropped`, or
`memory_fallback:public_evidence` / `memory_fallback:initial_public_observation`.
Retain existing detailed syntax/numeric reason codes rather than inventing a
second validation taxonomy. Leave deliberate empty writes classified as accepted;
analysis will also flag emptiness separately.

## 3. Shared actor behavior and identifiers — Role B owns implementation

Reserve actor argument `v30`, with bounded metadata `s2-action-v30` and diagnostic
full-history metadata `full-history-v30`. Verify availability before editing.
Keep existing versions intact and require explicit selection of v30; do not
silently change the global actor default for historical callers.

Base v30 on v29's generic gameplay and format-neutral Qwen review behavior:

- Use one substantive policy for prose and JSON, without required key names or
  prose headings. Read the supplied context to identify facts.
- If information needed for a decision is missing or uncertain, permit a legal
  cookbook reread or other normal information action. Do not assume the recipe
  is permanently available in memory and do not force a reread when it is known.
- Preserve general appliance/mechanics guidance and v29's logged model-based
  meal review/unavailable-action repair. Preserve optional-article action matching
  and allowed-action validation. Do not substitute a programmed useful action.
- Keep legal repeated actions available. No inspection blacklist, hidden loop
  detector, or semantic action veto outside the declared model policy.
- Use the same substantive instructions with full-history diagnostics, changing
  the context label as appropriate. History remains diagnostic-only.
- The new bounded path must not maintain or consult the unused persistent
  inspection-result cache. Within-turn repair messages/proposals are allowed;
  they must not persist as extra factual state between turns.

Keep model purpose labels `action`, `action_review`, and `action_repair`. Keep
review/repair policy metadata truthful; reuse existing v29 identifiers only for
unchanged review/repair behavior. Do not modify old-version prompts to implement
v30. Review policy identifiers may be reused unchanged when only the main actor
prompt changes; coordinate a new identifier if review behavior itself changes.

## 4. Runner and trace contract — all roles consume; D owns core changes

Preserve initialization, turn order, terminal handling, inference accounting,
usage completeness, fresh episode state, and the independent rendered-memory
guard in `runner.py`. No memory write occurs after a terminal action.

Preserve raw requests/responses, exact observations, memory-update events,
validation events, actions, results, errors, and purpose-level accounting. Keep
existing `MemoryUpdate.events` strings and derive new summaries from those plus
raw trace records; no component interface change is needed for telemetry.

`status: completed` includes gameplay losses; infrastructure failures remain
`status: error`, `success: null`. Do not relabel syntax-repair fallback or wrong
facts as infrastructure errors. A generation cut off by its output limit must
remain visible. Preserve the real launcher exit status; if unavailable, report
unknown instead of inferring zero from a completed episode.

Offline fact annotations and format-adherence checks must never reject a live
memory, repair an action, or feed facts back to the actor/writer.

## 5. Preflight and comparison manifest contract — D produces, C consumes

Extend the existing preflight, not a separate launcher framework. Use this
signature extension for `prepare_pilot`:

```python
prepare_pilot(directory, episode, actor, model, backend, seeds, *,
              memory_metadata: dict, protocol_id: str) -> dict
```

D owns all caller/test adaptations, including signature-only compatibility
changes in the deferred `evaluate_3x2.py` path. Select memory early enough to
capture its real metadata before loading weights. Require a nonempty protocol
identifier. D owns any small CLI wiring needed to provide it; preserve explicit
generic identities for existing fixture/capability paths instead of mislabeling
them as the new comparison.

New pilot manifests use schema version 2, retaining existing fields and adding:

```text
memory: exact selected MemoryStrategy.metadata dictionary
protocol_id: nonempty protocol identifier
source.source_digest: deterministic executable/dependency source fingerprint
```

`source_metadata()` should provide the same source identity to the manifest,
episode header, and result. Reuse the existing digest approach through a small
shared helper in existing code; do not import the deferred evaluation launcher
into the normal pilot path. D owns moving/re-exporting that helper and its tests.

Reject memory/actor/model/source/protocol/allowance changes or mismatched existing
results before loading weights. Reject old manifests for adoption into new runs;
do not rewrite or migrate historical artifact files. Make new optional fields
backward-readable in offline reports, with missing evidence marked unknown.

The future grid is described by a small `comparison-manifest.json`, schema 1,
with these required top-level keys:

```text
schema_version: 1
protocol_id: string
stage: development | held_out
source: the source_metadata identity, including source_digest
actor: exact actor metadata
memory: mapping from strategy name to its exact memory metadata
model: serialized TransformersConfig fields
runtime: recorded model runtime/package/GPU metadata
game: serialized CookingWorldConfig fields
action_budget: integer
strategies: unique list drawn from [prose, structured]
memory_token_limits: unique positive integer list
recheck_costs: unique list drawn from [2, 5]
seeds: unique integer list
```

Expected cells are the Cartesian product of the last four lists. Match episode
configuration and component metadata to the manifest, including model/runtime
fields and correct development/test-fold labeling. This is a small declared
grid and evidence format, not a new batch/resume engine. Each `(strategy, memory
limit, price)` has a separate condition directory and immutable pilot manifest.

For this comparison, require both strategies, exactly two distinct memory limits,
and one or two reread prices. Determine low/high from the numeric limits rather
than list order. One-condition generous-memory checks can use the existing
per-condition auditor; they do not need a pretend comparison contrast.

D and C must use this same schema. Synthetic tests may use 64/256 as fixture
values; that does not freeze them for a real experiment. Do not create a live
comparison manifest with guessed allowances or invent final sample sizes.

## 6. Analysis and annotation contract — Role C owns implementation

Reuse the existing auditor separately for each condition. It intentionally
rejects mixed configurations; do not weaken it to summarize a whole factorial
grid as one pilot. A new focused `game_memory/analyze_memory_budget.py` may
aggregate those audited conditions against the comparison manifest.

Analysis functions should return JSON-compatible summaries and be tested
directly. Produce JSON/CSV/Markdown through a thin CLI; avoid a new plotting or
orchestration dependency. Require exact planned coverage; flag duplicates,
missing/partial/error cells, wrong settings, and mixed versions. Never substitute
a valid loss or silently exclude invalid model outputs from the primary results.

Report by format, allowance, price, and seed:

- Success, termination reason, score, actions, rereads, and budget spent.
- Primary accepted updates, repaired accepted updates, previous-state fallback,
  accepted empty writes, and the denominator `memory_updates`.
- Stored memory tokens/utilization, over-budget and syntax rejection counts,
  generation-limit hits, and measurable candidate sizes. Invalid JSON has no
  valid canonical rendered size; distinguish it from raw output tokens.
- Model calls/input/output tokens by purpose, generation and episode time, and
  loading separately. Include failed/rejected attempts and usage completeness.

Acceptance/fallback classification is mutually exclusive per update; empty-write
classification is additional. Compute emptiness using the declared representation
(`""` for prose, `{}` for structured), without stripping stored prose or changing
it. For old traces with insufficient provenance, report unknown. If tokenizer
recounts are implemented, use the pinned cached tokenizer and record the method;
do not assume generated output-token counts equal rendered-memory counts.

Prepare small offline public-evidence checklists for development seeds 0/1 at
reset, after taking/preparing ingredients, and before meal preparation or a
terminal mistake. Record supporting event IDs. Distinguish supported facts,
omissions, contradictions, invented facts, and unknown cases. Empty memory cannot
earn perfect retention merely by making no incorrect claims. These are diagnostic
fixtures, never an online fact oracle or a new writer repair mechanism.

The primary allowance contrast is matched high-minus-low success within each
format; their difference is the format-by-allowance interaction. Two development
seeds support descriptive results, not strong statistical claims. Do not reuse
the old hybrid/120-game analysis as though it already supports this design.

## 7. Role ownership and deliverables

**Role A — T1: memory policy**

Own `game_memory/memory.py`, `tests/test_memory.py`,
`tests/test_memory_integration.py`, and `docs/p1-memory.md`.
Implement section 2. Test valid fact omission, structurally valid factual errors,
empty memory, malformed/oversized candidates, one repair maximum, exact unchanged
fallback, no initial recipe injection, statelessness, numeric fidelity, bounds,
and logged inference accounting. Keep all independent syntax/isolation safeguards.

Explicitly retire tests for removed v16 semantic behavior rather than merely
weakening them until they pass. The pinned v16 source/artifacts preserve that
baseline; add tests for the new experimental boundary. Do not edit actor,
components, runner, CLI, or preflight files.

**Role B — T2: actor policy**

Own `game_memory/actor.py`, `tests/test_actor.py`, and `docs/actor-policy.md`.
Implement section 3. Test that legal rereads and repeated actions remain
available, formats receive the same policy, reviews/repairs use the supplied
model and bounded evidence, and prior history does not affect the new path
outside memory. Fake-model tests verify wiring/boundaries, not actual prompt
quality; leave real-Qwen effectiveness to later calibration. Do not edit memory,
runner, manifests, or analysis.

**Role C — T4/T5: evidence and analysis**

Own `game_memory/summarize_diagnostics.py`, `tests/test_diagnostic_summary.py`,
the proposed `game_memory/analyze_memory_budget.py` and
`tests/test_analyze_memory_budget.py`, plus a narrowly scoped
`tests/fixtures/memory_annotations/` directory and
`docs/memory-annotation-guide.md` if needed.
Implement section 6 against the existing trace format and the manifest contract
in section 5. Use synthetic fixtures for missing/duplicate/mislabeled cells and
the preserved reproduction for backward-reading checks. Never edit old artifacts
or mix baseline v16 and new v17 into a format-only effect. Do not edit the live
writer, actor, runner, or CLI.

**Role D — T3/T6: preflight and integration owner**

Own `game_memory/pilot.py`, `game_memory/run_episode.py`, identity-related edits
in `game_memory/runner.py`, `tests/test_pilot.py`, `tests/test_runner.py`,
CLI/session compatibility tests in `tests/test_transformers_model.py`, and
signature/digest compatibility edits in `game_memory/evaluate_3x2.py` and
`tests/test_evaluate_3x2.py`. Own protocol/integration documentation and any
necessary README/checkpoint-guide updates. Notebook configuration changes can
wait until the CLI and calibration settings are settled.

Implement section 5, coordinate dependencies on A/B/C, and review the combined
behavior. A normal `run_episode --prepare-only` preflight must capture the memory
identity without allocating model weights. Test changed memory metadata, source,
protocol, allowance, and orphaned/partial artifacts. Verify that source-digest
changes are detected and all original exit/error evidence is preserved.

D is the integration owner, not permission to edit A/B/C files concurrently.
Request a focused patch/handoff from their owner for cross-file issues. After
all roles hand off, run:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

Investigate failures without rewriting historical evidence or erasing another
session's changes. The previous 313-test pass is a baseline, not a required test
count: new tests and explicit retirement of obsolete policy tests may change it.
Prepare a calibration-readiness report; do not start GPU calibration under this
assignment. Be the designated GPU/evidence owner when the user later starts T7.

## 8. Completion and coordination

Begin by stating your assigned role, owned files, and any contract mismatch you
find. Implement within that ownership without asking for permission on routine,
reversible changes. If another role has not finished a dependency, continue
independent work and report the specific dependency; do not invent a competing
API or modify its files.

Keep shared reports and this contract read-only unless you are explicitly
assigned their maintenance. Only the integration owner may coordinate a contract
amendment; every affected session must receive it before implementing a change.

At handoff, provide:

1. Files changed and the behavior implemented.
2. Exact test commands, results, skips, and failures.
3. Interface/version/event compliance and integration dependencies.
4. Remaining uncertainty, especially what fake tests cannot establish.
5. Confirmation that no GPU job, real-model tuning, or old-artifact modification
   occurred.

Each role also owns its own handoff note at
`docs/dev-handoffs/memory-calibration/ROLE.md` (replace ROLE with A, B, C, or D).
Use status `IN_PROGRESS`, `READY`, or `BLOCKED`, plus the information above. Never
edit another role's note. This is the coordination channel when separate Codex
sessions cannot message each other directly; no coordination service is needed.
D may implement its independent work immediately, but starts final integration
checks only after A/B/C report `READY` and have stopped editing their files.
Integration fixes go back to the relevant owner, which updates its own note.

The next gate is an integrated, tested implementation ready for separately
authorized T7 calibration. It is not a claim that either writer already works,
that an allowance is binding, or that either format is superior.
