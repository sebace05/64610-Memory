# Name and distractor ablation v1

This exploratory diagnostic tests whether Q00's `tevug` reading errors depend on
the name `tuven`, its assigned value, or record position. It changes no family
generator, writer, training data, old protocol, or frozen package. Standing GPU
authorization is recorded in README. No 8B inference or fine-tuning is included.

Use the four Q00 siblings and the same four previously correct controls as reader
diagnostic v1.1: Q01 worlds 0/1 and Q02 worlds 2/3. Prepare with the original
qualification evidence to verify the original prompts byte-for-byte; a clean
checkout can reconstruct inputs, explicitly marked unverified historical replay.

For each world and format, freeze these 16 conditions before inference:

1. Exact original prompt and a baseline with lexical entity order matched across
   prose/JSON. Original JSON already has that order.
2. Rename the suspected distractor, queried entity, or matched control distractor
   to each of two prespecified aliases, `balok` and `zomip`: six conditions. Preserve
   record slots without re-sorting names. Query renames update note and query.
3. Change either distractor's value to each of its three other destinations: six
   conditions. The two distractors originally share a value, so corresponding
   changes preserve identical destination histograms. The true queried value,
   names, options and record order stay fixed.
4. Swap the suspect's record with a neighbor or another distractor: two conditions.
   Move whole name/value records, preserving every fact and the query/options.

Q00 roles are fixed: queried `tevug`, suspect `tuven`, matched green distractor
`visuv`, neighbor `pisak`, and far distractor `gitix`. For Q01/Q02, deterministic
construction selects a same-value nonqueried distractor pair near the lexical
query slot and two other nonqueried records; the frozen case file records roles.
No roles or aliases are chosen using new model outcomes.

There are **256 logical cases, 248 distinct prompts**. Restricted A–E scoring is
primary. Check the original/matched baseline prompts with the existing independent
raw-forward scorer (24 distinct checks), then repeat the eight focal matched
baselines after all interventions. Total: **280 physical forwards**, one cached
Qwen3-4B-Instruct-2507 FP16 weight load, context 8192, seed 0, one A10/A10G, no text
generation/writing/downloads, zero configured retries. Startup cap 600 seconds,
execution cap 600 seconds, soft deadline 540 seconds. The reference scorer shares
weights/tokenizer/libraries; it is independent scoring code, not an independent
numerical stack. A reference mismatch stops the run. Baseline-repeat instability
is retained as an observation without an accuracy gate.

Save actual tokenizer IDs/pieces for every original/replacement name in bare,
leading-space, capitalized, and JSON-key snippets. Also save token offsets from
the exact focal baseline chat prompts, including note and query occurrences.
No token-distance or first-token heuristic is assumed to predict confusion.

```sh
.venv/bin/python -m game_memory.name_ablation prepare \
  --output-dir artifacts/name-ablation-v1/package \
  --historical-unit artifacts/memory-probe-v1/s1-preparation-20261117T200538Z/collection-bdm5ddqa/download/stage/qualification
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_name_ablation.py
```

The frozen Modal packet records the exact package/transport hash, bounds, App and
call identities. Its launcher uses standing authorization and refuses resubmission.
Read-only reporting: `.venv/bin/python -m game_memory.name_ablation report RUN`.
Keep redirected output outside RUN. Hashes, all raw logits/messages, selected
letters/destinations, exact-input reuse, timing, token usage, errors and completion
coverage are independently reconciled. Failed/partial attempts remain incomplete.

Interpret comparisons against the contemporaneous matched-order baseline, by
family and format. A wrong answer tracking the suspect's changed value, more than
the histogram-matched control, supports a suspect-specific behavioral effect.
Rename effects must be compared across both aliases and against control renames;
swaps probe position effects. Evaluate distractor-following separately when its
new value equals the true answer, where correctness alone cannot distinguish them.
All tested notes contain the correct queried fact, so ordinary mistakes count in
accuracy. Selected Q00/control cases do not estimate population accuracy or prove
an internal mechanism. Any revised name generator needs a separate version and
validation on fresh development families, preserving this checkpoint's evidence.
