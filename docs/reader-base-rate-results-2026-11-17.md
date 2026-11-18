# Paired reader base-rate results — November 17, 2026

**The stock 4B reader makes roughly 2% errors with the current names on complete
notes. Numbered IDs improve prose in this sample but leave the JSON error count
unchanged. The prespecified naming decision is inconclusive.** Keep the current
generator. These results establish neither a general name-filter rule nor a need
to fine-tune before trying the stock reader on the saved writer notebooks.

We implemented and ran the [frozen base-rate study](reader-base-rate-v1.md): 160
fresh development families, four counterfactual siblings per family, two naming
arms, and both prose and JSON. Each of the four cells contains 640 questions.
Facts, options, queried role and record order are paired across arms and formats.
The alternative is one fixed, randomly assigned `item-####` scheme; it was not
selected by trying replacements against the model. Every note is a scripted,
complete correct state, including the revoked entity. These are sufficient-note
reader controls, not compressed or writer-produced memories.

| Naming arm | Format | Correct / 640 | Accuracy | Errors | Error-rate 95% interval |
|---|---|---:|---:|---:|---:|
| Current made-up names | Prose | 627 | 97.97% | 13 | 0.78–3.59% |
| Current made-up names | JSON | 629 | 98.28% | 11 | 0.63–2.97% |
| Numbered IDs | Prose | 637 | 99.53% | 3 | 0.00–1.09% |
| Numbered IDs | JSON | 629 | 98.28% | 11 | 0.78–2.81% |

Intervals use the frozen 10,000 paired family bootstrap resamples, stratified
80/80 by updated versus untouched query, seed 0. Siblings stay together; 640
questions are not treated as 640 independent families. Intervals are descriptive
development estimates. The zero lower endpoint for numbered prose does not imply
a zero population error rate.

**How widespread are the failures?**

| Naming arm / format | Families with any error / 160 | Fraction | Family-level Wilson 95% interval |
|---|---:|---:|---:|
| Current / prose | 10 | 6.25% | 3.43–11.12% |
| Current / JSON | 9 | 5.63% | 2.99–10.34% |
| Numbered / prose | 3 | 1.88% | 0.64–5.37% |
| Numbered / JSON | 10 | 6.25% | 3.43–11.12% |

With current names, 16/160 families have at least one error in either format.
The 11 JSON errors occur in nine families: seven have one wrong sibling and two
have two; none has three or four. The earlier Q00 failure was a useful diagnostic,
but its three wrong JSON siblings do not describe the typical fresh-family result.
This study measures all reader errors under this task distribution; it does not
identify every error as the same name-interference mechanism observed in Q00.

Updated-query errors out of 320 are current prose 6, current JSON 4, numbered
prose 1, numbered JSON 6. Untouched-query counts are respectively 7, 7, 2 and 5.
All ordinary wrong answers remain in the denominator, including the one erroneous
abstention. There were no missing model responses or unparseable answers under
the restricted A–E interface.

**What did changing the identifiers accomplish?**

Positive effects below mean lower error with numbered IDs. Units are absolute
percentage points, and comparisons pair the same family and world.

| Opaque minus numbered error rate | Estimate | Paired family 95% interval |
|---|---:|---:|
| Prose | +1.56 pp | +0.31 to +3.13 pp |
| JSON | 0.00 pp | −1.56 to +1.56 pp |
| Equal-weight mean across formats | +0.78 pp | −0.39 to +2.11 pp |

The prose comparison fixes 12 current-name errors and introduces two new ones;
one question is wrong in both arms. JSON fixes all 11 current-name errors and
introduces 11 different errors. Identical JSON totals therefore hide a change in
which inputs fail; they do not establish that names are irrelevant.

The frozen practical margin is 2 pp. The pooled interval does not establish an
improvement greater than 2 pp. It also extends outside the equivalence margin,
and the prose interval extends above it. Consequently the implemented rule returns
`inconclusive`, rather than practical similarity or a justified generator change.
Three of the four observed error rates exceed the separate 1% planning threshold.
No thresholds or cases changed after observing scores.

The current-name JSON-minus-prose accuracy gap is **+0.31 pp** (95% interval
−1.09 to +1.72 pp). There is no clear general JSON disadvantage in this fresh
sample. With numbered IDs, the gap is **−1.25 pp** (−2.50 to −0.16 pp). Format
behavior depends on the naming condition in this experiment; the earlier selected
Q00 results should not be promoted to a universal JSON weakness.

**Are these implementation failures or reader failures?**

The audit reconstructs every prompt, option mapping, gold destination and raw-logit
argmax. All **38 wrong answer instances** across the four cells have the queried
true assignment in the actual note. An additional evidence check reconstructs
each note and verifies the queried fact; the saved error list includes the exact
text. Four examples, chosen as the first error in each cell in family/world order,
were also inspected directly:

| Case | Fact explicitly in the note | Selected destination |
|---|---|---|
| `F031/1/opaque/prose` | `Kiles is assigned to blue.` | insufficient information |
| `F020/3/opaque/json` | `"falel":"violet"` | blue |
| `F012/2/numbered/prose` | `Item-8170 is assigned to green.` | blue |
| `F008/0/numbered/json` | `"item-7742":"amber"` | blue |

