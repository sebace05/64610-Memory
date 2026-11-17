# Repository design critique and recommendations

November 17, 2026. Reviewed the working tree based on commit `18ade45`, including its uncommitted minimal core and legal choice changes. The executable source digest at verification was `b961ad33e47118cbd8085195b57bb714fb7ca7c67d7d3f0664e1b349bd300aed`. Exact file hashes, trace references, calculations, and verification results accompany this report in [the evidence record](design-critique-2026-11-17-evidence.json).

## Recommendation

**Keep the small experiment runner and its evidence protections. Change the order of the research: qualify the reader, isolate writing from reading, and demonstrate a meaningful memory intervention before comparing complete memory systems.** CookingWorld is useful as a secondary integration benchmark. The present one-room task and untrained Qwen actor are a weak primary instrument for attributing failures to memory capacity or representation.

The largest problem is experimental identification: a failed game can result from a wrong cooking decision, invented memory, forgotten progress, malformed JSON, or ineffective recovery. Several of those failures occur with the relevant information available and substantial storage unused. More episodes of the same design would measure the combined agent's unreliability without necessarily explaining memory.

Qwen was a defensible inexpensive starting point. The repository does not contain a controlled comparison establishing that another model is better. It does contain enough evidence to stop treating this unadapted checkpoint as an already qualified evaluator of memory quality. Task-specific reader training is a plausible next investment if controlled decisions remain unreliable; training a model from scratch is unjustified.

This review covers all 14 current Python modules, the 12 test files and their coverage, both notebooks, dependencies, checkpoint/protocol documentation, handoff materials, and the local evidence inventory. Complete public trajectories for the four-seed full-history baseline and four v31 bounded games were examined, including their memory changes and actor outputs. Historical reproduction and replay evidence were checked where relevant. Archived source copies were treated as historical implementations, not additional independent trials. This is not a claim to have rerun every historical checkpoint. No pretrained-model inference, downloads, training, or cloud jobs were performed.

## What the evidence actually establishes

The following panels belong to different protocols and source snapshots. They are descriptive diagnostics, not a new matched experiment.

**Full-history v31 baseline, train seeds 0–3:**

| Seed | Outcome | Actions | Recipe rereads | Maximum retained tokens |
| --- | --- | ---: | ---: | ---: |
| 0 | Success | 11 | 1 | 464 |
| 1 | Success | 9 | 2 | 431 |
| 2 | Terminal failure | 3 | 0 | 238 |
| 3 | Success | 8 | 0 | 345 |

At seed 2, step 3, response sequence 12 chooses `cook chicken wing in oven`. The initial recipe says to grill, the system maps grilling to the toaster, and the toaster action is legal. The oven action executes and loses immediately. No retained record was missing. This is an action-selection failure with available evidence, not demonstrated forgetting. The complete [baseline report](../artifacts/history-window-modal-baseline/20261117T023432Z-01de8202/report.md) documents the failed four-of-four readiness gate and unexecuted window phase.

Every observed retained history in this panel fits below 512 tokens. A 512-token window would perform no eviction along these saved trajectories. It would therefore be a nonbinding retention intervention on those records. This counterfactual is not a window-game result and does not justify retrospectively changing that frozen protocol.

**v31 actor with v17 model-written memory, 512-token allowance:**

| Format | Seed | Outcome | Actions | Stored-token range | First important observation |
| --- | --- | --- | ---: | --- | --- |
| Prose | 0 | Terminal failure | 7 | 180–203 | Chooses chopping although memory retains slicing |
| Prose | 1 | Budget exhaustion | 42 | 128–203 | Writer claims meal completion after grilling chicken |
| JSON | 0 | Budget exhaustion | 80 | 140–141 | Two malformed updates and failed repairs discard new progress; knife-inspection loop follows |
| JSON | 1 | Budget exhaustion | 77 | 95–106 | Recipe disappears and is not restored after rereading; toaster-inspection loop follows |

