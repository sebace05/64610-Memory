# P1: bounded-memory representations

`game_memory.memory` provides `ProseMemory`, `StructuredMemory`, and
`HybridMemory`. They implement the existing `MemoryStrategy` protocol without
changing the contracts, actor, environment, or runner. Hybrid remains outside the new comparison; its existing syntax and rendering
are retained for compatibility. These are production
strategy implementations; local tests use scripted generations and controlled
counters, not a real LLM or the Qwen tokenizer.

## Interface and use

```python
from game_memory.memory import ProseMemory, StructuredMemory, HybridMemory

memory = ProseMemory()  # Or StructuredMemory(); hybrid is deferred.
state = memory.empty()
# Liam supplies model; runner supplies the latest permitted evidence and context.
update = memory.update(state, action, observation, context, model)
state = update.memory
actor_visible_memory = memory.render(state)
```

Supply the chosen object directly as `memory` to the existing `run_episode()`;
its metadata strategy must match `EpisodeConfig.strategy`. CLI/backend integration is maintained separately; this policy changes no public
component interfaces.

`MemoryUpdate` contains serialized state and logger-only validation events.
The runner records events, counts rendered memory again, and owns inference
usage totals. Strategies store no model, facts, state, or message history on
their instances. All persistent factual information is in the supplied serialized
state and is exposed by `render()`. The returned state, rather than the hybrid
rendering, must be passed as `previous_memory` on the next update.

## Representations and validity

| Strategy | Empty serialized state | Actor-visible rendering |
| --- | --- | --- |
| Prose | `""` (zero characters) | Exact notebook text, including whitespace. |
| Structured | `{}` | Canonical serialized JSON object. |
| Hybrid | `{"prose":"","structured":{}}` | The labeled rendering below. |

Hybrid rendering is exactly:

```text
Prose:
<prose string>
Structured JSON:
<canonical structured object>
```

There is no trailing newline added after the structured object. An empty hybrid
renders as `Prose:\n\nStructured JSON:\n{}`. Both labels, all newlines, notebook
text, and JSON syntax share ONE total allowance. Neither store has a separate
limit or reserved allocation. Duplicate facts in the stores remain duplicated.
The envelope has exactly two fields, `prose` (string) and `structured` (object).
Extra keys are rejected so the envelope cannot carry unrendered facts. These
fields define syntax, not task-specific semantic slots.

Prose accepts UTF-8-encodable text verbatim, including empty text. Validation
does not judge whether prose is natural language, truthful, useful, or formatted
well; those are model behaviors to inspect later. Nothing is trimmed or truncated.

Structured memory requires one top-level JSON object. Keys and nested JSON
values are otherwise model-managed: objects, arrays, strings, numbers, booleans,
and null are allowed. There are no predefined recipe/location/status fields.
Hybrid's structured portion uses the same policy. Both reject:

- Malformed/trailing JSON, code fences, comments, and wrong top-level types.
- Duplicate keys at any nesting depth.
- `NaN`, `Infinity`, `-Infinity`, and floating-point overflow such as `1e400`.
- Decimal or exponent numbers whose value would change when serialized through
  Python's finite float representation, including precision loss and underflow.
- Numbers whose decimal exponent cannot be parsed by `Decimal` are rejected with
  `json_number_unrepresentable` and follow the same one-repair/fallback policy.
- Unpaired Unicode surrogates that cannot be rendered as ordinary UTF-8 text.
- Invalid hybrid field names or types.

JSON uses Python's standard parser/serializer: integers use Python integers.
Decimal/exponent numbers are accepted only when the decimal value of the parsed
finite float's serialized form equals the original decimal value. For example,
`1.2300` may render as `1.23`, while `9007199254740993.0`, `1e-400`, and
`0.10000000000000001` are rejected and offered one model repair. A writer can
retain an exact quantity as a JSON string. The strategy does not change a
numeric fact silently.
Canonical formatting sorts object keys recursively, uses compact `,`/`:`
separators, emits literal Unicode where possible, and adds no outer whitespace.
String contents (including whitespace) are preserved. The prompt requests this
same form. No missing keys, braces, or values are inferred; no semantic repair or
deduplication occurs in Python.

When an accepted model response differs from canonical serialized state, an
explicit `memory_json_canonicalized` or `memory_repair_json_canonicalized` event
records the transformation. Raw responses remain available through the runner's
model-call trace. Structural whitespace removed by this declared policy is not
part of stored actor-visible memory; all remaining punctuation, keys, escaping,
and string whitespace count. Raw generation usage is still accounted separately.

## Shared update policy and accounting

Prompt version `p1-memory-v17` (metadata version 17) shares the substantive writer instructions across
prose and structured JSON: retain useful supported recipe, inventory, and progress
information, update from evidence, avoid invented facts, and compress or omit
information to fit. Only representation instructions differ. Prose has no required
headings, inventory/progress template, or complete-recipe retention rule. JSON
remains model-managed without a predefined task schema. Hybrid retains its existing
syntax/rendering compatibility and is outside the new comparison. Only format instructions differ. Every
writer gets the same permitted fields: rendered previous memory, action, new
observation, goal, remaining action budget, reread price, and token allowance.
No legal-action list, score, environment handle, or raw history is added.

