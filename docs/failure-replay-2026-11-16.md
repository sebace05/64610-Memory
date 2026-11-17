# Saved-request replay diagnosis — reminder additions did not fix failures

November 16, 2026. One A10 diagnostic ran **18 calls: nine saved requests,
each baseline plus one system-prompt addition**. All nine baseline responses
reproduced their original saved outputs exactly. None of the six selected failure
cases was fixed; all three selected successful controls retained their narrow
correct behavior. No production prompts were changed or episodes rerun.

| Case | Baseline | Prompt addition |
| --- | --- | --- |
| Actor chooses chop despite stored slicing instruction | Wrong cut | Same wrong cut |
| Successful actor slicing control | Correct | Correct |
| Successful actor eating control | Correct | Correct |
| Writer claims meal completion after ingredient grilling | Unsupported completion | Unsupported completion persists; adds meal ready to enjoy |
| Writer drops existing recipe after invalid action | Recipe omitted | Same omission |
| Writer fails to restore recipe after cookbook reread | Recipe omitted | Recipe still omitted; JSON reformatted |
| Successful writer grilling-progress control | Selected facts retained | Selected facts retained |
| JSON repair after taking knife | Extra closing brace | Same malformed JSON |
| JSON repair after slicing apple | Extra closing brace | Same malformed JSON |

These are manually reviewed, case-specific criteria, not whole-notebook accuracy
or an unbiased benchmark. Actor legality was checked separately: chopping was a
legal action but contradicted the stored recipe method. Writer control scoring
covers the recipe and confirmed grilling only, not every claim in the notebook.
JSON repair validity uses the production syntax parser offline; no repaired text
is substituted for model output. There was no previously successful saved JSON
repair control in this selection; successful actor/writer controls provide only
partial regression coverage.

## What changed and what stayed fixed

`scripts/replay_failures.py` extracts exact model requests from preserved public
traces. It records trace/request hashes, original outputs, immutable case plans,
all actual model requests/responses, usage and model identity. It makes no game
actions and never fills notebook facts from Python. Offline assessments remain
outside model messages. Baseline messages are exact; variants change only the
system message, preserving all user evidence and any existing repair conversation.

Three diagnostic suffixes were frozen before launch:
- `actor-method-v1`: require the exact recipe preparation method; distinguish
  slicing/chopping and grilling/roasting/frying.
- `writer-facts-v1`: distinguish observed facts, requirements and plans; require
  public confirmation of completion; retain recipe, possession and progress;
  avoid inventing legal-action lists.
- `repair-json-v1`: preserve intended content while checking delimiters and
  returning exactly one valid JSON object without extra closing braces.

The suffixes are appended to the existing production system prompts. This tests
whether reminders help, not whether all alternative prompt designs fail. No
variant was tuned after observing its output. The writer completion failure
actually became more emphatic under its suffix, so these variants are not
promoted to production actor/writer versions.

## Runtime and verification

Pinned Qwen3-4B-Instruct-2507 revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, greedy CUDA FP16, generation seed 0,
context 8192, actor output cap 128 and writer/repair cap 1024. Actual GPU NVIDIA
A10; four CPUs, 32 GiB requested memory. Modal 1.6.4, Python 3.12.10, Torch
2.8.0/CUDA 12.8 and Transformers 4.57.6. One model load, fresh message input per
call, no retained conversation beyond the exact saved request. One container,
finite 600-second startup and 1800-second execution limits, no automatic retries,
and a durable marker committed before weights load.

The validated base image is `im-hcwu4yLdsDjSwc3tiBnYGv` (the previously passing
395-test gameplay image). Only the harness and its tests were layered onto it;
no production game modules, dependencies or policies changed. The existing
runtime's source digest is recorded in `source.json`; the new image and harness
hash are in the run reference. Two focused harness tests passed locally and in
the remote image; they check exact baseline preservation, unchanged user/repair
evidence, copy isolation and rejection of unknown variants. A local import-path
error was fixed before any GPU submission; the single diagnostic job then
completed successfully.

All 18 requests have matching responses. Request digests and baseline messages
were independently checked against the submitted plan; the current harness hash
matches the submitted hash. No generation hit its output cap. Usage totals:
**12,061 input tokens, 1,830 output tokens,
59.19 synchronized generation seconds**. Model loading
was 5.53 seconds; full remote worker time was 131.29 seconds.
Latencies are descriptive and include different token lengths/warmup; no speed
claim is made. The app stopped with zero GPU tasks.

## Interpretation and next experiment

These failures are reproducible on the saved inputs. Merely appending the three
reminders did not resolve them. This does not rule out prompting: existing
prompt structure, action-list ordering, copied notebook content and model
limitations remain possible contributors. The writer's recipe-recovery variant
changed formatting without retaining the missing recipe, illustrating why valid
syntax alone is an inadequate success measure.

The next diagnostic should replace the verbose system instruction with a short
explicit decision/update procedure and test input organization as a separate
factor. For the actor, a same-view public-history diagnostic could distinguish
memory representation from action selection; it must remain explicitly unbounded
diagnostic evidence. For the writer, separate prior claims from new public
feedback and require explicit confirmed-versus-planned status. Keep the original
inputs as controls and test one change at a time. More full episodes are not
justified by the failed reminder variants themselves. Any successful replay
change would still need new prompt versions and fresh gameplay validation.

Run reference: `artifacts/modal/replay-v1-f882d8fe7d57.json`.
Raw evidence: `artifacts/replay-downloads/replay-v1-f882d8fe7d57-9a00ec5e/replay-v1-f882d8fe7d57`.
Paired scores: `artifacts/replay-review/replay-v1-f882d8fe7d57/summary.json`.
Persistent volume: `memory-research-results/replay-v1-f882d8fe7d57`.
App: `ap-tFT16jOhsKGOl4odd5rxGY`.
Verified package: `artifacts/modal/saved-request-replay-v1-evidence.zip`, with
adjacent SHA-256. The package contains exact inputs/outputs, scores, source,
tests, runtime records and this report, excluding credentials, weights and
environments. It is local; raw evidence also persists remotely.