The [bounded calibration report](v31-v17-roomy-calibration-2026-11-16.md) identifies the exact events. I independently checked the underlying trajectories. All 206 stored updates were below the limit; there were no over-budget rejections or generation-limit hits. There were 204 primary acceptances and two previous-state fallbacks. A writer knowing its allowance can compress proactively, so spare space does not prove that the allowance has no influence. It does mean these losses do not establish unavoidable capacity loss.

An earlier apparent prose advantage has a different explanation. In the [v29/v16 reproduction](reproduction-2026-11-15.md), prose won four cells and JSON lost four, but **all 30 prose updates were programmed factual fallbacks**, while JSON accepted 34 of 36 generated updates. The policy difference is independently visible in the raw validation events. Those wins cannot establish superiority of model-written prose. The current v17 policy appropriately removed that assistance.

The [18-call saved-request replay](failure-replay-2026-11-16.md) reproduced all nine baselines. Its reminder additions fixed none of the six selected failures. A later [six-call method readout](../artifacts/method-readout-modal-execution/20261117T032231Z-3fe0a360/report.md) reproduced its three baseline outputs, but elicited an empty direction list for the failed case despite the visible recipe. These selected cases support further diagnosis, not a universal conclusion that prompting cannot work or a measurement of internal reasoning.

## The most important design weaknesses

### 1. The experiment combines several questions before qualifying their components

The actor and writer use the same general instruction model. The writer chooses facts, invents a schema, compresses, and tracks state. The actor interprets that representation, plans, maps cooking verbs to appliances, produces JSON, and may invoke reviews or repairs. Game success combines all of these abilities.

That is a legitimate experiment if the question is “which complete memory agent works better?” It is insufficient for “is JSON a better representation?” or “did the smaller memory cause the failure?” Generated prose and generated JSON can contain different facts, uncertainty, plans, and errors before the reader sees either.

**Smallest improvement:** start with fixed public decision states and equivalent facts rendered in both formats. Include full history and an explicitly labeled sufficient public-fact note as diagnostic controls. Separately test the writer on fixed observation sequences. Return to complete games after those components behave usefully. The [existing design proposal](memory-constraints-design-and-task-plan.md) already distinguishes these questions; the missing step is making that distinction determine the next experiment.

### 2. The task is difficult for the policy but often easy to store

One room and two ingredients remove much navigation and long-delay information retention. Nevertheless, an incorrect cut or appliance is irreversible. The experiment can end before memory has been meaningfully stressed. Seed 2 demonstrates exactly that failure mode.

At the other extreme, legal information actions can consume an entire budget. JSON seed 0 examines the knife 77 consecutive times; JSON seed 1 examines the toaster 68 times. These trajectories establish poor progress and state use, but their length is not evidence of a demanding successful memory task.

**Smallest improvement:** measure the number of rewrites between observing a necessary fact and using it, whether intervening observations reveal it again, and whether the decision actually distinguishes memories. Calibrate on development instances, then freeze the allowance and task. Increasing rooms indiscriminately introduces exploration difficulty; decreasing the allowance after seeing a failed result would compromise the comparison.

### 3. Representation semantics are underspecified

JSON keys are model-managed. A value such as `inventory.salt="present"` may mean visible in the room, required by the recipe, or carried. The [annotation guide](memory-annotation-guide.md) correctly refuses to invent a meaning. That caution also reveals a measurement weakness: some state errors cannot be scored consistently because writer and evaluator have no shared semantics.

The prose writer likewise mixes requirements, plans, observations, and completion. In seed 1 it writes “meal preparation complete” after grilling, before taking salt or preparing a meal. It later invents an action list even though its input contains no legal-action list. Both formats spend memory repeating public budget or goal information already available at the next decision.

**Smallest improvement:** for a separately declared comparison, specify the same conceptual fields for both formats: required ingredients and operations, confirmed possession, confirmed completion, and unknowns. Keep plans distinguishable from facts. A shared schema changes the research question and must be labeled; it should not silently replace the current unconstrained writer. Do not restore Python factual rescue to the model-managed comparison.

### 4. Reviews and repairs create a complex policy without catching the central error

