# Memory calibration integration gate

Contract: `memory-development-contract-v1`. This implementation authorizes CPU
checks only. Calibration, model downloads, GPU jobs, allowance selection, and
comparison launches need separate authorization.

Per-condition preflight uses `run_episode --pilot --prepare-only` with an explicit
`--protocol-id` for a declared study. It constructs the selected memory strategy
before loading weights and writes schema-2 `pilot-manifest.json`. The manifest
pins exact memory and actor metadata, episode settings (except seed), model and
runtime metadata, protocol, and source identity. Existing historical manifests
are readable evidence, but cannot be adopted or migrated into new runs.
Different allowances/formats/prices require separate condition directories.
Generic fixture and capability invocations retain generic protocol identifiers.

`runner.source_digest` fingerprints sorted Python modules, dependency files,
AGENTS.md, and the existing protocol document using relative paths and file bytes.
The deferred evaluator re-exports this helper for compatibility. `source_metadata`
adds the digest to Git commit/dirty evidence in manifest, episode header, and
result. Changes while sessions are editing intentionally invalidate a pilot;
prepare a new directory after source is stable. A dirty flag alone is insufficient
source identity. Protocol identity is also recorded in episode header and result.
No launcher exit status is inferred from episode completion; `run_logged` retains
both streams and the actual subprocess status, including nonzero/signal exits.

A future `comparison-manifest.json` must use schema 1 and exactly the shared
contract's fields: protocol_id, stage, source, actor, memory, model, runtime, game,
action_budget, strategies, memory_token_limits, recheck_costs, seeds. `source`
comes from `source_metadata`; component dictionaries are exact selected metadata;
model/game are dataclass serializations. Both prose and structured are required,
with two distinct positive allowances and one or two prices from 2/5. Seeds and
axis entries must be unique. Low/high use numeric order. The Cartesian product
is the required coverage. Development uses development folds; held_out uses test.
No live manifest is supplied: allowances and the 8/16-game choice remain unfrozen.
Role C owns validation/aggregation of that declaration and independent audits of
each immutable condition. This is an evidence format, not a scheduling engine.

Final integration requires A/B/C READY notes and no ongoing edits, then the full
suite. CPU/fake-model checks establish interfaces and evidence preservation;
they cannot establish useful Qwen writing, gameplay competence, binding memory
pressure, or a format advantage. See the role-D handoff for current check results
and outstanding dependencies.

Validated integration on November 16, 2026: A/B/C handed off READY and stopped
editing before the full suite. All **380 tests passed in 49.29 seconds** with
no skips, exit 0. The suite used project Python, disabled pytest plugin autoload,
local Java gateway access, and JVM performance-data files disabled to avoid
concurrent temporary-file lock warnings. Role D's handoff records exact commands,
earlier restricted-run failures/stalls, focused checks, and owned files.

The engineering gate for separately authorized T7 calibration is satisfied.
No GPU experiment, real-Qwen inference/tuning, model download, or historical
artifact edit was performed. Real gameplay inspection, full-history capability,
useful writer output, and memory-pressure calibration remain required before
freezing allowances or the 8/16-game comparison. Fake and tiny random CPU-model
checks cannot establish those research claims.
