from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from .base import BaseAgent
from ..graph.state import GraphState
from ..utils.logger import get_logger

logger = get_logger(__name__)


CONCIERGE_PROMPT = """You are the front-desk care navigator for a healthcare system.

Your responsibilities:
1. Greet the user warmly and capture their chief complaint
2. Ask AT MOST one clarifying question if absolutely necessary
3. Summarize what the user said clearly
4. Request help from back-office agents using lines that begin with @AgentName: followed by a concrete request
5. Merge internal replies into one clear, patient-friendly message
6. Mark the session as DONE when the plan is confirmed

Available agents to coordinate with:
- @UrgentCare: For clinical evaluation and workup recommendations
- @Insurance: For coverage and authorization questions  
- @Coordinator: For scheduling and appointment availability

Guidelines:
- Be concise and empathetic
- Never contradict earlier facts
- Always maintain patient context
- Present final plans in simple, actionable terms
"""


class ConciergeAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(name="Concierge", llm=llm, system_prompt=CONCIERGE_PROMPT)
        
    def process(self, state: GraphState) -> GraphState:
        context = self.format_context(state)
        case_data = state["case_data"]
        
        # Build conversation for LLM
        messages = [SystemMessage(content=self.system_prompt)]
        
        # Add case context if this is not the first turn
        if state["turn_count"] > 0:
            case_summary = f"""
            Patient Information:
            - Demographics: {case_data.demographics.get('age')}yo {case_data.demographics.get('sex')}
            - Chief Complaint: {case_data.chief_complaint}
            - Symptoms: {', '.join(case_data.symptoms)}
            - Insurance: {case_data.insurance.get('plan')} ({'in-network' if case_data.insurance.get('in_network') else 'out-of-network'})
            
            Recent Context:
            {context}
            """
            messages.append(SystemMessage(content=case_summary))
        
        # Add recent conversation
        for msg in state["messages"][-3:]:
            if msg.speaker == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.agent == self.name:
                messages.append(SystemMessage(content=f"Your previous response: {msg.content}"))
            else:
                messages.append(SystemMessage(content=f"{msg.agent}: {msg.content}"))
        
        # Get response from LLM
        response = self.llm.invoke(messages)
        content = response.content
        
        # Check for agent routing
        next_agent = self.parse_agent_tags(content)
        
        # Create and add message
        message = self.create_message(content, state)
        state["messages"].append(message)
        
        # Update state
        state["current_agent"] = self.name
        state["next_agent"] = next_agent
        state["turn_count"] += 1
        
        # Check if conversation should end
        if self.should_end_conversation(content) or state["turn_count"] >= state["max_turns"]:
            state["workflow_status"] = "done"
            
        logger.info(f"Concierge processed turn {state['turn_count']}, routing to: {next_agent}")
        
        return state