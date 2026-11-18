# Paired reader base-rate study v1

Frozen before inference. The question is how often the stock 4B reader fails on
sufficient notes under the current naming distribution, and whether one fixed
alternative naming scheme materially changes that error rate. Standing GPU
authorization is recorded in README. This checkpoint does not change any old
generator, writer, split, result, or prompt version.

## Data and arms

Use namespace `reader-base-rate-v1`, global seed 0, SHA-256-derived purpose streams,
and **160** fresh development families F000–F159. Reuse the existing eight-entity,
four-destination family constructor with explicit RNGs. There are 80 updated-query
and 80 untouched-query families; updated queries balance their old destinations.
Each family has four counterfactual worlds covering all true destinations.

Exclude earlier entity/pulse names, the diagnostic aliases, and normalized family
compositions from both the original v1 and matched-reader splits. Inspect held-out
structure only through software disjointness checks; do not print held-out facts
or infer on them. Repeated normalized compositions within this development split
are allowed, as in the original v1 construction. No family is selected based on
model success/failure. The package records all generated observations and mappings.

Two arms are fixed:

- `opaque`: the existing five-letter made-up names.
- `numbered`: `item-####`, sampled globally without replacement from item-1000
  through item-9999 using its own deterministic stream; 1,280 distinct IDs. Map
  eight IDs bijectively to each family's eight entities before inference. The
  mapping stays fixed across that family's worlds and formats. Do not search for
  favorable names, impose a token-distance rule, or try another alternative.

Render the **complete correct latest state**, including the revoked/unknown
entity, as scripted prose sentences and compact JSON. Preserve each family's
original randomly shuffled record slots across both naming arms and both formats;
do not re-sort JSON keys or renamed identifiers. Facts, query role, option mapping,
and public rules remain identical. Numbered prose capitalization follows the
existing renderer. Record counts, names, actual tokenizations and prompt hashes.
These are unbounded sufficient-note controls, not writer-produced or compressed
notebooks. This stage does not measure writer accuracy or memory drift.

There are **640 questions per arm/format cell**, four cells, or **2,560 primary
forwards**. Every ordinary error/abstention remains in its denominator. Use the
unchanged restricted A–E answer interface and prefix-stable token validation.

## Integrity and execution

Pin `Qwen/Qwen3-4B-Instruct-2507` revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, FP16, seed 0, context 8192, and the
existing cached Python/torch/transformers runtime. Require the actual device name
**NVIDIA A10**, rejecting A10G or another device **before weights**. No downloads,
8B, writer calls, generated answers, or fine-tuning occur. CPU preparation/reporting
imports no optional inference libraries.

After all primary cases, use F000/F001/F080/F081 world 0 in each naming/format
cell as sixteen fixed sentinels. For each, run a new production forward and an
independently implemented reference forward sharing the frozen weights/tokenizer;
stop on disagreement. Then repeat all sixteen production checks. Record repeat
and original-corpus replay differences as observations, without an accuracy gate.
That adds **48** calls, for a hard ceiling of **2,608** physical forwards.

One cached stock weight load per attempt, one requested A10, startup ceiling 600 s,
execution ceiling 1800 s, soft deadline 1500 s, zero configured scientific retries.
Each completed family's raw request/response/assessment unit is fsynced, hashed,
and committed before another family begins. All attempts use exclusive directories.

After an infrastructure interruption, preserve the failed attempt and never
resubmit its reserved identity. A fresh attempt may explicitly copy completed
family units pinned by completion hash from the **identical scientific package**.
Re-audit those units before weights and verify matching runtime/model configuration.
Copy bytes without alteration; incomplete units are retained unused. Generate
only missing whole families. Recompute the 48 integrity forwards contemporaneously
on the new worker, comparing the reference to its new production checks, and
report original-corpus replay differences separately. Reduce the new-call ceiling
by sixteen per copied family and distinguish reused from new GPU requests.

## Estimands and uncertainty

Report for each of the four arm/format cells:

- Correct/error counts and question-level accuracy/error rate.
- Number and fraction of families with any error among their four siblings, with
  a two-sided 95% Wilson interval at the family level.
- Query-type breakdown and individual family error counts, permitting inspection
  of concentrated failures rather than assuming independent sibling questions.

Primary effect: **opaque minus numbered error rate**, averaged equally across
formats. Positive values favor numbered IDs. Also report each format's paired
effect and each arm's JSON-minus-prose accuracy gap.

Use 10,000 paired family bootstrap resamples, seed 0, independently sampling 80
updated and 80 untouched families with replacement. Preserve all siblings, arms
and formats together. Reuse the existing bootstrap endpoint convention, ordered
samples 249 and 9749 (zero-based), as an approximate 95% descriptive interval.
Do not treat the 640 questions as independent observations. Degenerate bootstrap
intervals do not prove zero population error or practical equivalence; retain
affected-family Wilson intervals and flag degeneracy explicitly.

## Prespecified planning rules

The practical margin is **2 absolute percentage points**, an operational project
choice to avoid redesigning the task for a tiny observed change, not a universal
definition of significance. Apply these rules in order; no rule drops cases or
turns a complete study into a failed qualification gate:

1. If all four observed cell error rates are at most **1%**, report little observed
   adaptation headroom and prioritize stock-reader evaluation on actual writer
   notes. This does not prove the true population rates are below 1%.
2. If the pooled paired 95% interval lies wholly above +2 pp and neither format's
   point estimate declines, numbered IDs are a **candidate** new protocol. Check
   writer outputs/sizes for that version and assess residual reader errors before
   deciding on LoRA. No automatic generator change or training follows this study.
3. If the pooled interval lies wholly below −2 pp, reject this numbered-ID
   alternative and retain the current generator. Assess residual errors under
   the current names before deciding on LoRA.
4. If pooled and both format-specific intervals lie wholly within −2 to +2 pp,
   and all three effect intervals are nondegenerate, report practical similarity
   under this margin; keep the generator and consider LoRA if residual reader
   errors remain meaningful.
5. Otherwise report an inconclusive naming comparison. Keep the frozen generator
   pending stronger evidence. Similar point estimates alone do not establish
   equivalence, and inconclusive naming evidence does not automatically justify
   fine-tuning.

All rules and intervals are development planning aids for this synthetic task,
not confirmatory claims about every kind of identifier or general model accuracy.
Writer name corruption is a separate outcome. Evidence-based labels identify
unsupported facts; they do not repair missing information.

```sh
.venv/bin/python -m game_memory.reader_base_rate prepare \
  --output-dir artifacts/reader-base-rate-v1/package
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_reader_base_rate.py
```

The frozen Modal packet supplies the verified cached runtime, actual device check,
per-family volume commits, and submission reservation. Read-only reporting:
`.venv/bin/python -m game_memory.reader_base_rate report RUN`. Keep redirected
stdout outside RUN. Partial evidence yields no final rates or decision.
