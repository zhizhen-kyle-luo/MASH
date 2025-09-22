from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_core.runnables import RunnableConfig
import os
from dotenv import load_dotenv

from .state import GraphState
from ..agents.concierge import ConciergeAgent
from ..agents.urgent_care import UrgentCareAgent
from ..agents.insurance import InsuranceAgent
from ..agents.coordinator import CoordinatorAgent
from ..utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


class MASHWorkflow:
    """Main workflow orchestrator for the MASH system"""
    
    def __init__(self, llm=None, max_turns: int = 12):
        self.max_turns = max_turns
        self.llm = llm or self._initialize_llm()
        self.agents = self._initialize_agents()
        self.graph = self._build_graph()
        
    def _initialize_llm(self):
        """Initialize the LLM based on environment configuration"""
        if os.getenv("AZURE_OPENAI_API_KEY"):
            return AzureChatOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
                temperature=0.7,
                max_tokens=500
            )
        elif os.getenv("OPENAI_API_KEY"):
            return ChatOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
                temperature=0.7,
                max_tokens=500
            )
        else:
            raise ValueError("No LLM configuration found. Please set Azure OpenAI or OpenAI credentials.")
    
    def _initialize_agents(self) -> Dict[str, Any]:
        """Initialize all agents with the shared LLM"""
        return {
            "Concierge": ConciergeAgent(self.llm),
            "UrgentCare": UrgentCareAgent(self.llm),
            "Insurance": InsuranceAgent(self.llm),
            "Coordinator": CoordinatorAgent(self.llm)
        }
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(GraphState)
        
        # Add nodes for each agent
        for agent_name, agent in self.agents.items():
            workflow.add_node(agent_name, agent.process)
        
        # Add supervisor node for routing decisions
        workflow.add_node("supervisor", self._supervisor)
        
        # Set entry point
        workflow.set_entry_point("supervisor")
        
        # Add conditional edges from supervisor to agents
        workflow.add_conditional_edges(
            "supervisor",
            self._route_from_supervisor,
            {
                "Concierge": "Concierge",
                "UrgentCare": "UrgentCare",
                "Insurance": "Insurance",
                "Coordinator": "Coordinator",
                "END": END
            }
        )
        
        # Add edges from agents back to supervisor
        for agent_name in self.agents.keys():
            workflow.add_edge(agent_name, "supervisor")
        
        return workflow.compile()
    
    def _supervisor(self, state: GraphState) -> GraphState:
        """Supervisor node that determines routing"""
        # Check if we should end
        if state["workflow_status"] == "done" or state["turn_count"] >= self.max_turns:
            logger.info(f"Workflow ending: status={state['workflow_status']}, turns={state['turn_count']}")
            return state
        
        # Initial routing or continue based on next_agent
        if state["turn_count"] == 0:
            state["next_agent"] = "Concierge"
        elif state["next_agent"] is None:
            # Default back to Concierge if no specific routing
            state["next_agent"] = "Concierge"
            
        logger.info(f"Supervisor routing to: {state['next_agent']} at turn {state['turn_count']}")
        return state
    
    def _route_from_supervisor(self, state: GraphState) -> str:
        """Determine which node to route to from supervisor"""
        if state["workflow_status"] == "done" or state["turn_count"] >= self.max_turns:
            return "END"
        
        next_agent = state.get("next_agent", "Concierge")
        
        # Validate agent exists
        if next_agent not in self.agents:
            logger.warning(f"Unknown agent requested: {next_agent}, defaulting to Concierge")
            return "Concierge"
            
        return next_agent
    
    async def arun(self, initial_state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
        """Run the workflow asynchronously"""
        result = await self.graph.ainvoke(initial_state, config)
        return result
    
    def run(self, initial_state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
        """Run the workflow synchronously"""
        result = self.graph.invoke(initial_state, config)
        return result