"""Small shared contracts; model and memory modules can depend on these alone."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CookingWorldConfig:
    """Controls generated game content; wrapper prices/budgets are separate."""

    num_locations: int = 3
    num_ingredients: int = 2
    num_distractor_items: int = 0
    include_doors: bool = False
    limit_inventory_size: bool = False
    game_fold: Literal["train", "dev", "test"] = "train"

    def __post_init__(self) -> None:
        for name, low, high in (
            ("num_locations", 1, 11),
            ("num_ingredients", 1, 5),
            ("num_distractor_items", 0, 10),
        ):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer between {low} and {high}")
        if type(self.include_doors) is not bool or type(self.limit_inventory_size) is not bool:
            raise ValueError("include_doors and limit_inventory_size must be booleans")
        if self.game_fold not in {"train", "dev", "test"}:
            raise ValueError("game_fold must be train, dev, or test")

    def game_params(self) -> str:
        """Translate Python field names into the upstream engine's parameter string."""
        return ",".join((
            f"numLocations={self.num_locations}",
            f"numIngredients={self.num_ingredients}",
            f"numDistractorItems={self.num_distractor_items}",
            f"includeDoors={int(self.include_doors)}",
            f"limitInventorySize={int(self.limit_inventory_size)}",
        ))


@dataclass(frozen=True)
class AgentView:
    """The only environment fields intended for action prompts.

    observation is the current feedback, not accumulated history. The actor
    receives its bounded memory separately. Frozen fields prevent reassignment.
    """

    observation: str
    goal: str
    allowed_actions: tuple[str, ...]
    budget_remaining: int
    recheck_cost: int


@dataclass(frozen=True)
class Transition:
    """Runner/scoring record. Pass only view to the actor, not this whole record.

    valid_action means the command was permitted; executed means it actually
    reached the engine. A valid but unaffordable action is not executed/charged.
    action_cost is simulated game-budget use, not money or inference tokens.
    """

    view: AgentView
    action: str
    action_cost: int
    valid_action: bool
    executed: bool
    recipe_recheck: bool
    reward: float  # Change in engine score for this action, independent of cost.
    score: float
    score_raw: float  # Engine's unnormalized score, alongside normalized score.
    success: bool
    failure: bool
    terminated: bool  # The game itself ended in success or terminal failure.
    truncated: bool  # An action-budget or engine-move limit ended the episode.
    termination_reason: str | None

    @property
    def done(self) -> bool:
        """The runner must stop for either a game ending or an external limit."""
        return self.terminated or self.truncated
