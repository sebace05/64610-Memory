# Stock Qwen on model-written memory — November 18, 2026

**The stock-reader baseline is complete: plain text scored 87.5% and JSON 93.75%
at both P0 and P12. All six wrong answer instances had the correct queried fact
in the note, and all errors occurred in one family.** This is a small development
result, not evidence that JSON generally wins. No fine-tuning or RL ran.

We evaluated all 64 saved C00–C03 writer snapshots at B=256, using the literal
reader prompts exported by the completed writer calibration. Each family has
four counterfactual worlds. P0 follows the update/revocation; P12 follows twelve
no-change rewrites. The writer stayed frozen, and no notebook was regenerated.
The [v1.1 protocol](stock-memory-eval-v1.1.md) amends the
[original protocol](stock-memory-eval-v1.md) only to pin actual A10G hardware
before any predictions were generated.

| Model-written memory | P0 task accuracy | P12 task accuracy |
|---|---:|---:|
| Plain text (`prose`) | 14/16 — 87.5% | 14/16 — 87.5% |
| JSON | 15/16 — 93.75% | 15/16 — 93.75% |

The JSON-minus-plain-text gap is +6.25 percentage points at each checkpoint,
equivalent to one additional correct world out of sixteen. Family counts below
are identical at P0 and P12:

| Family | Plain text | JSON |
|---|---:|---:|
| C00 | 4/4 | 4/4 |
| C01 | 2/4 | 3/4 |
| C02 | 4/4 | 4/4 |
| C03 | 4/4 | 4/4 |

These are four budget-calibration families. Siblings and repeated probes share
facts/names; they are not independent replications. We report counts and family
results descriptively. There is no stock-accuracy qualification gate.

**Evidence review and failures.** Before reader inference, all 64 notes were
reviewed using their text and public rules. Separate annotations preserve each
query, notebook hash, supported destination, exact quote and rationale. Original
exports remain unchanged. All queried bindings were explicit, unambiguous and
correct, so evidence agreement equals task accuracy in every cell. No queried
fact was missing at either checkpoint. Other entities still have spelling,
omission and conflicting-record errors, as documented in the writer report.

Every wrong response concerns `dopum` in C01:

| Memory / world | Explicit queried fact | P0 answer | P12 answer |
|---|---|---|---|
| Plain text / 1 | `dopum=blue` | amber | amber |
| Plain text / 3 | `dopum=violet` | amber | amber |
| JSON / 1 | `"dopum":"blue"` | insufficient information | amber |

This accounts for six wrong answer instances across three chains and four
distinct erroneous prompts. The erroneous abstention counts as a task failure.
The JSON note in world 1 changes other fields between P0 and P12; its queried
assignment stays blue. All failures were inspected against the saved text and
raw scores. They are failures to use correct supplied query evidence under the
restricted A–E interface. This does not identify a unique internal mechanism or
rule out effects of unrelated writer defects and organization on the reader.

There were **no correct-to-wrong or wrong-to-correct transitions** between P0 and
P12 in either format. Two notes per format changed bytes; 28 of 32 chains retained
identical text. All snapshots were scored separately, including repeated inputs.
The JSON world-1 error changes from abstention to amber, so unchanged accuracy
does not mean all selected answers are unchanged.

**What this establishes.** We now have stock performance on actual model-written
memories, including ordinary reader mistakes in total accuracy. For the evaluated
queries, missing facts do not explain the failures, and the errors already occur
at P0. We observed no further queried-fact loss or accuracy decline over twelve
rewrites. This does not establish that every entity's fact was preserved or that
rewriting is generally harmless.

The notes called `prose` are compact assignment lists; JSON uses writer-chosen
nested schemas and metadata. This compares those actual memory outputs, not pure
syntax with identical organization. B=256 is roomy: the largest stored note is
183 tokens. This is not a memory-capacity boundary test. The earlier 160-family
scripted-note study used different families, notes and actual A10 hardware;
differences from its roughly 98% scores cannot be attributed to writer quality
alone. This run uses forced A–E choice scoring, not generated-answer evaluation.

The result makes a reader-only supervised LoRA experiment reasonable, with
uncertainty about how often the C01 behavior recurs. The next implementation
step is the existing protocol's R/V writer collection and evidence labeling,
with a stock validation baseline before adaptation. Keep C as development,
leave E held out, and give stock/adapted readers identical notebooks on actual
A10G. Do not fine-tune on the selected C01 failures alone. Training remains future
work; [the matched protocol](matched-reader-training-v1.md) specifies supervised
next-label training with LoRA, rather than an RL training loop.

