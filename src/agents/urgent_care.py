from .base import BaseAgent
from ..graph.state import GraphState
from ..utils.logger import get_logger
from langchain_core.messages import SystemMessage, HumanMessage

logger = get_logger(__name__)


URGENT_CARE_PROMPT = """You are a clinician doing initial evaluation in an urgent care setting.

Your responsibilities:
1. Propose minimal, safe initial work-up (≤2 options) with one-line rationale
2. Use vitals/history already provided in the case data - don't ask the user for them again
3. Stay concise - one reply per request
4. Focus on immediate assessment needs

Guidelines:
- Consider both lab work and imaging when appropriate
- Provide clear clinical reasoning
- Be decisive but safe in recommendations
- Format: "Recommend: [test/imaging] because [brief rationale]"
"""


class UrgentCareAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(name="UrgentCare", llm=llm, system_prompt=URGENT_CARE_PROMPT)
        
    def process(self, state: GraphState) -> GraphState:
        case_data = state["case_data"]
        
        # Extract the request from Concierge
        recent_request = None
        for msg in reversed(state["messages"]):
            if "@UrgentCare:" in msg.content:
                recent_request = msg.content.split("@UrgentCare:")[1].strip()
                break
        
        if not recent_request:
            recent_request = "Please provide initial workup recommendations"
        
        # Build context
        clinical_context = f"""
        Patient: {case_data.demographics.get('age')}yo {case_data.demographics.get('sex')}
        Chief Complaint: {case_data.chief_complaint}
        Symptoms: {', '.join(case_data.symptoms)}
        Vitals: {case_data.vitals}
        History: {', '.join(case_data.history) if case_data.history else 'No significant history'}
        
        Request: {recent_request}
        """
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=clinical_context)
        ]
        
        response = self.llm.invoke(messages)
        content = response.content
        
        # Create message and update state
        message = self.create_message(content, state)
        state["messages"].append(message)
        
        # Route back to Concierge
        state["current_agent"] = self.name
        state["next_agent"] = "Concierge"
        state["turn_count"] += 1
        
        # Store workup recommendations in internal context
        state["internal_context"]["workup_recommendations"] = content
        
        logger.info(f"UrgentCare provided workup recommendations at turn {state['turn_count']}")
        
        return state