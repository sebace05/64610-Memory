# Research redesign prompt for the designer agent

You are the research designer for the `64610-Memory` project. Propose a new experimental design that a separate critique agent will review before implementation. The critique agent has inspected the current repository and its saved gameplay. Your proposal must make its assumptions, controls, tradeoffs, and failure criteria explicit enough to challenge.

This is a design task. Do not implement the proposal or run training, pretrained-model inference, downloads, or cloud jobs. Read-only inspection and literature research are appropriate. Preserve existing code, results, failed attempts, and frozen protocols. Read the repository's `AGENTS.md` before proposing changes.

## Research objective and decision

Our working question is: **For a task-competent, frozen language-model agent, how do persistent-memory capacity and memory representation affect decisions, task completion, and inference cost?** Refine this into one primary, falsifiable question and identify which claims it can support.

We have compared model-written prose with model-written JSON in CookingWorld. We are reconsidering both the task and whether the actor needs task-specific training first. Do not assume that changing the benchmark is necessary, that fine-tuning is necessary, or that either memory format should win.

Distinguish two questions:

- **Representation:** Does the same decision-relevant information work differently when encoded as prose versus JSON?
- **Complete memory systems:** How do agents perform when writers choose, update, and compress their own facts in those formats?

The second includes writing quality, syntax, retention, and reading. It cannot isolate the effect of representation alone. Choose a primary question and place any other question in a clearly separate diagnostic or later phase. If your design instead studies zero-shot pretrained agents, explain why task training would change that claim.

## Current implementation and constraints

Repository: `/Users/abdivu/Desktop/school/6.4610/64610-Memory`.

Read these files if the checkout is available:

1. `AGENTS.md`, `README.md`, and `docs/minimal-core.md` for the active workflow.
2. `docs/design-critique-2026-11-17.md` and its adjacent evidence JSON.
3. `docs/v31-v17-roomy-calibration-2026-11-16.md`, `docs/reproduction-2026-11-15.md`, and `docs/memory-annotation-guide.md`.
4. Relevant current actor, memory, environment, runner, model, and audit modules. Historical documentation can describe removed implementations; inspect current callers before proposing reuse.

If files are unavailable, use the context below and identify what still requires verification. Do not invent unseen repository behavior.

The current core has one gameplay CLI, `game_memory.run_episode`, and three strategies: `full_history`, `prose`, and `structured`. V31 is the default actor. The writer is `p1-memory-v17`. The optional `legal-choice-v1` interface scores labels over public legal actions in full-history mode; it has software verification but no real Qwen capability result in the reviewed evidence. It also removes v31 reviews/repairs, so it is an interface-package change.

The pinned model is `Qwen/Qwen3-4B-Instruct-2507`, revision `cdbee75f17c01a7cc42f958dc650907174af0554`. Reviewed runs used greedy FP16 inference, context limit 8192, actor output cap 128, writer cap 1024, and stored-memory allowance 512. The known execution target is Linux with A10/A10G hardware. There is no fixed new training or evaluation budget: propose a finite allocation and label estimates rather than presenting them as measurements.

Each actor request starts fresh and receives the current public observation, goal, legal actions, remaining game budget, reread cost, and retained memory. Writers receive only previous memory, the action, the latest observation, and public task context. V17 enforces syntax and complete rendered size, allows one repair, and otherwise retains the exact previous valid state. It does not correct factual errors. JSON has no fixed task schema. Prose is literal text.

Persistent-memory allowance is distinct from total prompt size, generated-output limits, and game-action budget. Full history is an unbounded-storage diagnostic subject to the model context limit, with no writer. It is a reference, not a guaranteed mathematical upper bound. Bounded plans and scratch notes must share the declared allowance. No hidden history, retrieval archive, cross-request cache, recurrent state, or episode-specific weight update may bypass it. Distinguish general task knowledge in frozen weights from episode-specific facts that must be retained.

Keep scoring, hidden engine state, annotations, and scripted solutions out of actor/writer inputs. Any privileged reference belongs in separately labeled offline evaluation or training supervision, never an undeclared runtime aid. Evaluation inputs must respect what was knowable from public evidence.

## Findings the new design must address

- Four v31 full-history development games on train seeds 0–3 produced three wins and one loss. Seed 2 chose the oven for a grilling recipe despite retained recipe evidence, an explicit toaster mapping, and a legal toaster action. The failure was not demonstrated forgetting.
- Those four saved histories reached at most 464 tokens. A 512-token window would evict nothing along their observed trajectories. The historical four-of-four gate failed and the window phase was not run. Do not reopen or reinterpret that protocol.
- Four v31/v17 bounded games, prose/JSON on seeds 0/1, all lost while stored memory ranged from 95 to 203 of 512 tokens. There were 206 writes, two previous-state fallbacks, and no over-budget rejections or output-cap hits. Spare capacity does not prove the allowance had no influence, but these losses do not establish unavoidable capacity loss.
- Specific failures include chopping despite retained slicing instructions, inventing meal completion after grilling an ingredient, dropping the recipe, failing to restore it after rereading, and repeated low-information inspections. JSON syntax acceptance did not establish factual correctness.
- An earlier prose 4/4 versus JSON 0/4 result was confounded: all 30 prose updates were programmed factual fallbacks, while JSON accepted 34 of 36 model outputs. Current v17 removed that unequal assistance. Do not reinstate it and label the result model-written memory.
- Many prompt iterations reused seeds 0 and 1. Saved failures and successful controls are development material, not an unbiased evaluation set.
- The four bounded games used 1203.58 generation seconds; writing plus writer repair accounted for about 76%. Unequal failed trajectories do not establish comparative format efficiency.
- Two auditor gaps were reproduced on temporary copies: an actor response can disagree with its executed action, or a writer response with accepted memory, while the general auditor still passes. An optional-article normalization mismatch also affects diagnostics. Treat these as verification prerequisites and recheck their current status; they are not evidence that historical execution fabricated outputs.