**Scoring integrity and runtime.** The successful run used one cached FP16
`Qwen/Qwen3-4B-Instruct-2507` load, revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, actual **NVIDIA A10G**, seed 0,
context 8192, Python 3.12.10, torch 2.8.0/CUDA 12.8 and transformers 4.57.6.
The worker ran on AWS in `us-east`. No models or dependencies were downloaded.

There were **192 physical forwards**: 64 primary, 64 independent reference and
64 production repeats, covering 36 distinct prompt strings. All 64 independent
checks matched candidate logits exactly, maximum difference **0.0**. All 64
repeats matched labels and logits exactly. Reporting reconstructs prompts,
token IDs, option mapping and raw-logit argmax for every response. The independent
scorer shares weights, tokenizer and numerical libraries with the production
scorer. No scoring discrepancy was found in these exercised paths.

New reader usage was **64,113 input tokens** and **192 decision tokens**, with
zero unknown-usage requests and no autoregressive generation. Synchronized forward
time was **14.027 s**, study wall time **40.456 s**, and worker wall time
**44.405 s**. Model loading took **8.682 s**. Worker time is sampled before its
final outcome save/commit; it excludes provider/image startup and local collection.
These are measured scopes, not total project elapsed time or billed-cost estimates.
Earlier writer calls copied as provenance are excluded from new reader usage.

**Setup attempts were preserved.** Two default A10 placements supplied A10G;
v1 rejected them before tokenizer/weights, with zero model calls. A third,
OCI-pinned placement was rejected during Function creation and submitted no
input. V1.1 then fixed A10G before any reader prediction. All notes, annotations
and 192-forward ceiling stayed unchanged. Across all four attempts there was
exactly one model load and 192 model calls. Original failing exits are retained;
all four Apps are verified stopped with zero tasks. Modal's SDK exposes
[cloud selection](https://modal.com/docs/sdk/py/latest/App), but the service
rejected the attempted OCI pin; that failure is not a model result.

Final offline verification: **620 passed, 26 skipped**, with one existing upstream
TextWorldExpress Java cleanup warning, in 36.70 s. This includes 21 new evaluation
tests. The successful transport passed 10 tests; the rejected OCI transport also
has two additional placement tests. Tests cover unchanged exports, evidence-label
coverage, task versus evidence scoring, ordinary low accuracy, interruption,
independent disagreement, repeat instability, fake-data exclusion, pre-weight
device rejection, and rehashed falsified evidence. Optional local torch/cache
and Java integration checks account for the retained skips. Actual GPU traces
provide tokenizer/forward evidence for this run.

The collection was audited and independently re-audited locally. Worker,
collector and local reports are identical; all 79 downloaded files were rehashed.
Frozen source and earlier base-rate source verification passed after execution.

Successful scientific manifest:
`caa5c04ce91c1495fee3c2d0dc760c2477695d9927f69380f1d0f1f77ed44aa7`.
Transport plan:
`bdb873d1f9dcd74685d2e37e8784a2e5ac56b73b13ddd0226f70ea029c492616`.
Pre-inference source commit: `a53c33e`.
App: `ap-cg9c1WllyEYfOjMBA0yldN`; call:
`fc-01M7QN600CANV4VF51RNP026VJ`.

The [evidence ZIP](../handoff/stock-memory-eval-20261118-evidence.zip) includes
both protocol versions, separate pre-prediction annotations, literal writer
inputs/provenance, raw reader requests/logits, checks/repeats, all failed setup
attempts, test logs, reports, error review, timing/accounting and shutdown proof.
Verify its adjacent SHA-256 and internal
`handoff/stock-memory-eval-transfer-manifest.json` before restoring only `artifacts/`
entries, preserving existing files. The source/docs in Git remain authoritative.

After restoration, read-only reporting is:

```sh
.venv/bin/python -m game_memory.stock_memory_eval report \
  artifacts/stock-memory-eval-v1.1/modal-preparation-20261118T154145Z/collection-vydkp4vd/download/evaluation
```

Derived analysis, the six full wrong-answer records, manual error review and
verification are in `artifacts/stock-memory-eval-v1.1/execution-20261118T154249Z/`.
Completed attempt identities must not be relaunched.
