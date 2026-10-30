"""Small shared contracts; model and memory modules can depend on these alone."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CookingWorldConfig:
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
        return ",".join((
            f"numLocations={self.num_locations}",
            f"numIngredients={self.num_ingredients}",
            f"numDistractorItems={self.num_distractor_items}",
            f"includeDoors={int(self.include_doors)}",
            f"limitInventorySize={int(self.limit_inventory_size)}",
        ))


@dataclass(frozen=True)
class AgentView:
    """The only environment fields intended for action prompts."""

    observation: str
    goal: str
    allowed_actions: tuple[str, ...]
    budget_remaining: int
    recheck_cost: int


@dataclass(frozen=True)
class Transition:
    """Runner/scoring record. Pass only view to the actor, not this whole record."""

    view: AgentView
    action: str
    action_cost: int
    valid_action: bool
    executed: bool
    recipe_recheck: bool
    reward: float
    score: float
    score_raw: float
    success: bool
    failure: bool
    terminated: bool
    truncated: bool
    termination_reason: str | None

    @property
    def done(self) -> bool:
        return self.terminated or self.truncated
