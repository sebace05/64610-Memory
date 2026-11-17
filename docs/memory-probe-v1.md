# Memory probe v1

Status: protocol frozen before inference. Each Modal stage requires separate user
authorization. CookingWorld work is paused; its evidence and failed gates are
unchanged and not reinterpreted. Implementation: `game_memory/memory_probe.py`;
tests: `tests/test_memory_probe.py`.

## Question

For stock, frozen Qwen/Qwen3-4B-Instruct-2507 (revision
cdbee75f17c01a7cc42f958dc650907174af0554), does reducing the stored-memory
allowance from 256 to 64 tokens change the accuracy difference between
model-written JSON and model-written prose memory on a delayed factual query
after 12 intervening no-change rewrites? If the pilot floor rule selects 128,
the executed question is 256 versus 128 and is reported that way.

This compares complete memory systems (writing, compression, retention, syntax
handling, reading). It does not isolate JSON syntax. Neither format is predicted
to win; null and inconclusive results are valid.

## Task

- 8 opaque five-letter lowercase entities; destinations amber, blue, green,
  violet; repeats allowed.
- Observation 0: `Assignments: <name>=<destination>; ...` with all 8 initial
  assignments in family-shuffled order.
- Observation 1: `Update: <name> is now assigned to <destination>, replacing its
  previous assignment.` and `<Name>'s assignment is revoked; its destination is
  now unknown.` (different entity).
- Observations 2-13: 12 fillers, `Ambient pulse <name>. No assignments changed.`,
  with no entity names, destination words or query cues.
- Families of four sibling worlds; sibling w requires destination w (amber,
  blue, green, violet order). Reader inputs outside retained memory are
  byte-identical across siblings.
- Updated-query families (even index): siblings share observation 0 and the
  target's old value; the update assigns the target each of the four
  destinations (one leaves it unchanged; still an explicit update). Old values
  are balanced across a split's updated-query families.
- Untouched-query families (odd index): the target's initial value varies across
  siblings; a different entity receives the same update in all siblings.
- The revoked entity is never the primary query.
- Options: four destinations plus `insufficient information`, labels A-E,
  family-seeded order shared across siblings and conditions, independent of
  the answer.

## Frozen model-facing texts

Public rules (writer `public_rules` field and reader input):

1. An assignment remains valid until a later explicit assignment update or revocation.
2. An assignment update states the current destination and supersedes the earlier record. It may repeat the same destination. Revocation means the current destination is unknown; an old assignment must not be reused.
3. Any entity may be queried later. The query is not disclosed during writing.
4. No record lookup, reread, or other information source is available at query time. Choose "insufficient information" when the supplied evidence does not justify a destination. This is abstention, not a successful information-recovery action.

Reader system instruction:

> Use only the supplied context and current query. Assignments persist until explicitly replaced or revoked; destinations may repeat. Choose the latest supported destination of the queried entity. If the assignment is absent, revoked, or unresolved, choose insufficient information. Do not infer a destination from the other entities or guess. In diagnostic notes, a JSON null denotes an unknown destination; an omitted entity supplies no assignment. The context may be public history, prose, or JSON. Return only the label of one listed option.

Reader user message: `Public rules:`, the rules, `Retained context:`, the
literal memory, `Current query:`, `What is <entity>'s current destination?`,
then `A. <option>` ... `E. <option>`. No probe position, family ID or allowance.

Writer instruction (probe-writer-v1, both formats):

> Maintain the latest confirmed assignment of every observed entity. Replace superseded assignments and distinguish revoked or unknown assignments from confirmed destinations. Destinations may repeat. Any entity may be queried later. Use only previous memory, the last event, and the new public observation. Do not invent assignments or retain irrelevant pulse descriptions. Your replacement is the only persistent notebook and its complete rendering must fit the stated token allowance.

Writer system message: `Memory writer probe-writer-v1`, the instruction,
`Required format:`, then the existing p1-memory-v17 prose or JSON format
sentence verbatim. Writer user message: JSON with exactly previous_memory,
last_event (`[INITIAL_OBSERVATION]` / `[PUBLIC_UPDATE]`), observation,
public_rules and memory_token_limit.

