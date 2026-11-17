# GPU reader diagnostic results — November 17, 2026

**Completed:** revision 1.1 ran 312 model requests on an NVIDIA A10G, with one
cached Qwen load. All 104 production/reference scoring pairs had identical
candidate logits and selected labels. Raw evidence, accounting, collection, and
shutdown passed verification. No writer experiment or fine-tuning ran.

The user granted standing project GPU authorization on November 17. README records
it; repeated per-run GPU approval is not needed. Frozen settings, resource caps,
evidence retention, and shutdown still apply.

## Results and interpretation

These are eight selected development worlds from three qualification families,
not a representative or held-out sample. Every note contains all eight public
assignments, including the queried fact. Production and independent-reference
scoring agreed on every distinct prompt; counts below apply to both scorers.

| Input condition | Prose correct / 8 | JSON correct / 8 |
|---|---:|---:|
| Original historical entity/option orders | 8 | 5 |
| Matched lexical entity order | 6 | 5 |
| Matched reverse entity order | 7 | 7 |
| Lexical order, options rotated 1 position | 6 | 5 |
| Lexical order, options rotated 2 positions | 6 | 5 |
| Lexical order, options rotated 3 positions | 6 | 5 |
| Lexical order, options rotated 4 positions | 7 | 5 |

The focal Q00 JSON family reproduced the original pattern: the reader chose green
for all four siblings although the supplied target value varied across amber,
blue, green, and violet. When options rotated, green moved from D to C, B, A, and
E, and the chosen letter followed it. This contradicts a simple fixed-D strategy
on these cases; it does not identify the internal reason for choosing green.

Reversing entity order changed Q00 JSON from 1/4 to 3/4 correct without changing
the facts, query, or options. Prose was also sensitive to entity order. The
diagnostic establishes order sensitivity in these selected cases, not general
format superiority or information loss.

### Generated answers and the fixed parser

All **104 physical generations** were unparseable under the frozen rule accepting
only a bare uppercase A–E with an optional final period. Many responses instead
included a destination or explanation. Therefore the formal generated-answer
score was 0/8 in every cell. **That is a format-compliance result, not evidence of
zero semantic accuracy.** The parser was not relaxed after seeing the answers.

Examples from the original Q00 prompts:

| Supplied context / true destination | Actual generated answer | Interpretation |
|---|---|---|
| Prose / blue | `B. blue` | Semantically correct, rejected by the strict parser |
| JSON / blue | `D. green` | Semantically wrong as well as rejected by the parser |
| JSON / amber | `D. green` | Same wrong green answer as restricted scoring |

All four original Q00 JSON generations were `D. green`, including the three wrong
worlds. Thus those errors also appear in ordinary greedy text output and cannot
be explained solely by selecting the largest label logit. Other replies contained
longer explanations. Ninety-eight generations ended at EOS; six reached the
32-token cap. Every raw answer is preserved. No post-hoc semantic accuracy is
substituted for the prespecified metric.

### Recommended next interface

Retain restricted A–E scoring for the proposed matched reader-training comparison:
its mapping/argmax agrees with an independently implemented forward path, and
ordinary reading mistakes remain valid accuracy outcomes. Fine-tuning may improve
use of the supplied evidence; the stock reader is not required to pass the old
15/16 gate. If a future study uses generated answers, freeze an extraction rule
suited to its actual output format before held-out evaluation. Do not choose an
entity order merely because it repairs these inspected development cases.

## Execution and accounting

| Physical method | Calls | Actual input tokens | Accounted output tokens | Model seconds |
|---|---:|---:|---:|---:|
| Production restricted scoring | 104 | 34,406 | 104 decision tokens | 7.817 |
| Independent reference forward | 104 | 34,406 | 104 decision tokens | 7.355 |
| Greedy generation | 104 | 34,406 | 688 generated tokens | 32.140 |
| Total | 312 | 103,218 | 208 decision + 688 generated | 47.312 |

