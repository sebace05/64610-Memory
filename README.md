# 64610-Memory

Sebastian, Liam, Colin, and Pablo's project for MIT 6.4610 NLP.

## Project overview

**Research question:** How does the cost of recovering forgotten information change which memory strategy works best for an LLM agent?

We will compare prose notes, structured JSON, and hybrid memory in CookingWorld using TextWorldExpress. Each agent has the same memory allowance and action budget. Recipe rereads cost either 2 or 5 budget units; other actions cost 1. We will compare completion, recipe rechecks, game score, budget consumption, inference tokens, and runtime.

**Current status:** S1 is implemented and verified locally (October 30, 2026): 16 real-simulator tests pass, and three development seeds replay successfully at both rechecking prices. The S2 episode runner and fake integration fixtures are implemented and verified; its real-model milestone is still open. P1 production prose, JSON, and hybrid strategies are implemented and fixture-tested: 100 focused memory tests, 11 production-memory simulator regressions, and all 143 local tests pass. Real model/tokenizer integration, P2, and batch resume remain pending.

## Run the S1 environment verification

Requires Python 3.10+ and a working Java runtime. Tested locally with Python 3.12 and Java 8; no GPU or model access is needed for S1.

```sh
java -version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m game_memory.verify_s1 --output-dir artifacts/s1
```

- [Environment setup, behavior, and handoff](docs/s1-environment.md)
- [Shared AgentView/configuration/transition contracts](game_memory/contracts.py)
- [Saved real-game verification summary](artifacts/s1/summary.json)
- [Real-simulator tests](tests/test_environment.py)

**Important:** `examine cookbook` reveals the recipe too, so both it and `read cookbook` incur the selected rechecking price. Verification traces use privileged scripted solutions for plumbing checks only; they are not LLM results or an agent policy.

## Run the S2 integration fixture

This uses the real game with a scripted fake model and placeholder memory. It validates integration and logging, not LLM capability or memory quality.

```sh
.venv/bin/python -m game_memory.run_episode --backend fake --strategy prose --recheck-cost 2 --action-budget 6
.venv/bin/python -m game_memory.run_episode --backend fake --strategy hybrid --recheck-cost 5 --action-budget 6
```

Each invocation creates `events.jsonl` and `result.json` in a new directory under `artifacts/s2-fixtures/`. Fake runs are explicitly labeled `integration_fixture`; their whitespace usage counts are not real model tokens.

- [Runner and component handoff](docs/s2-runner.md)
- [Model, memory, and actor interfaces](game_memory/components.py)
- [Episode runner](game_memory/runner.py)
- [Fresh-prompt actor](game_memory/actor.py)

## P1 memory implementations

