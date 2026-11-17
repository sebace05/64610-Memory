# Proposal: memory schemes before and after reader fine-tuning

November 17, 2026. **Proposed for team review; not an execution protocol.**
The implementation and progress handoff are checkpointed in `4a847e1` on
`codex/modal-calibration-handoff`. This proposal adds no training code, changes no
model-facing prompts, and authorizes no training or real inference. The frozen
memory-probe-v1 run remains an ended experiment with a failed qualification gate.

## Current progress and observed failure

We have implemented the controlled assignment task, bounded prose/JSON writers,
restricted-choice reader, evidence audits, and Modal execution/collection path.
One authorized S1 run completed tokenizer preflight and reader qualification:

| Reader context | Result across 16 sibling worlds |
|---|---:|
| Full public history | 15 correct |
| Scripted sufficient prose | 16 correct |
| Scripted sufficient JSON | 13 correct |
| Missing-fact prose | 16 correct abstentions |
| Missing-fact JSON | 16 correct abstentions |
| No memory | 0 factual answers correct; 16 abstentions |

All three sufficient-JSON errors came from one counterfactual family. The reader
chose green in all four siblings while the queried assignment changed across the
four destinations. The failed notes contained the correct fact and occupied only
47–48 tokens. There were no writer calls or compression in this run. The frozen
15/16-per-context gate stopped v1 before its writer/budget pilot; no memory-format
comparison, low-budget selection, fine-tuning, or S2 occurred.

The audited evidence shows that correct facts reached the reader and that the
selected labels matched the actual model-forward candidate logits and option
mapping. We have identified no implementation bug causing these errors. This is
a failure of Qwen under our particular prompt and answer-selection interface;
the internal cause and behavior under other interfaces remain unknown. Auditing
recorded decisions does not independently validate every numerical model-forward
operation or rule out every software error.

See the [implementation and verification handoff](implementation-status-handoff-2026-11-17.md)
for the complete progress record, saved test results, accounting, and evidence
paths. Raw `artifacts/` files remain Git-ignored and are not supplied by a fresh
clone. The [v1 specification](memory-probe-v1.md) preserves the original rules.

## Research question and interpretation

**Does task-specific reader fine-tuning change the effectiveness of model-written
prose and JSON memory on delayed factual questions?**

The off-the-shelf checkpoint is `Qwen/Qwen3-4B-Instruct-2507`, revision
`cdbee75f17c01a7cc42f958dc650907174af0554`. It is already instruction-tuned;
"without fine-tuning" here means without additional project-specific training.

Ordinary model mistakes count against end-to-end accuracy in both reader
conditions. A stock reader does not need near-perfect accuracy to be evaluated.
If prose makes correctly retained information easier to use, that benefit is part
of the memory system's performance. Conversely, a wrong answer with a correct
notebook is a system failure but does not establish that the fact was forgotten.

This broadens the question relative to v1. The v1 qualification threshold was a
prerequisite for its planned retention comparison, not a universal requirement
for measuring memory-system accuracy. A future protocol can retain reader
competence measurements as diagnostics rather than using their accuracy to
exclude the stock-model condition. Technical failures, corrupted evidence,
incorrect scoring, and information leakage still invalidate affected comparisons;
they must be reported separately from ordinary wrong predictions.

## Matched experiment

Start with two reader configurations and three primary context conditions:

| Reader configuration | Full public history | Model-written prose | Model-written JSON |
|---|---|---|---|
| Off-the-shelf, no task-specific training | Evaluate | Evaluate | Evaluate |
| Task-fine-tuned reader | Evaluate | Evaluate | Evaluate |

Use the same held-out families, public observations, queries, option orders,
storage allowances, and probe positions for matched comparisons. Full history is
exempt from the stored-memory allowance and remains subject to the complete
context limit; it is a reference condition, not a guaranteed upper bound.

Initially fine-tune **only the reader**. Keep the original writer checkpoint,
writer instructions, syntax/size policy, repair opportunity, and fallback fixed.
Generate each bounded-memory chain once per family/world/format/allowance, then
give its identical snapshots to both readers. This isolates the reader-training
comparison without paying for duplicate writer chains.

Fine-tuning both writer and reader is a valid later whole-system comparison, but
would change two roles together. Improvements could then reflect better writing,
better reading, or their interaction. It should be explicitly labeled and should
not be interpreted as evidence for reader adaptation alone.

