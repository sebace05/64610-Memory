# Name and distractor ablation results — November 17, 2026

**Entity names materially affect the selected Q00 errors.** Renaming the queried
entity fixed all four Q00 worlds in both formats for both prespecified aliases.
Renaming `tuven` also helped, while renaming the matched green distractor `visuv`
did not. However, `tevug` and `tuven` already have different first tokens and no
shared name-token IDs. The result supports name-specific interference on these
inputs, not the proposed shared-first-token explanation or a validated generator
fix. No generator, writer, old package, training data or model weights were changed.

## What ran

Followed the [prespecified diagnostic](name-ablation-v1.md): four Q00 siblings
plus four previously correct Q01/Q02 worlds, prose and JSON, sixteen conditions
per world/format. Original prompts were verified against the saved qualification
evidence. All intervention comparisons use lexical record order matched across
formats; renames preserve record slots without re-sorting. Each note still
contains the true queried assignment, and options are fixed.

The **280 physical forwards** comprise 248 distinct primary prompts, 24 independent
baseline scoring checks, and eight focal baseline repeats after all interventions.
There are 256 logical primary cases and 296 logical assessments including checks
and exact-input reuse. No text generation, writer inference, fine-tuning, 8B run,
downloads, or held-out-family inference occurred.

## Q00 results

Each cell is correct out of four counterfactual siblings. Both aliases were fixed
before inference; no replacement was selected after looking at scores.

| Condition | Plain text | JSON |
|---|---:|---:|
| Exact original record order | 3/4 | 1/4 |
| Matched lexical baseline | 2/4 | 1/4 |
| Rename suspect `tuven` → `balok` | 3/4 | 4/4 |
| Rename suspect `tuven` → `zomip` | 4/4 | 3/4 |
| Rename query `tevug` → `balok` in note and question | 4/4 | 4/4 |
| Rename query `tevug` → `zomip` in note and question | 4/4 | 4/4 |
| Rename control `visuv` → `balok` | 2/4 | 1/4 |
| Rename control `visuv` → `zomip` | 2/4 | 1/4 |
| Swap whole `tuven` / `pisak` records | 4/4 | 3/4 |
| Swap whole `tuven` / `gitix` records | 4/4 | 2/4 |

The four selected control worlds remained 4/4 in each format for the original,
matched-order, and all six rename conditions. These are selected controls, not an
estimate of general task accuracy.

### Distractor values and destination-frequency controls

`tuven` and `visuv` both initially have value green. Changing either one to a
given new color therefore creates identical destination histograms. Query values,
names, options and record slots remain fixed.

| Changed record | New value | Plain text | JSON |
|---|---|---:|---:|
| `tuven` | amber | 4/4 | 3/4 |
| `tuven` | blue | 4/4 | 4/4 |
| `tuven` | violet | 3/4 | 2/4 |
| `visuv` | amber | 2/4 | 1/4 |
| `visuv` | blue | 2/4 | 1/4 |
| `visuv` | violet | 2/4 | 1/4 |

The matched control changes leave the baseline choices unchanged. Changes to
`tuven` substantially alter them. A simple destination-frequency explanation is
therefore insufficient for these cases.

The model does **not** always copy `tuven`'s destination. Across the nine JSON
value-change cases where the new distractor value differs from the true answer,
it selected that distractor value in 3/9 and answered correctly in 6/9. With the
equivalent `visuv` changes it selected the changed value in 0/9, kept choosing
green in 9/9, and was correct in 3/9. Plain text followed the changed suspect
value in 1/9 versus 0/9 for the matched control. Cases where distractor value
equals gold are excluded from this following statistic because correctness
cannot distinguish the explanations there.

### Actual tokenization

The cached checkpoint tokenizer produced these name pieces in the exact JSON
baseline prompt:

| Identifier | Note-key name pieces | Query occurrence |
|---|---|---|
| `tevug` | `te`, `v`, `ug` | space+`te`, `v`, `ug` |
| `tuven` | `tu`, `ven` | Not queried |

