"""CookingWorld adapter with experiment costs independent of engine scoring."""

from dataclasses import asdict
from importlib.metadata import version

from .contracts import AgentView, CookingWorldConfig, Transition


# Both legal engine commands disclose the same full recipe (verified in v1.1.0).
RECIPE_ACTIONS = frozenset({"read cookbook", "examine cookbook"})


def normalize_action(action: str) -> str:
    if not isinstance(action, str):
        raise TypeError("action must be a string")
    return " ".join(action.lower().split())


class CookingWorldEnvironment:
    """One isolated game at a time; use as a context manager to close Java."""

    def __init__(self, *, recheck_cost: int = 2, action_budget: int = 80) -> None:
        if type(recheck_cost) is not int or recheck_cost not in {2, 5}:
            raise ValueError("recheck_cost must be 2 or 5")
        if type(action_budget) is not int or not 1 <= action_budget <= 1_000_000:
            raise ValueError("action_budget must be an integer between 1 and 1000000")
        self.recheck_cost = recheck_cost
        self.action_budget = action_budget
        self._backend = None
        self._view: AgentView | None = None
        self._info: dict = {}
        self._config = CookingWorldConfig()
        self._seed: int | None = None
        self._done = False
        self._closed = False
        self._initial_recipe = ""
        self.steps = 0
        self.recipe_rechecks = 0
        self.budget_spent = 0

    def __enter__(self) -> "CookingWorldEnvironment":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self._backend is not None:
                self._backend.close()

    @property
    def view(self) -> AgentView:
        if self._closed:
            raise RuntimeError("environment is closed")
        if self._view is None:
            raise RuntimeError("call reset before requesting a view or taking an action")
        return self._view

    @property
    def metadata(self) -> dict:
        """Reproduction metadata for the logger, not an actor prompt."""
        self.view
        return {
            "schema_version": 1,
            "environment": "cookingworld",
            "textworld_express_version": version("textworld-express"),
            "seed": self._seed,
            "game_config": asdict(self._config),
            "game_params": self._config.game_params(),
            "recheck_cost": self.recheck_cost,
            "action_budget": self.action_budget,
            "initial_recipe_action": "read cookbook",
            "initial_recipe_cost": 0,
            "charged_recipe_actions": sorted(RECIPE_ACTIONS),
            "generate_gold_path": False,
        }

    def reset(
        self, seed: int, game_config: CookingWorldConfig | None = None
    ) -> AgentView:
        if self._closed:
            raise RuntimeError("environment is closed")
        if type(seed) is not int or not 0 <= seed <= 2_147_483_647:
            raise ValueError("seed must be an integer between 0 and 2147483647")
        config = game_config if game_config is not None else CookingWorldConfig()
        if not isinstance(config, CookingWorldConfig):
            raise TypeError("game_config must be a CookingWorldConfig")
        if self._backend is None:
            from textworld_express import TextWorldExpressEnv

            # Our positive action costs exhaust the wrapper budget before this
            # engine move cap; the extra room includes the initial free read.
            self._backend = TextWorldExpressEnv(envStepLimit=self.action_budget + 2)

        # A failed reset must not leave a previous episode available to step().
        self._view = None
        observation, info = self._backend.reset(
            seed=seed,
            gameFold=config.game_fold,
            gameName="cookingworld",
            gameParams=config.game_params(),
            generateGoldPath=False,
        )
        if "read cookbook" not in info["validActions"]:
            raise RuntimeError("reset must start with an accessible cookbook; no hidden navigation is used")
        recipe, _, done, info = self._backend.step("read cookbook")
        if done or info["tasksuccess"] or info["taskfailure"]:
            raise RuntimeError("initial recipe reading unexpectedly ended the game")

        self._config, self._seed = config, seed
        self._info = dict(info)
        self._initial_recipe = recipe
        self.steps = self.recipe_rechecks = self.budget_spent = 0
        self._done = False
        initial = f"{observation}\nInitial recipe (provided once at reset):\n{recipe}"
        self._view = self._make_view(initial)
        return self._view

    def _make_view(self, observation: str) -> AgentView:
        return AgentView(
            observation=observation,
            goal=self._info["taskDescription"],
            allowed_actions=() if self._done else tuple(sorted(self._info["validActions"])),
            budget_remaining=self.action_budget - self.budget_spent,
            recheck_cost=self.recheck_cost,
        )

    def step(self, action: str) -> Transition:
        previous = self.view
        if self._done:
            raise RuntimeError("episode is finished; call reset before another action")
        action = normalize_action(action)
        # Canonicalize against actual legal commands; an inaccessible cookbook
        # does not turn an unsuccessful read attempt into paid information access.
        legal = {normalize_action(a): a for a in previous.allowed_actions}
        valid = action in legal
        canonical = legal.get(action, action)
        recipe_action = valid and action in RECIPE_ACTIONS
        required_cost = self.recheck_cost if recipe_action else 1
        reward = 0.0
        executed = False
        charged = 0
        self.steps += 1

        if required_cost > previous.budget_remaining:
            observation = "Insufficient remaining budget for this action."
            terminated, truncated, reason = False, True, "budget_exhaustion"
        else:
            charged = required_cost
            if valid:
                observation, reward, engine_done, info = self._backend.step(canonical)
                self._info = dict(info)
                executed = True
                self.recipe_rechecks += int(recipe_action)
            else:
                # Do not advance the simulator or substitute a legal action.
                observation = "Invalid action. Choose one of the permitted actions."
                engine_done = False
            self.budget_spent += charged
            success = bool(self._info["tasksuccess"]) or self._info["score"] >= 1.0
            failure = bool(self._info["taskfailure"])
            terminated = success or failure
            truncated = False
            reason = "success" if success else "terminal_failure" if failure else None
            if not terminated and engine_done:
                truncated, reason = True, "engine_step_limit"
            elif not terminated and self.budget_spent == self.action_budget:
                truncated, reason = True, "budget_exhaustion"

        success = bool(self._info["tasksuccess"]) or self._info["score"] >= 1.0
        failure = bool(self._info["taskfailure"])
        self._done = terminated or truncated
        self._view = self._make_view(observation)
        return Transition(
            view=self._view,
            action=canonical,
            action_cost=charged,
            valid_action=valid,
            executed=executed,
            recipe_recheck=executed and recipe_action,
            reward=float(reward),
            score=float(self._info["score"]),
            score_raw=float(self._info["scoreRaw"]),
            success=success,
            failure=failure,
            terminated=terminated,
            truncated=truncated,
            termination_reason=reason,
        )