The [v31 actor](../game_memory/actor.py) reviews legal `prepare meal` proposals and repairs invalid output. A legal wrong cut or appliance passes directly to the environment. Consequently, syntax and legality controls can look excellent while the damaging semantic choice remains unexamined.

The successful four-seed baseline games also rely on seven repairs and three reviews across the panel. Success is a property of this whole policy, not just its first proposals. Adding a separate semantic reviewer for every failure would increase compute and introduce another fallible model stage.

**Smallest improvement:** compare one simple action interface on a fixed decision set before adding more review rules. The new [legal-choice interface](legal-choice-v1.md) is a reasonable candidate: it removes free-form command generation and guarantees interface legality. It is still untrained, removes reviews as well as changing output format, and has no real Qwen capability result here. Treat it as an interface-package comparison. A legal oven choice still loses a grilling recipe.

### 5. Development reuse creates a serious generalization risk

The history records many prompt revisions and repeated work on seeds 0 and 1. This was useful debugging, but it effectively tunes the system to a tiny set of recipes. The later seed-2 full-history loss shows why two familiar wins were an inadequate qualification gate. It does not by itself establish overfitting as the cause.

The [historical held-out protocol](experiment-3x2-protocol.md) has good principles, including matched seeds and uncertainty resampled by game. It targets retired actor/writer/hybrid implementations and cannot serve as the current evaluation specification unchanged.

**Smallest improvement:** freeze a new protocol only after development qualification. Split by game and recipe composition, not by individual turns. Use fresh validation recipes for model or prompt selection and keep the final test set unopened. Report paired success differences and uncertainty over games; thousands of correlated turns do not become thousands of independent task trials. The existing failed gate remains failed.

## Was CookingWorld the wrong benchmark?

