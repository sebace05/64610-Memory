"""Shared interfaces for independent actor, model, and memory implementations.

Protocols describe required methods; implementations need not inherit from them.
Frozen dataclasses carry the inputs/outputs shared across module boundaries.
"""

from dataclasses import dataclass, field
import math
from typing import Protocol, Sequence

from .contracts import AgentView


@dataclass(frozen=True)
class Message:
    """One role/content message sent in a single model request."""

    role: str
    content: str


@dataclass(frozen=True)
class Generation:
    """One response plus its reported usage; elapsed time is for that call only."""

    text: str
    input_tokens: int
    output_tokens: int
    elapsed_seconds: float
    # Optional backend evidence, e.g. finish reason and peak CUDA allocation.
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Reject invalid usage records before they corrupt episode totals.
        if not isinstance(self.text, str):
            raise TypeError("generation text must be a string")
        for count in (self.input_tokens, self.output_tokens):
            if type(count) is not int or count < 0:
                raise ValueError("token counts must be nonnegative integers")
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be finite and nonnegative")


class Model(Protocol):
    """Liam's backend implements generation, token counting, and run metadata."""

    @property
    def metadata(self) -> dict:
        """JSON-compatible identity/settings; include is_fake explicitly."""
        ...

    def generate(self, messages: Sequence[Message], *, purpose: str) -> Generation:
        """Use only these messages; purpose labels acting/writing/repair usage."""
        ...

    def count_tokens(self, text: str) -> int:
        """Count exact rendered memory without adding chat-template tokens."""
        ...


@dataclass(frozen=True)
class MemoryContext:
    """Public task settings for the writer; no scores, game object, or history."""

    goal: str
    budget_remaining: int
    recheck_cost: int
    memory_token_limit: int


@dataclass(frozen=True)
class MemoryUpdate:
    """Replacement state plus audit events, such as repair or fallback details."""

    # State is serialized text. Strategies may parse it internally to edit JSON.
    memory: str
    events: tuple[str, ...] = ()  # Logger-only details; not extra actor memory.


class MemoryStrategy(Protocol):
    """Pablo's strategies implement the same contract, regardless of format."""

    @property
    def metadata(self) -> dict:
        """Include strategy (prose/structured/hybrid), version, and is_fake."""
        ...

    def empty(self) -> str:
        """Return a fresh starting state; never reuse the previous game's state."""
        ...

    def update(
        self, previous_memory: str, action: str, observation: str,
        context: MemoryContext, model: Model,
    ) -> MemoryUpdate:
        """Rewrite from the prior state and latest evidence; handle repair here."""
        ...

    def render(self, memory: str) -> str:
        """Include every separator/JSON character the actor will actually see."""
        ...


class Actor(Protocol):
    """Choose an action from the approved view and rendered bounded memory."""

    @property
    def metadata(self) -> dict: ...

    def choose_action(self, view: AgentView, memory: str, model: Model) -> str: ...