Retain the controlled task's information boundaries: writers never receive the
future query, options, gold answer, hidden state, or full transcript; bounded
readers receive only their supplied notebook and public query context. All
persistent factual content and plans share the declared memory allowance. Reader
answers do not feed back into the writer chain.

## Controls and analysis

Evaluate both readers with no memory and with equivalent scripted sufficient
prose/JSON notes, including absent and revoked assignments. Scripted notes remain
diagnostic controls and never replace generated primary memories.

Retain P0 immediately after the real update and P12 after twelve no-change
rewrites. The unchanged P0 notebook supplies the carry-forward comparison at P12;
reuse its reader result only when the complete input and reader identity match.
Results must never be reused between stock and fine-tuned readers. This measures
the configured rewrite process, not elapsed-time decay or general agent behavior.

Report absolute accuracy for every reader/context/allowance/probe cell. At a fixed
allowance and probe, compare the JSON-minus-prose accuracy gap between readers:

```text
training-by-format interaction =
    (accuracy[fine-tuned, JSON] - accuracy[fine-tuned, prose])
  - (accuracy[stock, JSON]      - accuracy[stock, prose])
```

Also report each memory condition relative to full history and no memory,
abstention, syntax/size repairs and fallbacks, rendered sizes, measured tokens,
generation/forward time, end-to-end time, and training cost separately. Do not
subtract full-history error from memory error and call the remainder pure
forgetting, or evaluate only cases where one reader was already correct.

Inspect a predefined sample of actual generated notebooks against public facts.
Distinguish omitted, stale, incorrect, or unresolved facts from supported facts
that a reader fails to use. End-to-end accuracy alone cannot make that distinction,
and success on scripted flat JSON does not establish competence with every
model-chosen JSON schema.

Families are the independent experimental units; the four sibling worlds provide
controlled contrasts within each family. Preserve paired comparisons and query
strata when computing uncertainty. Eight families, as in v1, would support an
exploratory result with limited precision; many bootstrap resamples do not create
more independent evidence.

## Checks and decisions before implementation or execution

1. **Check the answer interface before training.** Compare the exact failed
   prompts with an independent reference implementation of next-token scoring,
   and perform a bounded generated-answer diagnostic. Freeze its cases,
   extraction rules, call ceiling, and interpretation before execution. Our
   current scorer ranks A–E at the next token; that behavior need not match a
   normally generated answer. Published work documents this distinction in
   instruction-tuned models, but does not establish the cause of our Qwen errors:
   [Wang et al., ACL Findings 2024](https://aclanthology.org/2024.findings-acl.441/).
2. **Freeze training, validation, and test families before training.** Keep
   sibling worlds together, separate names and normalized compositions across
   splits, and balance training exposure to history, prose, JSON, updates,
   revocations, missing facts, and option positions. Select checkpoints and
   prompts using training/validation data only. Observed Q0 cases are development
   evidence, not a fresh test of the revised design.
3. **Specify the adaptation procedure.** Freeze training targets, data source and
   size, method, hyperparameters, seed(s), checkpoint-selection rule, and resource
   ceilings. Teaching general task/interface behavior is different from exposing
   held-out episode assignments. These choices are unresolved; this proposal does
   not select a training framework or claim that adaptation will succeed.
4. **Establish the intended storage intervention.** Saved tokenizer preflight
   measured complete scripted JSON notes at 45–49 tokens and prose at 62–67.
   Every JSON note fits 64; both formats fit 128. These are feasible complete
   encodings, not measurements of generated writers or optimal compression.
   Inspect development writer behavior and select common allowances using a
   predefined rule that does not require a particular format to win. Decide
   whether to add a budget interaction or hold storage roomy and focus on
   rewrite robustness within the reader-training comparison.
5. **Freeze the new protocol and analysis.** Specify family counts, primary
   contrast, annotation sampling, all reader/writer identities and prompts,
   integrity checks, technical-failure handling, and stopping rules. Do not drop
   low-accuracy stock-model cases or tune repeatedly on the held-out comparison.
   Preserve the v1 gate failure and historical packages unchanged.
6. **Authorize bounded execution separately.** Training, model downloads,
   interface diagnostics, writer pilots, and final evaluations require their
   concrete settings and separate execution authorization. Publishing this
   proposal does not launch any of them.

The next implementation should reuse the existing generator, bounded writers,
model adapter, and inference ledger where they fit. Add only what the chosen
training comparison and the demonstrated scoring uncertainty require.