**It was a reasonable integration environment, but an unnecessarily confounded first memory experiment.** Its procedural generation, text observations, configurable difficulty, and reproducible mechanics are valuable. The upstream project describes CookingWorld as a combination of ingredient search, preparation, and meal completion with held-out ingredient/preparation distributions. It is designed to test several abilities together. [TextWorldExpress project](https://github.com/cognitiveailab/TextWorldExpress).

For the present project, that brings costs: Java/Py4J startup, cooking-specific mechanics such as grilling with a toaster, irreversible mistakes, inventory tracking, recovery decisions, and many low-information inspections. Simulator throughput is not the limiting path for these LLM runs; TextWorldExpress's speed is useful, but does not solve actor qualification. [Original simulator paper](https://arxiv.org/abs/2208.01174).

There were easier choices:

| Choice | What it would isolate | Main limitation | Recommendation |
| --- | --- | --- | --- |
| Fixed public CookingWorld transcripts and decision probes | Reading equivalent facts; writer retention over identical evidence | Does not establish closed-loop success | Best immediate use of existing evidence |
| Small text task with randomized requirements, state updates, distractors, and a later choice | Capacity, rewriting delay, contradictions, and retrieval with minimal mechanics | Narrower external validity; requires a small new task specification | Best original starting point if designing again |
| Current CookingWorld gameplay | Combined memory, grounding, recovery, and planning | Failure attribution remains difficult | Keep as the secondary integration test |
| POPGym memory tasks | Memory in partially observable control across a range of tasks | Requires adaptation/training and does not directly evaluate prose versus JSON readers | Consider only if the research shifts toward learned recurrent control |

POPGym is explicitly designed around partial observability and memory baselines; that makes it a better conceptual fit for some memory questions, not an automatically cheaper replacement for this text-agent study. [POPGym paper](https://arxiv.org/abs/2303.01859).

A minimal text task should include paired cases where the current observation and legal options are identical but an earlier randomized requirement makes a different answer correct. Otherwise a model may solve the task from present cues without memory. Delay observations must not repeat the decisive fact. Those are proposed design requirements, not results from an implemented replacement benchmark.

In CookingWorld, the current legal-action list itself supplies useful state cues: for example, `prepare meal` availability changes with prerequisites, and `eat meal` appears after preparation. This is an intentional public interface, not a demonstrated hidden-state leak. A no-memory diagnostic would quantify how much information it supplies. It must be separately specified; it is not one of the current three conditions.

There is also unnecessary instructional burden in requiring the “earliest unfinished” direction. Successful seed 0 prepares the apple before the first listed chicken direction. The engine accepts that ordering. Unless global ordering is the research target, prefer any dependency-correct route in a future policy and scoring rubric; do not count a harmless ordering difference as a task failure.

## Was Qwen the wrong model, and is training necessary?

The selected checkpoint is a 4B non-thinking instruction model with a native context much larger than the repository's 8192-token runtime limit. Its general benchmark and tool-use results do not certify this particular recursive memory task. The published card recommends sampling settings; the project instead deliberately uses greedy decoding for a fixed experiment. That is a defensible control, not evidence that greedy is optimal. Changing decoding would require its own condition. The observed calibration failures had no output-cap hits, so increasing the 128-token actor cap or 1024-token writer cap is not an evidence-based first fix. [Qwen model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).

**The most relevant literature comparison is the DSSR paper already referenced in the repository.** It uses the same Qwen3-4B-Instruct-2507 base with a behavior-cloned reader, trained across memory formats with two DAgger iterations, then frozen; the reported full-history validation success is 97.8%. It uses original TextWorld, different tasks, a restricted action set, and inventory supplied in observations. Its strong reader is therefore not evidence that the unadapted base checkpoint should work here. It also reports limited writer-training gains, with failed long-delay improvement gates. These results motivate reader qualification and caution about writer training, not importing a headline success rate. [DSSR, setup and appendices A–B](https://arxiv.org/html/2609.32805v2).

My model-selection recommendation is a finite comparison on the same public decision cases: the pinned 4B baseline and one more capable candidate under an explicit compute budget. Qwen3-8B is one available candidate, not an established winner. Its template defaults to thinking mode; swapping only `model_id` into the current strict-JSON, short-output adapter would introduce an uncontrolled mismatch. Non-thinking mode must be explicit for a comparable test, and memory fit must be checked. [Qwen3-8B model card](https://huggingface.co/Qwen/Qwen3-8B).

Choose based on semantic action accuracy with sufficient evidence, destructive mistakes, equivalent-fact format sensitivity, and measured latency/tokens. Do not select the reader by whichever memory format happens to win. A stronger writer alone cannot correct the full-history wrong-appliance failure; a stronger reader alone cannot reconstruct a discarded recipe reliably.

**Training should target the component that fails its control:**

1. **Reader first, if sufficient-evidence decisions remain unreliable.** Use supervised action selection or a small LoRA adapter before considering RL. Train across both representations, full history, missing facts, and recovery cases, then freeze the reader before comparing writers. Include newly visited mistakes rather than only successful demonstrations. Accept multiple valid routes; missing-information examples should teach a justified information action rather than an oracle action requiring unavailable facts.
2. **Writer second, if a qualified reader still fails on generated state.** Train updates that preserve supported requirements, possession, and completion across unrelated observations. Evaluate complete recursive continuations: a good isolated rewrite can be erased by the next rewrite. Keep training and evaluation games separate and test cross-reader use.
3. **No new pretraining program.** The base already solves several games. The missing capability is task adaptation and reliable state handling, not demonstrated absence of all relevant pretrained knowledge.

TWOSOME provides separate evidence that environment-specific adaptation can improve LLM decision policies through valid-action scoring and LoRA/PPO. Its Overcooked and VirtualHome results do not establish that RL is necessary for this repository. They support training as a concrete alternative to indefinitely accumulating prompt rules. [TWOSOME paper](https://arxiv.org/abs/2401.14151).

Gold actions or hidden simulator state may be used as explicitly labeled offline supervision or evaluation references where appropriate. They must not enter the bounded actor/writer input, and trained examples should respect what was knowable from their supplied public evidence. Stored plans still count against the declared allowance.

## Implementation findings and smaller fixes

### High priority: the default auditor does not establish output provenance

Two controlled mutations on temporary copies pass the current auditor:

- **Action mismatch:** in the seed-2 full-history trace, replace the step-3 actor response's oven action with the toaster action, leaving the executed oven transition unchanged. Both the original copy and altered copy return `logging_checks_passed=true`.
- **Writer mismatch:** in prose seed 0, replace the initial writer response with unrelated text while retaining the original accepted memory and later actor inputs. Both copies still pass.

The raw evidence was never modified. These probes demonstrate gaps in the checker, not evidence that historical execution fabricated actions or memory. The [runner](../game_memory/runner.py) directly uses component outputs in the normal path. However, the general [auditor](../game_memory/summarize_diagnostics.py), especially the action/update processing around lines 524 and 541, verifies budgets, public input, and continuity without establishing those two output-to-state links. Its legal-choice-specific auditor already performs a stronger selected-label/action link.

**Smallest fix:** independently reconstruct the selected v31 output after its review/repair routing and compare its canonical command with the action event. For accepted prose require literal response equality; for JSON independently apply the declared canonical representation. For fallback require exact previous state. Add negative fixtures for each mismatch and the actual routing exceptions. Do not call the actor or memory updater to manufacture the expected result, and do not add live semantic corrections. Actual token recounting remains a separate verification.

### Medium priority: diagnostics misclassify an accepted action form

At `summarize_diagnostics.py:54`, `analyze_events` calls `validate_action_output(text, allowed)` without `allow_optional_article=True`. V31 accepts `take the red apple` as `take red apple`; the diagnostic classifies that same proposal as `unavailable_action`. I reproduced both results without inference. This can inflate apparent output/repair problems in valid v31 traces.

**Smallest fix:** choose the diagnostic normalization policy from the recorded actor metadata, retaining historical policies for historical evidence. Add one example covering the production/diagnostic disagreement. Do not change the v31 actor prompt.

### Medium priority: verification needs one complete runtime path

Current real-backend preparation checks model/runtime metadata, while Java startup occurs in environment reset after model construction. The caller must separately capture startup streams and status. This leaves room for an expensive model load before a known simulator incompatibility, and for missing startup evidence when a command is launched manually. The historical host OOM and gateway investigations show these are experienced workflow costs.

**Smallest fix:** perform the existing Java compatibility probe before loading weights in the real launch path, and give the documented command a small standard-library supervisor that captures startup, raw status, timeout, and load/episode timing. Reuse existing helpers and preserve all flags and errors. This does not call for restoring the retired cloud/session framework or implementing general resume.

### Medium priority: the research plan is less durable than the run identity

`prepare_pilot` records configuration, policy, source, and runtime, but the requested seed set is not stored in its manifest. The `seeds` argument checks duplicates against existing results. It does not establish the complete planned coverage or the endpoint/gate. Separate historical plans often provide that missing context, but a protocol ID alone is not a specification.

**Smallest fix:** keep one small immutable protocol record with the planned games, endpoints, gate, and exclusions, referenced by the existing manifest. Compare completed and missing cells against it. Preserve the current guards; a generic experiment registry is unnecessary.

### Medium priority: current versus historical documentation remains easy to confuse

README and `minimal-core.md` correctly identify the active CLI. Older files still call themselves current: `implementation-checkpoints.md` points to the old Qwen guide, `p1-memory.md` advertises removed hybrid imports, and `handoff/README.md` contains both implemented-launcher and no-launcher statements. The notebooks are historical and depend on retired launchers/session modules; that is an intentional boundary, not a reason to restore compatibility code.

**Smallest fix:** add a short historical-status banner and the exact restoration/source reference to each historical entry point; maintain one current result/evidence index. Leave historical results and commands intact. The existing minimal-core seed-0 result also deserves an index entry so a reader can find executed evidence without mistaking a prepared example for execution history.

### Lower priority: simplify only after measuring the expensive path

The current interfaces, frozen public view, lazy model imports, stateless memories, and single CLI are reasonable. Replacing the 14-module core with a framework would not address the demonstrated failures. Strict JSON, Unicode, and token accounting protect the experiment; removing them for fewer lines is poor prioritization.

The four bounded games used 255,235 input tokens, 33,935 output tokens, and 1203.58 generation seconds. Writer plus writer-repair calls consumed **919.58 seconds, about 76% of generation time**. That is the measured path to investigate. These unequal-length failed trajectories do not prove one format is slower at an equivalent task.

Potential future interventions include shorter equivalent-fact memories, constrained JSON generation, or explicit partial updates. Each changes writer behavior and needs a new condition. Constrained syntax can prevent a brace error; it cannot establish truthful inventory or progress. Do not add retrieval of an unbounded raw archive to a bounded-memory condition: that would change the storage model.

The legal-choice scorer currently materializes full sequence-by-vocabulary logits and duplicates the legal-action list in its prompt. Fixed alphabetical action order also ties labels to positions. Neither feature has a demonstrated runtime or accuracy penalty here. Profile before optimizing, and test seeded option permutations separately before claiming robust label-based decisions. Guaranteed legality and a single forward pass do not establish semantic accuracy or measured speed.

## A simpler path to a defensible result

If starting again, I would begin with fixed public transcripts or the small delayed-choice task, one reader, two equivalent encodings, and a few calibrated allowances. Only after demonstrating the intended intervention would I add recursive writing, followed by complete CookingWorld gameplay. That sequence would have avoided debugging a planner, an inventory tracker, a compressor, output syntax, and cloud execution at the same time.

For this repository now, the smallest useful sequence is:

1. **Repair evidence verification and navigation.** Fix the two provenance checks and optional-article diagnostic; add the current evidence index. These are software work and require no new inference.
2. **Freeze a decision panel and writer sequences.** Reuse saved failures and successful controls, then reserve new development cases covering different preparations and missing-information decisions. Specify equivalent-fact notes using public evidence only. Existing selected replays are development cases, not an unbiased test set.
3. **Qualify one reader.** Under separately authorized inference, compare the frozen 4B actor/interface with one candidate on sufficient-evidence controls. If neither is reliable, adapt the reader or simplify the primary task. Do not silently rescue decisions in Python.
4. **Measure the representation or system question explicitly.** For representation, hold facts fixed. For complete systems, allow writer differences but report their retention, contradiction, repair, fallback, and downstream costs. Calibrate allowance and delay on development data and then freeze them.
5. **Run a fresh held-out comparison only after qualification.** Use matched games, report uncertainty, retain all losses and infrastructure failures separately, and count every acting/writing/review/repair call. Add reread price only after a useful memory comparison exists.

This is a proposal for a new checkpoint. It neither authorizes inference nor reopens the historical failed window gate. The desired result is an attributable finding about memory, even if the finding is that reader errors or writer state corruption dominate at the tested allowances.

## Verification and limits

The required suite completed with **383 passed, 25 skipped, one warning in 22.07 seconds; exit 0**, using `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q` with local simulator loopback access. The warning is an upstream TextWorldExpress destructor `BrokenPipeError`. The 25 skips include unavailable model-library checks and the Java unified-logging regression. They do not verify actual pretrained inference or cached-Qwen tokenization in this environment.

An initial sandboxed attempt stalled in Py4J and was interrupted: 173 passed, one skipped, exit 2, with a partial-initialization destructor error. It is retained separately in the evidence record and is not presented as a complete test pass. No assertions, dependencies, or JVM settings were changed to obtain the completed result.

Fresh read-only audits passed for the four full-history games and each of the four bounded condition directories. The mutation probes expose the limits of those passes. Token ranges in this report come from saved counts, supported by the historical independent pinned-tokenizer recounts; this review did not perform a fresh tokenizer recount. Historical timings retain their original measurement scopes and hardware; no new cross-hardware efficiency conclusion is asserted.

The available results do not establish a format winner, a universally superior model, or that training is necessary. They do establish that a capacity-only explanation is inadequate, that model-managed state fidelity and reader grounding need separate controls, and that the existing audit should be strengthened before it supports further research claims.