## Components

- Writers inherit v17 rendering, syntax/size validation, one repair and exact
  previous-valid-state fallback through `_BoundedMemory._messages`; v17 defaults
  are unchanged. Greedy, cap 1024, context 8192. No semantic correction.
- Memory: the counted rendered string only (pinned tokenizer, no special tokens).
- Reader: one restricted next-label argmax over A-E (first-listed tie), via
  `TransformersModel.score_choices`; no generation, review or repair.
- All model calls go through `runner._LoggedModel` with a probe-owned emitter.
- Probes: P0 after observation 1; P12 after filler 12; stateless.
- Carry-forward: the P0 read of the P0 snapshot is referenced as the "no further
  rewriting" comparison at P12 (identical input, no extra call).
- Controls at both probes: full public history, no memory, sufficient prose,
  sufficient JSON (forward reduction of public events, all 8 entities, never in
  writer paths, must fit 256 actual tokens).
- Reader results are reused only for exact (family, rendered messages, labels,
  model identity); the key never contains the gold answer.

## Splits

dev D00-D01; qualification Q00-Q03; test T00-T07. SHA-256-derived per-purpose
seeds from global seed 0. Disjoint names and normalized compositions across
splits. Frozen and hashed before inference. No replacement or regeneration.

## Gates

- Q0 (16 worlds, P12; 96 logical assessments, 76 distinct prompts): at least
  15/16 correct for full history, sufficient prose and sufficient JSON
  separately; at least 15/16 abstentions for each missing-fact format (even
  f+w: target fact removed; odd f+w: revoked entity queried); no-memory factual
  accuracy at most 4/16 (a construction check, not reader competence);
  byte-identical sibling inputs; zero technical failures. Failure ends the study.
- Pilot (D00-D01, 64 and 256, both formats, both probes): stop if both formats
  score at most 2/8 at P12/B256. Otherwise B_low = 128 if pooled P12/B64
  factual accuracy is below 4/16, else 64. No required direction or size of
  any accuracy change. An incomplete pilot yields no decision.

## Analysis

Per family f, A(f, format, B, probe) is the mean over the four siblings. At P12:
D_f = [A(JSON,B_low) - A(prose,B_low)] - [A(JSON,256) - A(prose,256)].
Primary estimate: equal-weighted mean of the two stratum means. Report all
eight D_f values, positive/negative/zero counts, and a stratified family
percentile bootstrap (10,000 resamples, seed 0, four families with replacement
per stratum). With four families per stratum the interval is a small-sample
description; its coverage is not established. Secondary: per-cell P0/P12
accuracy, abstention and destination coverage; P0-to-P12 change;
carry-forward; all controls; costs. Annotation: 32 P12 snapshots (one sibling
per test family x four format/allowance cells), sibling destinations balanced
within each stratum by a dedicated seeded shuffle; one annotator (the user).
An unchanged update retained correctly is "retained", not "stale".

## Execution limits

- Modal A10/A10G; one Qwen load per worker; zero retries.
- S1: startup cap 600 s, execution cap 7200 s.
- S2: T(n) = max(600, ceil(1.5 x (L + n x R) + 300)) from S1 measurements; one
  worker if T(8) <= 14400, otherwise two separately authorized workers
  (T00-T03, T04-T07) each capped at T(4) <= 21600.
- Request ceilings: S1 1070; S2 3976; whole study 5046.
- Completed units (Q0, each family) are fsynced, recorded with hashes and
  committed to the results volume before the next unit starts.

## Exclusions and interpretation limits

No training, adapters, validation pool, extra pilot or calibration, extra
conditions or samples, recent-history window, double coding, CookingWorld runs,
legacy v31 auditor repair, dashboards, or general execution framework. Eight
independent families support weak population inference only. No claims about
internal reasoning, general reliability, CookingWorld transfer, or
information-theoretic capacity.
