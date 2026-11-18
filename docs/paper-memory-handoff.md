# Paper-reading handoff

Branch: `codex/long-context-paper-memory`.

Stock Qwen 4B reads paper chunks, keeps a prose or JSON notebook, then answers
factual questions. Writers never see the questions. No fine-tuning has run.

Completed: three papers, nine questions, 2,048-token notebooks. Strict scores:
**full paper 9/9, prose 5/9, JSON 6/9**. One JSON miss is citation-only. P01 prose
lost three stored facts despite spare capacity. P02 JSON retained 176 workers but
abstained on a task label missing from its note. The sample is too small to rank
formats.

Read the [results and evidence](paper-memory-results-2026-11-18.md) and
[frozen protocol](paper-memory-v1.md). Code: `game_memory/paper_memory.py`;
inputs: `data/paper-memory-v1/papers.json`. Offline: 641 passed, 26 skipped.
All 94 generations are accounted for; all Apps are stopped.

Use `.venv/bin/python`. Standing GPU authorization is in the README. Explicit
`gpu="A10G"` worked; generic `A10` sometimes allocated another device.

Suggested continuation prompt:

> Work on `codex/long-context-paper-memory`. Read the paper pilot results and
> protocol, then inspect the saved notes. Start with the small P02 JSON diagnostic:
> compare the original conceptualization question with an explicit main AUI/Control
> question and a supplied task-label mapping, keeping the notebook fixed. Then
> prepare a larger stock-model study with paper-specific facts across sections and
> a generous shared memory allowance chosen on development papers. Keep questions
> hidden from writers and match papers/questions across formats. Reuse the existing
> code, version new settings, test offline, and preserve raw results. Fine-tuning
> remains a later option.
