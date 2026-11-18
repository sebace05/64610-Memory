# Paper-memory experiments: next-step handoff

Repository: `sebace05/64610-Memory`

Branch: `codex/long-context-paper-memory`

## Current checkpoint

Stock Qwen3-4B reads paper chunks, maintains a prose or JSON notebook, then answers
factual questions. Writers never see the questions. No fine-tuning has run.

The pilot scored **9/9 full paper, 5/9 prose, 6/9 JSON**. One JSON miss is
citation-only. Facts disappeared during rewrites, including from a 393-token
note with spare capacity. One task-label/reader ambiguity remains. Three papers
cannot establish a format winner.

We already imposed **2,048 stored tokens** and a **2,560-token generation cap**:
eight repairs and seven fallbacks occurred. Writing took about 45 minutes of
generation time across three papers; answering/repeats took about 29 seconds.

Read the [results and evidence](paper-memory-results-2026-11-18.md),
[frozen protocol](paper-memory-v1.md), and
[papers/questions](../data/paper-memory-v1/papers.json).
Code: `game_memory/paper_memory.py`; tests: `tests/test_paper_memory.py`.
All 94 generations are accounted for and all Apps are stopped.

## Why these initial papers

Before inference, we took the first three eligible QASPER training-paper IDs:
12,000–36,000 source characters and at least three short, body-supported extractive
answers. The final nine questions were agent-curated. This was a reproducible
development sample, not a representative benchmark or official QASPER score.

## Immediate setup

1. **P02 diagnostic:** reuse the saved JSON. Compare the original question, an
   explicit main AUI/Control question, and the original with a task-label
   clarification. Label added evidence. Repeat each once: six reader generations,
   no new writing. Preserve pilot scores.
2. **Scoring:** the new primary exact-match score should ignore standalone
   `BIBREF` citation markers, such as `(BIBREF31)`. Also report strict v1 exact
   match and raw answers. Freeze this rule before predictions.
3. **Setup:** use three fresh training-split papers. Start at 8,192 stored tokens;
   increase generation/context headroom together, including repairs. Profile one
   bounded GPU run. Finalize limits using fit, cost and truncation records before
   evaluation. Accuracy errors stay counted.

## Next main experiment: more papers at one generous allowance

| Setting | Proposal |
|---|---|
| Evaluation sample | 20 fresh QASPER development-split papers, disjoint from setup papers |
| Selection | Actual source length roughly 4k–8k Qwen tokens; seeded ordering, seed 0; record exclusions before inference |
| Questions | Nine paper-specific literal facts per paper, spread roughly evenly across early, middle and late sections |
| Labels | Source paragraph, exact supporting quote and accepted answers fixed before predictions |
| Model | Same frozen stock 4B checkpoint for writing and reading |
| Notebook allowance | One shared cap, initially 8,192 tokens, finalized on setup papers |
| Conditions | Full paper, prose, JSON; evidence-only and no-context controls |
| Writer behavior | Same instructions and chunking across formats; questions hidden |

Use study-specific facts; the pilot answered Google News vector dimensions without
context. Full-paper errors stay counted; perfect accuracy is not a qualification gate.

Report paired accuracy/uncertainty across **papers**, stored tokens, repairs,
fallbacks and time. Classify facts as never stored, stored then lost, retained but
misread, or label-ambiguous. A matching number alone does not establish support.

## Later experiments

**Length:** on longer papers, ask the same early-supported questions after roughly
4k, 8k and 16k tokens of reading at a fixed allowance. Reuse writer snapshots and
compare full-text prefixes. This measures retention as text arrives; update count
and compression pressure also grow. Check context/GPU fit first.

**Memory pressure:** fix papers, input length and questions; compare 1k, 2k, 4k and
8k stored tokens on a subset, reusing completed matching conditions. Plot accuracy
against storage. Consider fine-tuning later, based on the observed failure types.

## Copyable continuation prompt

> Work on `sebace05/64610-Memory`, branch `codex/long-context-paper-memory`.
> Read `docs/paper-memory-next-experiments.md`, the pilot results/protocol and
> `game_memory/paper_memory.py`. Scope this iteration to the immediate setup and
> the 20-paper generous-memory baseline described in the handoff.
>
> Implement the six-generation P02 reader diagnostic using the saved JSON note.
> Prepare three fresh training-split setup papers and 20 disjoint development-split
> evaluation papers, with nine verified paper-specific factual questions per
> evaluation paper. Freeze selection, evidence, aliases and citation handling
> before evaluation. Use the stock checkpoint and match papers/questions across
> full-paper, prose and JSON conditions, with the diagnostic controls retained.
>
> Start setup at an 8,192-token notebook allowance with adequate generation and
> context headroom. Run a bounded fit/profile check, then freeze one shared
> allowance and execution limits before the evaluation run. Count ordinary model
> errors. Keep questions hidden from writers and preserve intermediate notebooks so
> fact loss can be localized.
>
> Reuse existing code, version changed behavior and preserve the completed pilot.
> Use `.venv/bin/python`, run relevant offline tests, and retain raw prompts,
> responses, usage and shutdown records. Standing GPU authorization is in README;
> the pilot used explicit `gpu="A10G"`. Push the implementation and results, then
> update the short handoff with findings and the next experiment.
