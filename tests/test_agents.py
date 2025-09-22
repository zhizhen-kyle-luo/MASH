import pytest
from unittest.mock import MagicMock, Mock
from datetime import datetime
import uuid

from src.agents.base import BaseAgent
from src.agents.concierge import ConciergeAgent
from src.agents.urgent_care import UrgentCareAgent
from src.agents.insurance import InsuranceAgent
from src.agents.coordinator import CoordinatorAgent
from src.graph.state import GraphState, PatientCase, Message


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing"""
    llm = MagicMock()
    response = Mock()
    response.content = "Test response"
    llm.invoke.return_value = response
    return llm


@pytest.fixture
def sample_case_data():
    """Create sample patient case data"""
    return PatientCase(
        case_id="test_001",
        demographics={"age": 45, "sex": "F"},
        chief_complaint="Severe abdominal pain",
        symptoms=["Pain", "Nausea"],
        vitals={"bp": "120/80", "hr": 75},
        history=["Hypertension"],
        insurance={"plan": "Test Plan", "in_network": True},
        constraints={"prefer_morning": True},
        availability={}
    )


@pytest.fixture
def sample_state(sample_case_data):
    """Create a sample GraphState"""
    return {
        "messages": [],
        "case_data": sample_case_data,
        "current_agent": "test",
        "next_agent": None,
        "turn_count": 0,
        "max_turns": 10,
        "workflow_status": "active",
        "current_plan": None,
        "internal_context": {},
        "session_id": str(uuid.uuid4())
    }


class TestBaseAgent:
    def test_parse_agent_tags(self, mock_llm):
        agent = ConciergeAgent(mock_llm)
        
        # Test valid tags
        assert agent.parse_agent_tags("@UrgentCare: Please evaluate") == "UrgentCare"
        assert agent.parse_agent_tags("@Insurance: Check coverage") == "Insurance"
        assert agent.parse_agent_tags("@Coordinator: Schedule appointment") == "Coordinator"
        
        # Test no tag
        assert agent.parse_agent_tags("No tag here") is None
    
    def test_should_end_conversation(self, mock_llm):
        agent = ConciergeAgent(mock_llm)
        
        assert agent.should_end_conversation("The plan is DONE")
        assert agent.should_end_conversation("Plan confirmed with patient")
        assert agent.should_end_conversation("Session complete")
        assert not agent.should_end_conversation("Still working on it")


class TestConciergeAgent:
    def test_process_initial(self, mock_llm, sample_state):
        mock_llm.invoke.return_value.content = "Hello! I understand you have abdominal pain. @UrgentCare: Please evaluate."
        
        agent = ConciergeAgent(mock_llm)
        result = agent.process(sample_state)
        
        assert result["turn_count"] == 1
        assert result["next_agent"] == "UrgentCare"
        assert len(result["messages"]) == 1
        assert result["messages"][0].agent == "Concierge"
    
    def test_process_marks_done(self, mock_llm, sample_state):
        mock_llm.invoke.return_value.content = "Your plan is confirmed. Session DONE."
        
        agent = ConciergeAgent(mock_llm)
        result = agent.process(sample_state)
        
        assert result["workflow_status"] == "done"


class TestUrgentCareAgent:
    def test_process_workup(self, mock_llm, sample_state):
        # Add a request message
        sample_state["messages"].append(
            Message(
                id=str(uuid.uuid4()),
                session_id=sample_state["session_id"],
                turn_id=0,
                speaker="agent",
                agent="Concierge",
                role="assistant",
                content="@UrgentCare: What's the initial workup?",
                timestamp=datetime.now()
            )
        )
        
        mock_llm.invoke.return_value.content = "Recommend: CT scan and blood work for abdominal pain evaluation."
        
        agent = UrgentCareAgent(mock_llm)
        result = agent.process(sample_state)
        
        assert result["next_agent"] == "Concierge"
        assert "workup_recommendations" in result["internal_context"]


class TestInsuranceAgent:
    def test_process_approval(self, mock_llm, sample_state):
        sample_state["internal_context"]["workup_recommendations"] = "CT scan recommended"
        sample_state["messages"].append(
            Message(
                id=str(uuid.uuid4()),
                session_id=sample_state["session_id"],
                turn_id=0,
                speaker="agent",
                agent="Concierge",
                role="assistant",
                content="@Insurance: Coverage for CT scan?",
                timestamp=datetime.now()
            )
        )
        
        mock_llm.invoke.return_value.content = "Decision: Approved\nReason: In-network provider"
        
        agent = InsuranceAgent(mock_llm)
        result = agent.process(sample_state)
        
        assert result["next_agent"] == "Concierge"
        assert result["internal_context"]["insurance_decision"] == "Approved"
    
    def test_extract_study_type(self, mock_llm):
        agent = InsuranceAgent(mock_llm)
        
        assert agent._extract_study_type("Need a CT scan") == "CT"
        assert agent._extract_study_type("Ultrasound required") == "Ultrasound"
        assert agent._extract_study_type("MRI of the brain") == "MRI"
        assert agent._extract_study_type("Blood work needed") == "Labs"


class TestCoordinatorAgent:
    def test_process_scheduling(self, mock_llm, sample_state):
        sample_state["internal_context"]["workup_recommendations"] = "CT scan"
        sample_state["internal_context"]["insurance_decision"] = "Approved"
        sample_state["messages"].append(
            Message(
                id=str(uuid.uuid4()),
                session_id=sample_state["session_id"],
                turn_id=0,
                speaker="agent",
                agent="Concierge",
                role="assistant",
                content="@Coordinator: Schedule CT scan",
                timestamp=datetime.now()
            )
        )
        
        mock_llm.invoke.return_value.content = "Available: Tomorrow at 09:00 for CT scan"
        
        agent = CoordinatorAgent(mock_llm)
        result = agent.process(sample_state)
        
        assert result["next_agent"] == "Concierge"
        assert "scheduled_appointment" in result["internal_context"]