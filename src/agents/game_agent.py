from abc import ABC, abstractmethod
from typing import Dict, Any
from src.models.schemas import GameState


class GameAgent(ABC):
    """Abstract base class for all game agents."""

    def __init__(self, llm, agent_name: str, config: Dict[str, Any] = None):
        self.llm = llm
        self.agent_name = agent_name
        self.config = config or {}

    @abstractmethod
    def make_decision(self, state: GameState) -> Dict[str, Any]:
        """Make strategic decision based on game state."""
        pass

    @abstractmethod
    def calculate_payoff(self, state: GameState) -> float:
        """Calculate utility/payoff from game outcome."""
        pass

    @abstractmethod
    def calculate_metrics(self, state: GameState) -> Dict[str, float]:
        """Calculate agent-specific metrics."""
        pass
