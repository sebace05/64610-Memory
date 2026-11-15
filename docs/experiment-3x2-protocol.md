# Frozen 3×2 held-out evaluation protocol

This protocol is fixed before the first held-out game is opened. The development
pilot and hybrid smoke artifacts are separate and excluded from this evaluation.
Gameplay losses are results; infrastructure errors are recorded separately.
No actor or memory prompt is tuned using these evaluation episodes.

## Matched grid

- Conditions: prose, structured JSON, and hybrid memory at recipe-reread costs
  2 and 5. Hybrid's prose and JSON stores share one 256-token rendered allowance.
- Instances: 20 seeds, exactly 1000 through 1019 inclusive, in the CookingWorld
  `test` fold. Every seed appears once in each condition, for 120 planned episodes.
- Game: one location, two ingredients, zero distractors, no doors, unlimited
  inventory. One initial recipe is supplied at reset at zero action-budget cost;
  subsequent `read cookbook` and `examine cookbook` actions have the assigned
  cost. Other game actions cost one unit. The action budget is 80 units.
- Actor: `s2-action-v29`, with no immediate-repeat action filter. Memory writer:
  `p1-memory-v16`; rendered memory limit: 256 Qwen tokenizer tokens. Full
  history diagnostics and fake components are excluded.
- Model: `Qwen/Qwen3-4B-Instruct-2507` at immutable revision
  `cdbee75f17c01a7cc42f958dc650907174af0554`, on the RTX 5070 Ti,
  `float16`, greedy decoding, generation seed 0, context limit 8192, action
  output limit 128 tokens, memory output limit 512 tokens. The same checkpoint
  acts and writes memory in every condition.

## Execution and audit

Each condition has a separate pilot manifest, raw `events.jsonl` trace, result,
and launch log. A source snapshot and its SHA-256 digest are stored beside the
evaluation artifacts. The model may stay loaded between conditions; every game
starts with fresh actor and memory episode state. If a process is interrupted,
preserve its partial trace and launch log. A rerun, if technically justified,
uses a new attempt directory and is labeled as such. Never overwrite a result
or silently replace a valid gameplay loss.

Check the first completed episode in each condition for successful logging,
token accounting, memory bounds, and correct fixed settings. These checks may
stop an infrastructure failure, but not a game loss or undesirable model
behavior. Run the independent trace auditor on each condition and verify exact
coverage of all 120 planned `(memory, price, seed)` cells before analysis.

Report success, terminal failure, budget exhaustion, score, recipe rereads,
budget spent, model input/output tokens, generation time, and end-to-end time.
Compare conditions on matched seeds; resample whole seeds for uncertainty,
not individual turns. Report incomplete cells and infrastructure failures
explicitly. The two-seed development pilot is descriptive and is not pooled
with the held-out evaluation.

The one-room/two-ingredient difficulty was selected on the development pilot
to establish playable base behavior and remains fixed here. Local pilot timings
suggest several hours of GPU time for 120 episodes; a 1.5× contingency is
appropriate because longer failed episodes can consume all 80 budget units.