There are 112 logical prompts, 104 distinct prompts, and 336 logical assessments.
Twenty-four assessment rows reuse exact identical inputs within the same method.
Maximum absolute candidate-logit difference between scorers was **0.0**.
The independent path shares weights, tokenizer, and libraries; agreement does
not rule out every underlying numerical/library issue.

Adapter model-load time was 6.877 s. Diagnostic wall time, including preflight,
loading, calls, and local evidence writing, was 65.798 s. Worker time was 68.629 s,
sampled before its final outcome save/volume commit. Per-call model times exclude
tokenization/transfer/CPU selection or decoding as recorded by the adapters.
Image construction, provider startup, and final cleanup have different scopes;
these numbers are not added to estimate billed GPU cost. Cost was not measured.

Model: `Qwen/Qwen3-4B-Instruct-2507`, revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, cached-only FP16, context 8192,
generation seed 0, greedy generation capped at 32. Existing cache mounted
read-only; no model/dependency downloads or installations occurred.

## First attempt and integration correction

The first attempt used package `d43e0e8f…`, loaded Qwen on A10, and completed two
agreeing scoring forwards. Its third request failed before generation because the
diagnostic passed `reader_diagnostic_generation` to a backend that accepts only
action/memory purposes. Child exit status was 1. It consumed 678 input tokens,
two decision tokens, and 0.447 s of known forward time; no generation or writer
call occurred. Its App was verified stopped with zero tasks.

Revision 1.1 changes the caller to the existing `action` generation purpose,
retains the 32-token configured cap, and adds an offline regression through the
actual backend's purpose-validation branch. The first attempt and its immutable
package remain preserved. The corrected attempt has a fresh version, manifest,
reservation, App, and output directory. Cases and model-facing messages are
byte-identical between packages; this was an integration fix, not prompt tuning.

The failed A10 attempt selected D on a prose prompt previously answered E on
A10G, with identical message bytes, rendered-prompt hash, and label IDs. The top
scores were close; the completed A10G run reproduced E. Hardware/run-associated
numerical variation is observed, but its cause was not isolated. No repeatability
or controlled hardware study is claimed.

Full offline checks after the fix: **519 passed, 26 skipped, one retained upstream
TextWorldExpress cleanup warning**, exit 0. Optional local model checks remain
skipped where torch is absent. The transport checks separately passed 56 tests.
The completed GPU run supplies real evidence for the paths it exercised, not
retroactive passes for every skipped test.

## Evidence and reproducibility

| Record | Location |
|---|---|
| Corrected scientific package | `artifacts/reader-diagnostic-v1.1/package/` |
| Corrected manifest digest | `123ec062cb91c4b6d6a653c37249c7c13922c101a8069fb6a0a118c387dd30a4` |
| Corrected transport / collection | `artifacts/reader-diagnostic-v1.1/modal-preparation-20261117T222632Z/` |
| Downloaded results | `collection-nidp6qru/download/diagnostic/` inside that transport packet |
| Authorization, exits, independent audit | `artifacts/reader-diagnostic-v1.1/execution-20261117T222632Z/` |
| Failed attempt | `artifacts/reader-diagnostic-v1/execution-20261117T221700Z/` |
| Successful App / call | `ap-YFJ4wS9tG4zwoPm2WCbZJ9` / `fc-01M7NT2PCEDH81BQYQ6VSC881R` |

**Both diagnostic Apps were verified stopped with zero tasks.** Original v1/S1
evidence, failed attempts, and frozen packages were preserved. The independent
offline audit verifies hashes, all 336 assessment identities, actual raw logits,
selected labels/destinations, facts in supplied notes, strict generated parsing,
usage, and all scorer pairs without importing model libraries.

Raw `artifacts/` files remain Git-ignored. The selected source/evidence packets
are preserved in [the diagnostic evidence archive](../handoff/reader-diagnostic-20261117-evidence.zip),
with an adjacent SHA-256 and an internal per-file manifest. Follow
[handoff restoration instructions](../handoff/README.md) before following raw paths.
They also include the prior memory-probe-v1 evidence needed to check historical
prompt provenance. Full CookingWorld evidence remains in its existing archives.
