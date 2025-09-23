from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models import BaseLLM
from pydantic import BaseModel

from ..graph.state import GraphState, Message
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AgentResponse(BaseModel):
    content: str
    next_agent: Optional[str] = None
    metadata: Dict[str, Any] = {}
    request_clarification: bool = False


class BaseAgent(ABC):
    """Base class for all agents in the MASH system"""
    
    def __init__(self, name: str, llm: BaseLLM, system_prompt: str):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.clarification_count = 0
        
    @abstractmethod
    def process(self, state: GraphState) -> GraphState:
        """Process the current state and return updated state"""
        pass
    
    def parse_agent_tags(self, content: str) -> Optional[str]:
        import re
        pattern = r'@(UrgentCare|Insurance|Coordinator):'
        match = re.search(pattern, content)
        return match.group(1) if match else None

    def format_context(self, state: GraphState) -> str:
        recent_messages = state["messages"][-5:] if len(state["messages"]) > 5 else state["messages"]
        context_parts = []

        for msg in recent_messages:
            if msg.agent and msg.agent != self.name:
                context_parts.append(f"{msg.agent}: {msg.content}")

        return "\n".join(context_parts) if context_parts else "No prior context."

    def create_message(self, content: str, state: GraphState, role: str = "assistant") -> Message:
        return Message(
            id=str(uuid.uuid4()),
            session_id=state.get("session_id", "default"),
            turn_id=state["turn_count"],
            speaker="agent",
            agent=self.name,
            role=role,
            content=content,
            timestamp=datetime.now()
        )

    def should_end_conversation(self, content: str) -> bool:
        end_markers = ["DONE", "plan confirmed", "session complete"]
        return any(marker.lower() in content.lower() for marker in end_markers)