`ProseMemory`, `StructuredMemory`, and `HybridMemory` in `game_memory/memory.py`
implement the existing memory interface with shared writer instructions, one
repair attempt, and previous-valid-state fallback. Hybrid counts both stores and
its labels/separators under one allowance. See [policies, example records, and
handoff](docs/p1-memory.md), [P1 unit tests](tests/test_memory.py), and
[runner/simulator regressions](tests/test_memory_integration.py).

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_memory.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_memory_integration.py
```

These checks use scripted outputs and controlled counters through the model
interface. Actual Qwen token accounting and memory quality still require Liam's
production tokenizer/model. The existing fake CLI remains an integration fixture.

## Scope and deadlines

- **October 30–November 1:** agree on interfaces and build independently runnable components.
- **November 2:** first real episode connecting the game, model, memory, and logging.
- **November 3:** review the first capability and six-condition pilot results.
- **November 5:** finish the pilot audit, estimate compute costs, and freeze the evaluation protocol.
- **November 6–12:** run and audit the main experiments; finish core experimentation by November 12.
- **November 13–19:** analysis and report writing. Report draft due **November 19**.

Plan for approximately **8 human hours per person this week**: three two-hour task blocks, one hour for setup/contracts, and one hour for integration/review. Coding-agent execution and GPU runtime are separate from these estimates; supervision and review count toward human time. Report blockers early and split tasks that exceed their allowance.

## Modular implementation

The environment adapter, actor/runner foundation, shared interfaces, and P1 memory strategies are implemented in `game_memory/`. Real model/tokenizer integration and the batch executor remain pending. Each module must include an example input/output so other owners can develop against fixtures before integration.

| Component | Owner | Responsibility |
| --- | --- | --- |
| Shared contracts/configuration | Sebastian, reviewed by everyone | Public data structures, configuration fields, and module interfaces. |
| Environment adapter | Sebastian | Reset games, execute actions, apply rechecking costs and budgets, report scores and termination. |
| Memory strategies | Pablo | Prose, JSON, and hybrid updates; rendering, token enforcement, validation, and reset isolation. |
| Model adapter and actor | Liam | GPU inference, fresh action prompts, parsing, token/runtime accounting, and a fake backend for local development. |
| Episode/batch runner | Sebastian | Connect modules, log traces/results, and resume batches without duplicating completed games. |
| Evaluation tooling | Colin, with Liam reviewing statistics | Validate result coverage, calculate summaries and paired comparisons, and annotate traces. |

### Shared interfaces

Agree on these project interfaces before implementing independently. They wrap the upstream environment; they are not exact TextWorldExpress API signatures.

```text
Environment.reset(seed, game_config) -> AgentView
Environment.step(action) -> Transition
Model.generate(messages, purpose=...) -> Generation
Model.count_tokens(text) -> int
Memory.empty() -> serialized text
Memory.update(previous_memory, action, observation, context, model) -> MemoryUpdate
Memory.render(memory) -> text
run_episode(config, environment, actor, memory, model, output_dir=...) -> result dictionary
```

- `AgentView`: current observation, goal, permitted actions, remaining budget, and recipe-reread price.
- `Transition`: next view plus action cost, score, success/failure, and termination information. Scoring-only fields stay out of model prompts.
- `Generation`: generated text, input/output token counts, and elapsed time. Model/runtime identity and settings belong in `Model.metadata`.
- `MemoryUpdate`: accepted serialized memory and validation/repair events. The runner counts rendered tokens and inference usage.
- `EpisodeResult`: episode identity, outcome, score, steps, recipe rereads, budget spent, tokens, runtime, and termination reason.

The environment does not call the model; the model does not inspect game internals; memory cannot read the raw history; evaluation reads saved results rather than running games.

## This week's task board

S1 is **Done locally**. S2 is **In progress**: runner and fixtures implemented; real L1/P1 integration pending. P1 is **Review**: implementation and controlled-counter fixtures pass; real tokenizer integration remains pending. Other tickets remain **Planned**. Each has one owner and approximately two hours of human work. Use **Planned → In progress → Review → Done**, with **Blocked** when necessary. A task is done only when its evidence is linked and reviewed.

### Sebastian — environment and integration

| ID | Due | Task | Done when |
| --- | --- | --- | --- |
| S1 | Nov 1 | **Done locally (Oct 30).** Install CookingWorld and implement the environment/cost wrapper. Check the Java dependency, reset behavior, recipe-action detection, budget limits, and termination. | A fixed action sequence on the same seed gives matching observations/scores under both prices, with the expected reread-cost difference. Save the command, configuration, and trace. |
| S2 | Nov 2 | **In progress.** Build the runner against fixtures, then integrate the real environment, model, and memory. Depends on S1, P1, and L1. | One real episode ends for a valid reason and saves a complete result and trace. A mock-only run does not count. |
| S3 | Nov 4 | Add episode identifiers, safe result writing, coverage records, and resume-by-completed-episode behavior. Depends on S2 and the agreed log schema. | Interrupt and resume a development batch without duplicate completed episodes. Every planned run is complete, invalid, or pending. |

### Pablo — memory strategies and correctness

| ID | Due | Task | Done when |
| --- | --- | --- | --- |
| P1 | Nov 1 | **Review.** Prose, JSON, and hybrid implemented through the shared update/render and token-count interface. [Policies and fixture evidence](docs/p1-memory.md); 100 focused memory tests and 11 runner/simulator regressions pass. Actual Qwen tokenizer integration pending L1. | All three process the same fixture. Rendered memory respects the combined 256-token allowance, including JSON formatting and hybrid separators. |
| P2 | Nov 2 | Verify history isolation, reset behavior, malformed-output/overflow handling, and a separately labeled full-history diagnostic mode. Depends on P1. | Checks demonstrate no raw-history leakage, no cross-episode memory, valid repair/fallback behavior, and correct hybrid accounting. Full-history mode does not silently truncate. |
| P3 | Nov 5 | Audit at least four real pilot traces and repair correctness defects. Depends on pilot traces from L2. | Findings identify the episode/step and evidence for a fact being retained, lost, contradicted, or re-observed. Report explicitly if memory demand is absent. |

### Liam — model, capability, and experiment protocol

| ID | Due | Task | Done when |
| --- | --- | --- | --- |
| L1 | Nov 1 | Run the candidate model on Colab; implement the model adapter, actor, and local fake backend. Pin model/tokenizer revision, libraries, precision, and generation settings. | A real action response and memory update are saved with tokens, latency, GPU, and runtime settings. |
| L2 | Nov 3 | Run a staged development pilot: one full-history episode first, then up to five full-history diagnostics and two instances across all six bounded-memory conditions. Depends on S2 and P2. | Save outcomes, costs, and a diagnosis of gameplay, memory, formatting, or infrastructure failures. Keep evaluation seeds unused. |
| L3 | Nov 5 | Freeze prompts, settings, seed lists, and failure rules; forecast the full evaluation's cost with a 1.5× contingency. Depends on L2 and S3. | A versioned protocol and measured forecast support a decision to run 120 episodes, reduce matched instances for resource reasons, or resolve a named blocker. |

### Colin — evaluation and evidence

| ID | Due | Task | Done when |
| --- | --- | --- | --- |
| C1 | Nov 1 | Define metrics and valid/invalid runs; create synthetic results with hand-calculated expected summaries. Liam reviews the definitions. | Required log fields and expected answers are explicit, allowing analysis work before real results exist. |
| C2 | Nov 3 | Implement the results summarizer, paired comparisons, and missing/duplicate-run checks using a coding agent. Depends on C1 and a real result from S2. | Synthetic checks pass and a real pilot result loads without manual editing. Liam reviews pairing and statistical calculations. |
| C3 | Nov 5 | Annotate four pilot trace windows and write approximately 250 words describing actual methods and proposal deviations. Depends on L2 and C2. | Examples link to evidence, distinguish observations from interpretation, and include technical review of two examples by Pablo or Liam. |

## Pilot defaults and experimental controls

These are initial decisions to verify during development, not tested findings.

- **Environment/model:** CookingWorld through TextWorldExpress; Qwen/Qwen3-4B-Instruct-2507 through Transformers and PyTorch. No training. Use the same model for acting and memory writing. Liam selects supported precision on the actual GPU and records it.
- **Six conditions:** three memory formats × two reread prices. Begin with a 256-token memory allowance and an 80-unit action budget; calibrate on development games before freezing evaluation.
- **Initial recipe:** working default is one standardized initial recipe reading outside the action budget, with the same resulting state/information in matched runs. Subsequent reads cost 2 or 5. Record this clarification explicitly in the protocol.
- **Actor input:** current observation, bounded memory, goal, permitted actions, remaining budget, and reread price. Build a fresh prompt each turn. Logs may retain history; the bounded-memory agent may not access it.
- **Memory update:** one requested generation at initialization and after each nonterminal action for every format. Hybrid shares one total allowance. Count exact rendered memory with the model tokenizer; 256 tokens is not the limit for the entire prompt.
- **Invalid output:** allow one repair attempt using the same visible evidence. If memory is still malformed or over budget, retain the previous valid memory. If an action remains invalid, record a failed attempt costing 1 unit without silently substituting an action. Count all inference attempts.
- **Information leakage:** do not provide free recipe/look/inventory helper calls. Audit whether observations or action lists reveal recipe details and document any unavoidable cues.
- **Data:** use disjoint development and evaluation seed lists. Hold game settings and the built-in environment split constant across the comparison. Match all six conditions on each instance; do not tune on evaluation outcomes.
- **Logs:** save exact actor/writer inputs, observations, actions, memory changes, costs, tokens, runtime, model/configuration versions, and termination. Separate infrastructure errors from valid gameplay failures.
- **Resume:** skip completed episode identifiers. An interrupted partial episode may restart from its seed; exact mid-episode recovery is not required this week.

## Checkpoints and fallback decisions

1. **Oct 30:** agree on contracts, example records, ownership, and experimental defaults.
2. **Nov 1:** demonstrate independently runnable environment, memory, model, and evaluation fixtures.
3. **Nov 2:** complete the first real integrated episode. If blocked, pause optional work and repair the failing interface.
4. **Nov 3:** inspect capability and memory demand. As a starting engineering heuristic, seek at least two full-history successes out of five and inspectable retention/recovery behavior. These counts are not statistical findings. If gameplay fails, try a simpler supported game configuration first. If memory is trivial, consider one development-only memory/task adjustment; do not tune until a preferred format wins.
5. **Nov 5:** review pilot traces, correctness, and measured cost; freeze the evaluation configuration. Persistent feasibility blockers need a TA discussion before launching a large batch.

Post a short asynchronous update on work days: artifact/link, next task, and blocker/help needed. After 30 minutes blocked, post a minimal failing example and contact the dependency owner.

## Main evaluation and writing

- **Nov 6–9:** run the frozen 20-instance × 6-condition evaluation: **120 episodes**. Check early batches for correctness and cost without retuning on outcomes.
- **Nov 10–12:** finish justified infrastructure/correctness reruns, audit coverage, and freeze results. If resources require fewer instances, use the same prespecified seed prefix for all conditions and report the reason.
- **Analysis:** report completion and recipe rechecks, plus score and resource use. Compare structured versus prose and hybrid versus prose at each price, then compare those differences across prices. Bootstrap whole matched game instances for uncertainty; do not treat individual steps as independent samples. The two-instance pilot is descriptive.
- **Nov 13–19:** Sebastian writes systems/reproducibility; Pablo writes memory methods and limitations; Liam writes quantitative results/analysis; Colin assembles and edits framing, related work, and the full draft. Each owner verifies their technical claims.
- **Internal deadlines:** complete draft Nov 15; technical review Nov 17; clean submission copy Nov 18; report draft submission Nov 19.

## Coding-agent workflow and resources

- Give each coding-agent ticket its allowed files, interface, fixtures, acceptance checks, and required demonstration command/output.
- Use separate worktrees or nonoverlapping file ownership for parallel agents. Coordinate changes to shared contracts, configuration, and dependencies through the human owner.
- Owners review and merge code and can explain its behavior. Passing self-written unit tests alone does not establish real environment/model integration.
- Prioritize automation, accounting checks, trace inspection, and matched evidence. A viewer or additional repeats can follow a working, affordable pilot. Fine-tuning, archive retrieval, a second environment, and multi-service infrastructure are outside this week's scope.
- Plan around four separate approximately $40 Colab allowances and up to $100 additional team spending. Measure remaining balances and actual costs; do not assume credits are pooled. Start with one GPU worker and stop idle sessions.

## Implementation references

- [TextWorldExpress](https://github.com/cognitiveailab/TextWorldExpress): environment interface, Java dependency, and CookingWorld configuration.
- [Qwen3-4B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507): model identity, chat template, and Transformers usage.

Model capability, compatibility, runtime, and cost for this project remain pilot deliverables.
