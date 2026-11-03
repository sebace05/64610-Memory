"""Connect the environment, actor, memory, and model for one game.

Read run_episode() for the main flow: reset -> initial memory write -> choose
action -> execute action -> update memory -> repeat until the game ends.
_LoggedModel records inference calls made by both the actor and memory writer.
"""

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import subprocess
import time
from typing import Sequence
import uuid

from .components import Actor, Generation, MemoryContext, MemoryStrategy, Message, Model
from .contracts import CookingWorldConfig
from .environment import CookingWorldEnvironment


def source_metadata() -> dict:
    """Record source identity without putting Git status contents in the log."""
    root = Path(__file__).resolve().parents[1]
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                capture_output=True, text=True, check=True, timeout=5)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                                capture_output=True, text=True, check=True, timeout=5)
        return {"commit": commit.stdout.strip(), "worktree_dirty": bool(status.stdout)}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "worktree_dirty": None}


@dataclass(frozen=True)
class EpisodeConfig:
    """Fixed settings for one run; frozen prevents accidental field reassignment."""

    seed: int = 0
    strategy: str = "prose"
    recheck_cost: int = 2
    action_budget: int = 80
    memory_token_limit: int = 256
    game: CookingWorldConfig = field(default_factory=CookingWorldConfig)

    def __post_init__(self) -> None:
        # Validate before a game or model call starts. These are configuration
        # errors, rather than evidence that an agent failed at the task.
        if type(self.seed) is not int or not 0 <= self.seed <= 2_147_483_647:
            raise ValueError("invalid seed")
        if self.strategy not in {"prose", "structured", "hybrid", "full_history"}:
            raise ValueError("unknown memory strategy")
        if type(self.recheck_cost) is not int or self.recheck_cost not in {2, 5}:
            raise ValueError("recheck_cost must be 2 or 5")
        if type(self.action_budget) is not int or not 1 <= self.action_budget <= 1_000_000:
            raise ValueError("invalid action budget")
        if type(self.memory_token_limit) is not int or self.memory_token_limit < 1:
            raise ValueError("memory_token_limit must be a positive integer")
        if not isinstance(self.game, CookingWorldConfig):
            raise TypeError("game must be a CookingWorldConfig")


class _LoggedModel:
    """Wrap a supplied model without adding conversation history.

    Actor and memory modules receive this adapter instead of the underlying
    model, so their successful generations and repair calls share one ledger.
    emit writes trace events; step_number reads the runner's current turn.
    """

    def __init__(self, model: Model, emit, step_number) -> None:
        self._model = model
        self._emit = emit
        self._step_number = step_number
        self.input_tokens = 0
        self.output_tokens = 0
        self.elapsed_seconds = 0.0
        self.usage_complete = True
        self.by_purpose: dict[str, dict] = {}

    @property
    def metadata(self) -> dict:
        return self._model.metadata

    def count_tokens(self, text: str) -> int:
        # Counting memory uses the backend's tokenizer but performs no inference.
        count = self._model.count_tokens(text)
        if type(count) is not int or count < 0:
            raise ValueError("model tokenizer returned an invalid token count")
        return count

    def generate(self, messages: Sequence[Message], *, purpose: str) -> Generation:
        # Record the request before calling the model, so a failed call still
        # leaves its input and purpose in the trace. Tuple fixes message order.
        messages = tuple(messages)
        request = {"step": self._step_number(), "purpose": purpose,
                   "messages": [asdict(m) for m in messages]}
        self._emit("model_request", **request)
        try:
            result = self._model.generate(messages, purpose=purpose)
            if not isinstance(result, Generation):
                raise TypeError("model must return a Generation")
        except Exception as error:
            # A failed request may have consumed resources without returning
            # usage. Keep known totals, but mark them incomplete instead of zero.
            self.usage_complete = False
            self._emit("model_error", step=request["step"], purpose=purpose,
                       error_type=type(error).__name__, error_message=str(error))
            raise
        # Aggregate all successful calls, including any action/memory repairs.
        # Per-purpose totals separate acting cost from memory-maintenance cost.
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        self.elapsed_seconds += result.elapsed_seconds
        totals = self.by_purpose.setdefault(purpose, {
            "calls": 0, "input_tokens": 0, "output_tokens": 0, "elapsed_seconds": 0.0
        })
        totals["calls"] += 1
        totals["input_tokens"] += result.input_tokens
        totals["output_tokens"] += result.output_tokens
        totals["elapsed_seconds"] += result.elapsed_seconds
        self._emit("model_response", step=request["step"], purpose=purpose, **asdict(result))
        return result