Each update:

1. Validates and counts the previous state (use `empty()` for initialization).
2. Calls the supplied model once with `purpose="memory"`.
3. Validates syntax, creates the complete rendering, and calls
   `model.count_tokens(rendered)` against `context.memory_token_limit`.
4. If invalid or oversized, calls the same supplied model at most once more with
   `purpose="memory_repair"`. This receives the original messages, rejected
   response, and validation reason; no additional task evidence is introduced.
5. Accepts a valid, within-limit candidate, including empty prose and `{}`.
6. If both attempts fail, returns the exact supplied previous valid serialized
   state unchanged. At initialization this is `empty()`. No initial recipe,
   inventory, progress, or public-fact replacement is constructed in Python.

Metadata declares `update_policy: syntax_and_size_one_repair_previous_state_v1`,
`semantic_validation: none`, `fallback: previous_valid_memory`, and `max_repairs: 1`.
Rendering remains `p1-render-v2`; JSON identity and numeric safeguards are unchanged.
The v16 semantic validators, mandatory prose headings, fact-specific repair hints,
and public-fact fallback builders are retired, along with their policy tests.
The pinned v16 commit and reproduction artifacts preserve that baseline; there
is no runtime version switch. Omissions, stale facts, and invented facts are
measurable writer outcomes, not live rejection conditions.

Each successful update emits exactly one final outcome: `memory_accepted`,
`memory_repair_accepted`, or `memory_fallback:previous_valid_memory`.
Rejections use `memory_rejected:<reason>` or `memory_repair_rejected:<reason>`
with existing syntax/numeric/size reason codes. JSON canonicalization is an
additional event, never another update or acceptance. Empty writes are accepted.
There is no runtime v16/v17 switch. The pinned v16 source and artifacts preserve
its semantic validators and programmed factual fallbacks as historical evidence.
Their obsolete policy tests are explicitly retired; v17 tests assert that factual
omissions and errors are accepted when syntax and rendered size are valid.

Events preserve the existing syntax/numeric/size reasons:
`memory_rejected:<reason>` and `memory_repair_rejected:<reason>`.
Exactly one final outcome is emitted: `memory_accepted`,
`memory_repair_accepted`, or `memory_fallback:previous_valid_memory`.
Canonicalization adds `memory_json_canonicalized` or
`memory_repair_json_canonicalized`; it is not another update. Empty writes remain
accepted outcomes. No semantic rejection or public-evidence fallback event is
emitted. Repair gets the same evidence, rejected candidate, format instructions,
and syntax/size reason; Python supplies no corrected facts. No generated memory
is truncated. The runner's independent rendered-memory guard remains authoritative.

All inference, including repairs, passes through the supplied model. The existing
`_LoggedModel` records both purposes and includes their tokens and runtime in
episode totals. Token counts must be nonnegative integers. Model/transport and
tokenizer exceptions propagate as component errors, not memory fallback events.
An invalid/oversized predecessor, or a limit too small even for the format's empty
rendering, fails before generation rather than inventing another fallback.

## Example fixture

For all three formats, tests supply exactly the same initial evidence:

```text
Action: [INITIAL_OBSERVATION]
Observation: Recipe: dice and grill the cheese.
Context: goal="Prepare the meal.", remaining budget=80, reread price=2,
         memory allowance=256
```

Scripted accepted outputs and their renderings are:

| Strategy | Model output / serialized state | Rendering |
| --- | --- | --- |
| Prose | `Dice and grill cheese.` | Same text. |
| Structured | `{"note":"Dice and grill cheese."}` | Same canonical JSON. |
| Hybrid | `{"prose":"Dice and grill cheese.","structured":{}}` | `Prose:\nDice and grill cheese.\nStructured JSON:\n{}` |

The example's `note` key is chosen by the test model, not required by the strategy.
Tests also retain the same fact in both hybrid stores to demonstrate duplication
is allowed, and reject a combined rendering exceeding 256 even when each store
alone would fit.

Run from the repository root with the documented test dependencies:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_memory.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_memory_integration.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

P1 tests cover representations, common fixture/evidence/instructions, exact-bound
and one-over-bound candidates, syntax/format accounting, repair/fallback, stateless
strategy objects, numeric fidelity, and accounting through the existing logged
adapter. `tests/test_memory_integration.py` also runs all three production memory
strategies at both prices through the real simulator, actor, and runner using
scripted fake inference. It checks repair/fallback, actor-visible rendering,
trace/result persistence, fixture labeling, inference totals, and reuse of the
same strategy object across episodes. Controlled
character counters (including weighted variants) make boundaries deterministic;
they do not establish correct Qwen tokenization or real-model memory quality.
The model adapter must supply the actual tokenizer without chat-template tokens,
stateless generation, and production model/runtime metadata. P2 isolation and
full-history work remain separate.
