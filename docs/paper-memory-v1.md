# Paper memory pilot v1

Frozen before Qwen predictions. This is a three-paper pipeline shakedown, with
nine literal-fact questions. It does not estimate a general format ranking or a
causal effect of document length. No fine-tuning runs in this pilot.

**Question:** after reading the same paper once in order, how accurately can the
stock reader answer objective questions from a prose notebook versus JSON?

## Inputs and conditions

The source is the [QASPER v0.3 training split](https://huggingface.co/datasets/allenai/qasper),
CC BY 4.0, from [Dasigi et al., 2021](https://aclanthology.org/2021.naacl-main.365/).
The curated text, attribution, questions, answer aliases and supporting paragraphs
are in `data/paper-memory-v1/papers.json`. The source train JSON SHA-256 is
`9458bfe76074a8fa8d1685af02bcc73537aa6d338ad20591dfaff1946bc88bf4`.

Select the first three training papers by sorted ID with 12,000–36,000 source
characters and at least three answerable, single-extractive-span, single-evidence
QASPER questions (span at most 100 characters and 15 words; literal body evidence).
This yields 1611.02550, 1701.08118 and 1707.06939. Clarify three factual questions
per paper before predictions. Codex checked each against the source; these are
agent-reviewed questions, not independently human-validated rewrites. This custom
pilot is **not** the original QASPER benchmark score. Dev/test splits are unused.
Use title, abstract and body paragraphs only. Tables, figures and missing formula
placeholders are not reconstructed; no selected question needs them.

Pack whole paragraphs in order into chunks of at most 6,000 characters. Keep a
single oversized paragraph intact, subject to the tokenizer context preflight.
Each writer receives only its previous notebook, the next chunk and the allowance.
It never receives the questions, gold answers, future text or hidden history.
The first chunk includes the title and abstract. Read each chunk exactly once per
format. There are no artificial filler rewrites.

The primary conditions are full paper, final prose notebook and final JSON
notebook. The full-paper reference has no notebook restriction. The notebook
reader sees only the final saved text and one question. Cheap diagnostic controls
are no context and the gold source paragraph. Every condition uses the same reader
prompt and questions. No-context abstention under an evidence-only instruction
does not establish that the model lacks pretrained knowledge.

## Fixed settings and limits

Stock `Qwen/Qwen3-4B-Instruct-2507`, revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, FP16, seed 0, greedy decoding,
actual **NVIDIA A10G**, configured context 16,384 tokens. Reuse the cached pinned
runtime. Check hardware, cached assets and actual tokenizer before loading weights.
Check every actual prompt plus its output reservation without truncation.

Both notebooks have **2,048 stored Qwen tokens**. All JSON keys, values and
punctuation count. Writer generation cap: 2,560 tokens; answer cap: 96 tokens.
Stored memory, generation caps, total model context and inference cost are distinct.
There is no additional monetary penalty or reread action in this task.

Reuse v17 syntax/size validation: one repair using the same evidence, then retain
the previous valid notebook if both candidates fail. Canonicalize valid JSON with
the existing exact-number, sorted-key renderer. Preserve rejected outputs, repairs,
fallbacks, length-ended generations and empty notes; all answers remain scored.
Paper-facing writer/reader prompts have separate `paper-memory-v1` versions.

One job per paper, one model load per job. For `n` chunks, at most **4n + 20 physical
generations**: two formats × n writes × at most two attempts, 15 primary answers,
and five exact-prompt repeats (first question per condition). No answer caching.
Startup ceiling 600 seconds, execution ceiling 1,800, soft deadline 1,500. Retries
are zero. Run P00 first to establish fit, accounting and runtime, then P01/P02 if
the technical audit passes. Accuracy does not gate continuation. Failed attempts
stay recorded and are never silently resubmitted. Commit raw traces after each
update/answer and completed chains before starting another unit. Stop every App.
Standing project GPU authorization covers this bounded pilot.

## Scoring and interpretation

Require a short answer or `INSUFFICIENT_INFORMATION`. Primary metric is normalized
exact match against **frozen** aliases. Normalize Unicode NFKC, case, whitespace,
an optional `Answer:` prefix, surrounding quotes, a terminal period and commas
between digits. Preserve signs, decimal points and percent symbols. Secondary
metric is maximum whitespace-token F1 over aliases. Empty, malformed, abstaining
and length-ended answers remain in the denominator. Do not add aliases after
seeing outputs. Report any manual semantic judgment separately.

Report all nine primary predictions per condition, accuracy by paper, repeat
stability, source/chunk/notebook/prompt tokens, repairs/fallbacks, generated tokens,
generation time and end-to-end time. Inspect every main-condition mismatch using
the source evidence and the exact final note. Distinguish omitted/contradicted
facts, reader mistakes on sufficient notes and grading/wording disagreements.
Annotate evidence location within the source and whether that paragraph was read.
Compare paired prose/JSON outcomes. Three papers are too few for a useful
population confidence interval; report raw counts and paper-level differences.

The full-paper condition is a reference, not an assumed upper bound. Evidence-only
answers check reader/scoring behavior. Results on different papers cannot isolate
length from content. After the shakedown, freeze a larger paper sample and matched
length/position variants before claiming a length effect or starting adaptation.

## Commands

Preparation and reporting are offline; running loads the cached GPU model:

```sh
.venv/bin/python -m game_memory.paper_memory prepare artifacts/paper-memory-v1/package
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_paper_memory.py
.venv/bin/python -m game_memory.paper_memory run PACKAGE NEW_OUTPUT --paper P00
.venv/bin/python -m game_memory.paper_memory report OUTPUT
```

For Modal use the frozen per-paper launcher packets recorded in the results
handoff. The CLI `run` is the science worker, not a local CPU fallback.
