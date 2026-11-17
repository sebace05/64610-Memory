# Legal-choice-v1

This opt-in, untrained action-interface experiment preserves v31 as the default.
Its initial scope is `full_history` only. It retains v31's public-view JSON,
literal history, appliance/prerequisite guidance, and meal-finalization rules.
Only the system output sentence changes; an ordered JSON option list is appended
to the user message. The complete public action set remains present twice, without
sorting, filtering, normalization, pruning, or deduplication. There is no inventory
feed, exploration script, oracle information, or semantic rescue. A legal but
task-damaging selection is returned unchanged.

`LegalChoiceActor` assigns `ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`
in public action order, rejecting empty, malformed, duplicate, or over-52 action
sets before scoring. It accepts an exact label only, maps it to the canonical
action, and stores actions in ordinary gameplay history. It has no review, repair,
fallback, or cross-turn state. Consequently this compares actor-interface packages,
not just JSON formatting. Guaranteed interface legality does not guarantee a
correct cooking decision. It does not reproduce the paper's trained-reader
performance, training, regret analysis, or serving infrastructure.

## Scoring and accounting

The actual tokenizer must encode each label as one distinct, nonspecial output
vocabulary token. For the exact chat-template string P, rendered with
`tokenize=False, add_generation_prompt=True`, every `encode(P + label)` must equal
`encode(P) + [label_token_id]`, without special tokens. Standalone encoding is
insufficient. Failed validation is an infrastructure error, without retries.

The adapter tokenizes P without duplicate special tokens or truncation, reserves
one context position, and performs exactly one forward pass under inference mode,
with `use_cache=False` and no past cache. It never calls `generate`. Final-position
candidate logits are converted to float32. Only those candidates compete; finite
scores are mandatory. Stable softmax probabilities are conditional on the legal
label set. Exact ties choose the first supplied label. Configured device, dtype,
and attention implementation remain unchanged; bitwise reproducibility is not
promised.

Each response preserves ordered labels, token IDs, float32 logits, conditional
probabilities, selected label/token, argmax/tie rules, and evidence provenance.
Input tokens count the actual templated prompt; output tokens count one selected
next-token decision. `action_max_new_tokens` is unused by this scorer. Latency is
synchronized forward-pass time, excluding tokenization, validation, transfer,
and CPU candidate selection; it is not ordinary generate latency. CUDA peak
allocation is recorded when applicable. Requests are flushed before inference;
backend exceptions and non-Generation returns preserve prior usage and mark
usage incomplete. Every returned Generation is counted and logged unchanged
exactly once before its decision-token count is checked. A returned count other
than one raises `ValueError: choice scoring must report one decision token`,
without an action, retry, repair, or model_error. Its known usage remains complete;
the terminal sequence is model_request → model_response → episode_error →
episode_end. Gameplay losses remain distinct from infrastructure errors.

`rendered_prompt_sha256` hashes the UTF-8 bytes of the actual P that is tokenized,
including the generation prompt, whitespace, and Unicode. The response marks this
`actual_rendered_prompt`; this is prompt evidence, not proof of correct behavior.
Fake fixtures instead use null and `unavailable_fixture`, with explicitly synthetic
IDs, word counts, scores, and zero latency. They cannot establish Qwen capability.
The independent auditor derives mapping/history expectations from trace events,
checks ordered sequences, scoring arithmetic, canonical actions, usage and costs,
and validates hash format/provenance. It cannot independently verify the hash's
value without the matching tokenizer/template. Actual scoring responses also
record `special_token_ids`, the sorted unique inventory from the actual
tokenizer's `all_special_ids`. The actual-evidence audit requires a sorted,
duplicate-free list of nonnegative integers disjoint from candidate IDs, retaining
output-vocabulary bounds checks. This checks consistency of recorded evidence;
it does not independently reload the tokenizer or prove every logged field true.
Fixture inventories and IDs remain synthetic software checks, never Qwen
verification. After the first episode_error, the legal-choice auditor allows only
the final episode_end. An unexpected output count is accepted only as recorded
failure evidence with the immediately matching action_generation ValueError and
episode_end, result.status=error; it cannot be an executed decision or completed
game. All other scoring/accounting checks remain in place. Its fixed system-prompt digest is
derived from the preserved v31 full-history parity fixture with only the required
sentence replaced; it is separate from the model's rendered-prompt hash.

## Offline verification status

Implementation uses scripted CPU components and stub-environment integration.
The existing v31 parity fixtures and expected hashes remain unchanged. Optional
tiny-random CPU forward tests and pinned cached-tokenizer-only verification are
included. In this environment torch/transformers are unavailable, so actual tiny
forwards and actual cached-Qwen-tokenizer validation are **unexecuted**, not passes.
See the implementation evidence linked below for final commands, counts, exit
statuses, preservation hashes, and platform failures. No actual Qwen weights or
GPU behavior have been verified. No scientific episodes, pretrained Qwen inference,
downloads, installations, cloud jobs, or paid compute are authorized by this work.

## Verification fixes — 2026-11-17

The historical implementation report above retains its original verification
status. Fresh evidence: [verification attempt](../artifacts/legal-choice-v1-verification/attempt-20261117-164128/report.json).
The required five-file selection passed **244 tests**, skipped **1** (torch
unavailable), and emitted **1** upstream TextWorldExpress destructor
BrokenPipeError warning; exit status **0**. The explicit optional selection stayed
at **8 cases**: all skipped (7 require torch; 1 requires transformers), 20
deselected, exit **0**, no warnings. Tiny-model forwards and pinned cached-Qwen
tokenizer/configuration verification remain **unexecuted**. No cache availability
is established when its dependency cannot import.

The full suite passed **383 tests**, skipped **25**, emitted the same **1**
upstream warning, and exited **0**. Skips: 23 transformer tests, 1 torch-dependent
pilot test, and 1 Java 9+ unified-logging regression on the local older runtime.
The 16 new regression cases also passed separately with preserved synthetic
traces. Existing V31 fixtures and source outside the six-file allowlist retain
their starting hashes. Initial sandbox/Py4J interruptions and new-test setup
failures are preserved alongside successful reruns; no runtime configuration was
changed. Simulator fixture checks used local Java access outside the sandbox.
No scientific gameplay, pretrained weights/inference, downloads, installations,
cloud jobs, or paid compute occurred. GPU behavior remains unverified, and the
prepared real command below remains unexecuted and requires separate authorization.

## Prepared command — NOT EXECUTED

Execution requires separate authorization. Use this fresh destination only for
these fixed settings; preserve startup streams and original exit status as in the
minimal-core workflow. The stored allowance is configured but exempt for full
history; the action and memory generation caps are unused by this policy.

```sh
.venv/bin/python -m game_memory.run_episode \
  --backend transformers --actor-prompt legal-choice-v1 --strategy full_history \
  --protocol-id qwen-legal-choice-v1 --seeds 0 2 \
  --output-dir artifacts/qwen-legal-choice-v1/full-history-attempt-1 \
  --model-id Qwen/Qwen3-4B-Instruct-2507 \
  --model-revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --device cuda --dtype float16 --generation-seed 0 --context-limit 8192 \
  --action-max-new-tokens 128 --memory-max-new-tokens 1024 --local-files-only \
  --game-fold train --num-locations 1 --num-ingredients 2 --num-distractor-items 0 \
  --no-include-doors --no-limit-inventory-size \
  --action-budget 80 --recheck-cost 2 --memory-token-limit 512
```

[Implementation evidence](../artifacts/legal-choice-v1-implementation/attempt-20261117-103859/).