All 16 independent scoring checks agree exactly with their contemporaneous
production forwards, maximum candidate-logit difference **0.0**. All 16 repeat
checks also match exactly, and all 16 original-corpus replay labels agree.
This provides no evidence of a scorer/prompt-construction bug behind these
mistakes. They are reader errors under the specified restricted A–E interface.
The independent implementation shares the weights, tokenizer and numerical
libraries, and checks a fixed subset; it is not an independent model evaluation.
This run does not compare generated answers with restricted choices.

The earlier ablation still establishes that particular renames and distractor
changes can fix Q00. This larger study shows that one fixed replacement scheme
does not eliminate fresh reader errors or materially improve both formats under
the frozen criterion. It does not validate a token-distance or visual-similarity
filter. No generator, old split, historical package or model weights changed.

**Next research step.** Keep the current generator and assess the stock reader on
the already saved B=256 writer notebooks at P0/P12. Separate missing/contradictory
facts from failures to use supported facts, while retaining all errors in total
accuracy. That will show whether writer loss or residual reader error dominates
the actual memory comparison. Decide on reader LoRA from that evidence and its
available headroom; this naming study does not automatically trigger training.
The matched-training protocol remains available if adaptation is warranted.

This recommendation is a follow-up to the frozen `inconclusive` outcome, not an
additional completed experiment. No writer-note reader evaluation, LoRA, 8B run
or protocol regeneration occurred here. There are 152 distinct normalized role/
destination compositions across the 160 fresh families; repeated compositions
within this development split were permitted in advance. Names and compositions
are disjoint from prior splits. Claims apply to this sufficient-note synthetic
development distribution, not model-wide accuracy or long-term memory quality.

**Execution and verification.** One cached FP16
`Qwen/Qwen3-4B-Instruct-2507` load on an actual **NVIDIA A10**, revision
`cdbee75f17c01a7cc42f958dc650907174af0554`; Python 3.12.10, torch 2.8.0,
transformers 4.57.6. The device check ran before weights. Actual tokenizer
preflight covers all 2,560 prompts and three boundary contexts for each of the
2,560 distinct identifier strings. No weights or dependencies were downloaded.

There were **2,608 physical scoring forwards**: 2,560 primary, 16 contemporaneous
production checks, 16 independent reference checks and 16 repeats. All completed;
there were no retries, copied units, failures or unknown-usage calls. Recorded
usage is **899,747 input tokens** and **2,608 decision tokens**. No autoregressive
text generation occurred. The full prompt averages were current prose 338.05,
current JSON 320.01, numbered prose 370.00 and numbered JSON 351.92 tokens.
Numbered IDs cost about 32 extra prompt tokens in this task; stored-note allowance
was not measured or imposed here.

Measured synchronized forward time was **168.987 s**, the study wall time
**372.904 s**, and worker wall time **378.939 s**, including model loading,
tokenizer checks and durable family commits. Model loading alone was **5.895 s**.
The worker time is sampled before its final outcome save/commit; these timings
exclude provider/image startup and local collection and do not estimate billed
cost. The App is verified **stopped with zero tasks**.

Offline verification before inference: **599 passed, 26 skipped** in 32.69 s,
including 22 new base-rate tests; frozen transport tests: **10 passed**. Coverage
includes paired facts/order, split disjointness, device rejection before weights,
request ceilings, incomplete evidence, independently recomputed scores, family
uncertainty, fixed decisions and hash-pinned interrupted-run recovery. Relevant
optional local integration checks account for the existing skips. The complete
collection passed its audit and was independently re-audited locally; both reports
are identical. Source and scientific-package verification passed after the run.

Scientific manifest:
`383daaa7e0022a276f14775f5fac8b6ec4919838104a8161f96930a0703d8123`.
Frozen transport plan:
`1a2435509cebbd4e17ce9019a9d277a6b9e8df6cd17d6d8b7d2e2753a2a1c221`.
App: `ap-F8uftgFzkbLPUTY07J4Rtc`; call:
`fc-01M7PE7F60ANK8K165X1P660D7`.

The [evidence ZIP](../handoff/reader-base-rate-20261117-evidence.zip) preserves
the frozen inputs/source, raw prompts/logits, actual tokenizer evidence, per-family
completion hashes, full reports, derived analysis and error notes, provider logs,
accounting and shutdown verification. Validate its adjacent SHA-256, ZIP CRCs and
internal `handoff/reader-base-rate-transfer-manifest.json`. Restore only `artifacts/`
entries after full path/hash checks, skipping identical files and stopping on
conflicts. Never overwrite evidence or overlay archived source onto the checkout.

After restoration, read-only reporting is:

```sh
.venv/bin/python -m game_memory.reader_base_rate report \
  artifacts/reader-base-rate-v1/modal-preparation-20261118T042015Z/collection-4upfp5nq/download/study
```

Derived analysis and its script are in
`artifacts/reader-base-rate-v1/execution-20261118T043100Z/`. Its script uses exclusive
outputs; rerun a copy in a fresh directory to retain the original. The GPU attempt
is completed; do not relaunch its reserved identity.