## Compare two viable design paths

**Path A: retain CookingWorld and qualify or train the reader first.** Assess supervised action selection or parameter-efficient fine-tuning before assuming reinforcement learning is needed. Specify supervision, data sources, game-level splits, format coverage, recovery examples, and an objective qualification gate. Consider the distribution shift if training sees only full history but evaluation uses compressed state. Freeze one reader before comparing memory conditions; do not separately optimize a reader for each format unless that is a different declared experiment. Teach mechanics and generalization to new recipes, rather than memorizing the familiar games. Explain whether the task actually demands memory after qualification.

**Path B: use fixed public transcripts or a simpler primary memory task.** Specify a minimal task with randomized episode facts, meaningful updates, intervening observations, and later decisions. Include paired cases with identical current public inputs and options but different earlier facts requiring different choices. Prevent current observations, action availability, labels, or stereotyped answers from revealing the target. Vary retention delay without showing the decisive fact again. State whether CookingWorld should remain a secondary integration test.

Compare causal clarity, expected implementation effort, training cost, inference cost, external validity, and failure attribution. Select one path or a small staged combination. Do not propose a broad benchmark suite or training framework without a demonstrated need.

## Required design details

Your recommended design must specify:

1. **Claim and intervention.** Define the primary endpoint and contrast. Explain which variables change and which remain fixed, including actor, writer, action interface, output limits, and decoding.
2. **Information boundary.** Enumerate everything visible at decision/update time and everything persistent. If a schema is introduced, give equivalent conceptual guidance to both formats and label the schema as an intervention. Do not keep an extra uncounted fact tracker.
3. **Baselines and diagnostics.** Justify a minimal set that can separate reader error, writer corruption/omission, and capacity restriction. Consider full history, no memory, a bounded recent-history window, and equivalent sufficient public-fact notes; use only the controls needed for the claim. Privileged state is a separate diagnostic, not ordinary memory.
4. **Memory demand.** Demonstrate how the task requires past information, how delay/rewrite count is measured, and how capacity is calibrated. Do not equate a long rollout, eviction, or high utilization with a causal memory effect. Avoid both floor and ceiling performance. Freeze settings after development calibration.
5. **Training decision.** State which component, if any, is trained and why. Specify a small initial dataset/allocation, held-out qualification, a stopping rule, and the fallback if training does not help. Writer training should be a separate decision after reader qualification. No training from scratch without evidence that adaptation is inadequate.
6. **Evaluation.** Separate training, development, validation, and final test instances at the game/recipe level. Fix selection rules and planned coverage in advance. Include matched instances, uncertainty at the independent-instance level, semantic failure categories, technical failures, and all actor/writer/review/repair token and time costs. State what the proposed sample size can and cannot resolve.
7. **Feasibility and sequence.** Give a finite minimum pilot, proposed numeric gates with rationale, compute limits, stop conditions, and a small implementation plan tied to demonstrated failures. Separate software correctness from actual-model capability. No retrospective seed replacement or retuning under the same identity.

A controlled sufficient-fact note may prove that a useful encoding exists for a diagnostic state; it does not prove optimal compression or that an online writer could have selected it without hindsight. A trained reader must still make justified information-seeking decisions when its input lacks necessary facts. High success must not be obtained by leaking the evaluation recipe through training, metadata, or a reference solver.

## Primary sources to verify

- [TextWorldExpress](https://github.com/cognitiveailab/TextWorldExpress) is an accelerated text-game environment for agent research; it does not require a particular modern LLM training recipe.
- [Original TextWorld paper](https://arxiv.org/abs/1806.11532) explicitly concerns training and evaluation of reinforcement-learning agents. Distinguish original TextWorld from the project's TextWorldExpress adapter.
- [DSSR](https://arxiv.org/html/2609.32805v2), particularly setup and appendices A–B, uses the same Qwen base family/checkpoint with a behavior-cloned, subsequently frozen reader. Its reported full-history validation success is 97.8%. Its environment, action filtering, inventory input, and training differ from ours; do not transfer that rate to the pretrained checkpoint or our task. Its writer-training gains also have important delay limitations.

Use primary sources for additional technical claims. Distinguish published results, local observations, and your hypotheses. Verify source details rather than reproducing the earlier critique unquestioningly.

## Deliverable for the critique agent

Return one concrete proposal, preferably `docs/research-redesign-proposal.md` if working in this checkout. Include:

- A short decision and exact primary research question.
- A compact comparison of Paths A and B and the reason for your choice.
- The proposed protocol, training decision, controls, gates, and finite resource allocation.
- A complete small worked episode with the public inputs, memory snapshots, counted-budget policy, and correct decisions. Show both formats and a missing-fact case; mark illustrative encodings and unmeasured tokenizer counts honestly.
- The smallest implementation changes and validation needed before inference.
- The strongest threats to validity, unresolved decisions, and evidence that would make you abandon your recommendation.

Close with a critique checklist: whether the intervention isolates the stated question, whether the reader is qualified, whether episode facts can bypass memory, whether the capacity/delay intervention is meaningful, whether format guidance is fair, whether the held-out split is clean, and whether the cost is justified. The critique agent must be able to identify a concrete flaw or approve a concrete design without filling in missing experimental choices.
