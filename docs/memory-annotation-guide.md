# Offline memory annotation

These checklists are diagnostic evidence only. They never enter writer/actor inputs,
validate a live write, or select an action. The preserved v16 examples illustrate
annotation; they cannot be pooled into the v17 comparison.

Use the public reset observation, executed actions and their exact observations
up to the memory checkpoint. Cite event `sequence` IDs (zero based) and exact
supporting quotes. Do not read hidden simulator state, score, scripted solutions,
or later observations to judge what was knowable at the checkpoint. A negative
claim about an unexecuted action needs the complete preceding action ledger.

Before inspecting memory, list required recipe facts and known inventory/progress
facts for that checkpoint. Inspect reset, after taking, after preparation, and
immediately before meal preparation or a terminal mistake. Record an unreached
checkpoint explicitly; do not create a post-terminal memory. Seeds 0/1 in
`tests/fixtures/memory_annotations/development-seeds.json` reference real preserved
public events; seed 1 terminates on its first preparation attempt.

For each required fact label supported, omission, contradiction, or unknown.
Separately enumerate inspectable memory claims: supported, contradiction (opposed
to evidence or another explicit memory claim), invented (asserted without public
support), or unknown (ambiguous meaning or insufficient evidence). Model-managed
JSON keys have no guaranteed schema: a boolean ingredient flag may mean seen,
collected, or required. Do not infer a schema to manufacture a contradiction.
A direction marked false may still retain the required recipe method.

Report supported required facts / all required facts as retention, with unknowns
shown separately and retained in the denominator. Report incorrect claims against
inspectable claims separately. Empty memory has zero retention and no measurable
claim accuracy; it never earns perfect retention. Example assessments cover empty,
correct, contradictory and ambiguous notes. These labels require human judgment;
the summary function counts supplied labels and does not infer cooking facts.

Run `python -m game_memory.analyze_memory_budget ROOT --format json` (using the
project `.venv/bin/python`) against a separately declared comparison manifest.
The JSON contains detailed provenance and candidate measurements; CSV/Markdown
provide the episode table and serialize the detailed evidence. No tokenizer is
loaded: recorded stored counts and explicit size-rejection counts are the only
rendered sizes. Raw generation output counts remain separate; invalid JSON has
no canonical rendered size. Format adherence only flags obvious JSON-shaped prose
and parsed JSON objects; other prose cases remain unknown pending inspection.
Missing legacy provenance, loading times and launcher statuses stay unknown.
