from typing import TypedDict, List, Dict, Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class Message(BaseModel):
    """Single message in the conversation"""
    id: str
    session_id: str
    turn_id: int
    speaker: Literal["user", "agent"]
    agent: Optional[Literal["Concierge", "UrgentCare", "Insurance", "Coordinator"]] = None
    role: Literal["system", "assistant", "user"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PatientCase(BaseModel):
    """Patient case data structure"""
    case_id: str
    demographics: Dict[str, Any]
    chief_complaint: str
    symptoms: List[str]
    vitals: Dict[str, Any]
    history: List[str]
    insurance: Dict[str, Any]
    constraints: Dict[str, Any] = Field(default_factory=dict)
    availability: Dict[str, List[str]] = Field(default_factory=dict)


class GraphState(TypedDict):
    """State passed between nodes in the graph"""
    messages: List[Message]
    case_data: PatientCase
    current_agent: str
    next_agent: Optional[str]
    turn_count: int
    max_turns: int
    workflow_status: Literal["active", "done", "error"]
    current_plan: Optional[Dict[str, Any]]
    internal_context: Dict[str, Any]  # For agent-to-agent context sharing