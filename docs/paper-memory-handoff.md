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

Next: follow the [experiment plan and copyable continuation
prompt](paper-memory-next-experiments.md). It starts with the P02 diagnostic and
a 20-paper baseline at a generous shared allowance. Length and tighter-budget
sweeps follow as separate experiments.