Their first tokens already differ, and the name-token IDs do not overlap. Thus
requiring different first tokens would not reject this demonstrated pair.
Token-ID overlap/edit distance alone is not established as a repair criterion.
We did not measure embedding similarity or inspect an internal attention circuit.

`balok` tokenizes as `bal`, `ok`; `zomip` as `z`, `om`, `ip`. Both query renames
work despite different token counts, so reducing the query to two tokens is not
necessary for the observed improvement. Full name/boundary snippets and exact
prompt offsets are retained in `name-tokens.json`; capitalized and leading-space
contexts can have different token pieces.

## Interpretation and next decision

The ablation adds evidence beyond the earlier order/option diagnostic: changing
specific identifiers or the suspect's value can repair the same reading task,
where equivalent control changes do not. Position also contributes. These are
behavioral effects on four related Q00 worlds; they do not establish a general
visual-similarity rule, a complete internal mechanism, or universal JSON weakness.
The original mistakes remain reader errors on correctly specified inputs.

Before committing to LoRA or rebuilding the dataset, validate a prespecified
clearer-identifier condition on fresh development families in both formats. Keep
the original condition as a reported difficulty comparison. Do not choose names
by repeatedly testing until Q00 passes, and do not use held-out results to tune
the name rule. The existing B=256 writer calibration is completed and remains
valid for its original protocol; any new generator is a separate version whose
writer outputs and sizes need checking. No such generator change is implemented
by this diagnostic.

## Integrity, runtime, and evidence

All 24 distinct production/reference checks had identical candidate logits and
labels: maximum absolute difference **0.0**. All eight end-of-run baseline repeats
also matched their initial logits exactly. Reference scoring shares the model,
tokenizer and numerical libraries; this checks independent scoring code.

This NVIDIA A10 run's original Q00 plain-text score is 3/4, versus 4/4 in the
earlier completed A10G diagnostic. The earlier failed A10 attempt already showed
the same amber-case discrepancy. We use the contemporaneous baseline for all
comparisons; within-run repeatability does not establish cross-hardware identity.

One cached FP16 Qwen3-4B-Instruct-2507 load took **5.061 s**. The diagnostic used
**92,573 input tokens** and **280 decision tokens**, with no generated output
tokens and no unknown-usage calls. Synchronized forward time was **17.489 s**;
diagnostic wall time **32.457 s** and worker wall time **35.194 s**, sampled before
the final outcome save/volume commit. These scopes exclude provider/image startup
and do not estimate billed cost. The App is
verified stopped with zero tasks. No retry or failed GPU attempt occurred here.

Offline verification: **577 passed, 26 skipped**, with the retained upstream
TextWorldExpress Java cleanup warning. This includes 18 new ablation tests. The
frozen transport separately passed 10 tests. Tests cover unchanged gold/options,
isolated interventions, matched color histograms, order-preserving renames,
historical prompt reconstruction, token offsets, physical-call reuse, incomplete
evidence, scoring disagreement, repeat instability and falsified reports.

Package digest:
`310ea7b1d0789cd00154aa6cd14f4e35a560517b1dfb40acce6ae26760df54e7`.
App: `ap-W5AtipWPo5RPgvUahYC2Z6`; call:
`fc-01M7PASCV1V47KTDQW1EZSQ1V4`.

The [evidence ZIP](../handoff/name-ablation-20261117-evidence.zip) preserves frozen
source/cases, manifests, raw requests/logits, assessments, actual tokenization,
counts/timing, stdout/stderr, collection audit, provider logs and shutdown proof.
Validate its adjacent SHA-256 and internal
`handoff/name-ablation-transfer-manifest.json` before restoring only `artifacts/`
entries, skipping identical files and stopping on conflicts. Never overlay source
or overwrite existing evidence.

After restoration, read-only reporting is:

```sh
.venv/bin/python -m game_memory.name_ablation report \
  artifacts/name-ablation-v1/modal-preparation-20261118T032101Z/collection-713s1ldn/download/ablation
```

Derived analysis and its script are in
`artifacts/name-ablation-v1/execution-20261118T032412Z/`. This attempt is completed;
do not relaunch its reserved identity.