def run_episode(
    config: EpisodeConfig,
    environment: CookingWorldEnvironment,
    actor: Actor,
    memory: MemoryStrategy,
    model: Model,
    *,
    output_dir: Path,
) -> dict:
    """Run one episode; caller owns and closes the environment.

    A valid gameplay failure is status=completed. Component failures are
    status=error, with success=None; they must not be counted as game losses.
    This is not a resumable batch executor (S3).
    """
    # Reject mismatched components before creating artifacts. Otherwise a run
    # could be labeled with settings different from those the game actually used.
    if (environment.recheck_cost, environment.action_budget) != (
        config.recheck_cost, config.action_budget
    ):
        raise ValueError("environment costs/budget do not match episode configuration")
    if memory.metadata.get("strategy") != config.strategy:
        raise ValueError("memory strategy does not match episode configuration")
    if actor.metadata.get("requires_unlimited_inventory") and config.game.limit_inventory_size:
        raise ValueError("mechanics prompt requires unlimited inventory")
    full_history = config.strategy == "full_history"
    if full_history != (actor.metadata.get("context_mode") == "full_history"):
        raise ValueError("actor context mode does not match episode configuration")
    if full_history and memory.metadata.get("diagnostic_only") is not True:
        raise ValueError("full history requires an explicitly diagnostic archive")
    # Copy metadata into JSON-native values (e.g. tuple -> list). This keeps the
    # returned result identical in shape to the result read back from disk.
    components = json.loads(json.dumps({
        "actor": dict(actor.metadata), "model": dict(model.metadata),
        "memory": dict(memory.metadata),
    }))
    # Unknown/unmarked components are conservatively treated as test fixtures.
    is_fixture = any(c.get("is_fake") is not False for c in components.values())
    kind = "integration_fixture" if is_fixture else (
        "full_history_diagnostic" if full_history else "development")
    # Unique directories preserve previous runs. Skipping completed experiment
    # configurations on resume is separate S3 work; UUIDs do not implement that.
    episode_id = uuid.uuid4().hex
    directory = Path(output_dir) / episode_id
    directory.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    step = 0  # Turn being attempted; the environment counts processed attempts.
    last = None
    # state is the memory module's serialized state; rendered is the exact text
    # it exposes to the actor. Neither variable is the full interaction history.
    state = ""
    rendered = ""
    phase = "initialization"  # Identifies where an exception occurred.
    error_data = None
    outcome = "error"  # Only a valid game ending below changes this to completed.
    reset_complete = False
    source = source_metadata()

    with (directory / "events.jsonl").open("x") as events:
        sequence = 0

        def emit(event: str, **data) -> None:
            """Append one JSON object per line, in auditable sequence order."""
            nonlocal sequence
            record = {"event": event, "sequence": sequence,
                      "elapsed_seconds_since_start": time.perf_counter() - started, **data}
            events.write(json.dumps(record, sort_keys=True) + "\n")
            events.flush()  # Make events available while the episode is running.
            sequence += 1

        # Both components must use this same adapter for all their model calls.
        logged = _LoggedModel(model, emit, lambda: step)

        def check_memory(candidate: str) -> tuple[str, int]:
            """Enforce the bound on rendered memory, including its formatting."""
            if not isinstance(candidate, str):
                raise TypeError("memory state must be serialized text")
            text = memory.render(candidate)
            if not isinstance(text, str):
                raise TypeError("rendered memory must be text")
            # This is a bound on stored memory, not on the entire action prompt.
            count = logged.count_tokens(text)
            if not full_history and count > config.memory_token_limit:
                raise ValueError("memory component violated the token-limit contract")
            return text, count

        def update_memory(action: str, view) -> None:
            """Give the writer only prior memory and the latest public evidence."""
            nonlocal state, rendered
            previous = rendered
            context = MemoryContext(view.goal, view.budget_remaining,
                                    view.recheck_cost, config.memory_token_limit)
            # No environment handle, log, or old observations cross this boundary.
            update = memory.update(state, action, view.observation, context, logged)
            new_text, count = check_memory(update.memory)
            # Accept the replacement only after rendering and size checks pass.
            state, rendered = update.memory, new_text
            emit("memory_update", step=step, action=action,
                 previous_memory=previous, memory=rendered, memory_tokens=count,
                 validation_events=list(update.events))

        try:
            # 1. Record the planned configuration, then reset the real game.
            emit("episode_start", schema_version=1, episode_id=episode_id, kind=kind,
                 config=asdict(config), components=components,
                 source=source,
                 memory_token_limit_applies=not full_history,
                 memory_update_policy="initialize_and_after_nonterminal_actions")
            view = environment.reset(config.seed, config.game)
            reset_complete = True
            emit("reset", view=asdict(view), environment=environment.metadata)
            # 2. Initialize bounded memory from the initial recipe observation.
            # The marker labels a writer input; it is not another game action.
            state = memory.empty()
            rendered, _ = check_memory(state)
            phase = "initial_memory"
            update_memory("[INITIAL_OBSERVATION]", view)

            while True:
                # 3. Choose from the current view and memory. The actor receives
                # no accumulated conversation or access to the event log.
                step += 1
                phase = "action_generation"
                action = actor.choose_action(view, rendered, logged)
                phase = "environment_step"
                # 4. The wrapper alone executes actions, charges game-budget
                # units, and decides success/failure/budget exhaustion.
                last = environment.step(action)
                emit("action", step=step, memory_before_action=rendered,
                     transition=asdict(last))
                view = last.view
                if last.done:
                    # No later decision can use another write. This is identical
                    # across strategies and explicitly recorded in the header.
                    emit("memory_update_skipped", step=step, reason="episode_finished")
                    outcome = "completed"
                    break
                phase = "memory_update"
                # 5. Preserve useful information before the next action prompt
                # replaces this observation with whatever the next step returns.
                update_memory(last.action, view)
        except Exception as error:
            # Component exceptions are not valid gameplay losses. Interruptions
            # such as Ctrl-C propagate and can leave a trace without a result.
            error_data = {"phase": phase, "error_type": type(error).__name__,
                          "error_message": str(error)}
            emit("episode_error", step=step, **error_data)

        # 6. Summarize the run. completed includes unsuccessful games; only
        # success=True means the task was solved. Errors use success/failure=None.
        # Game budget units and inference usage remain separate measurements.
        result = {
            "schema_version": 1,
            "episode_id": episode_id,
            "kind": kind,
            "status": outcome,
            "config": asdict(config),
            "components": components,
            "source": source,
            "success": last.success if outcome == "completed" else None,
            "failure": last.failure if outcome == "completed" else None,
            "score": last.score if last else None,
            "score_raw": last.score_raw if last else None,
            # A failed reset must not report counters from an earlier episode.
            "steps": environment.steps if reset_complete else 0,
            "recipe_rechecks": environment.recipe_rechecks if reset_complete else 0,
            "budget_spent": environment.budget_spent if reset_complete else 0,
            "input_tokens": logged.input_tokens,
            "output_tokens": logged.output_tokens,
            "model_elapsed_seconds": logged.elapsed_seconds,
            "usage_complete": logged.usage_complete,
            "usage_by_purpose": logged.by_purpose,
            "runtime_seconds": time.perf_counter() - started,
            "termination_reason": last.termination_reason if outcome == "completed"
                                  else "infrastructure_error",
            "error": error_data,
        }
        emit("episode_end", result=result)

    # Close the trace before publishing the final result name. Rename avoids
    # exposing a partially written result.json to readers watching the directory.
    temporary = directory / "result.json.tmp"
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temporary.replace(directory / "result.json")
    return result
