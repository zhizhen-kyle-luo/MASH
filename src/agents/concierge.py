from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from .base import BaseAgent
from ..graph.state import GraphState
from ..models.schemas import ClinicalSummary
from ..utils.logger import get_logger

logger = get_logger(__name__)


CONCIERGE_PROMPT = """You are a healthcare care navigator and conversational AI assistant.

Your responsibilities:
1. Engage in natural conversation with patients to understand their healthcare needs
2. Ask follow-up questions to gather necessary information for clinical assessment
3. Generate clinical summaries for specialist agents based on conversation
4. Coordinate with back-office agents using @AgentName: requests
5. Present final care plans in patient-friendly language

Available agents to coordinate with:
- @UrgentCare: For clinical evaluation and workup recommendations
- @Insurance: For coverage and authorization questions
- @Coordinator: For scheduling and appointment availability

Conversation Guidelines:
- Be empathetic and professional
- Ask one question at a time
- Gather: chief complaint, symptom duration/severity, relevant history
- Don't overwhelm patients with too many questions
- Generate clear clinical summaries for specialists
- Mark session as DONE when care plan is complete

When you have enough information, generate a clinical summary and route to appropriate specialists."""


CLINICAL_SUMMARY_PROMPT = """Based on the conversation history, generate a concise clinical summary for specialist agents.

Include:
- Chief complaint
- Key symptoms and timeline
- Relevant patient factors
- Urgency assessment

Format as professional clinical narrative suitable for specialist review."""


class ConciergeAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(name="Concierge", llm=llm, system_prompt=CONCIERGE_PROMPT)

    def process(self, state: GraphState) -> GraphState:
        # Debug: Check if we have clinical summary
        has_summary = bool(state.get("clinical_summary"))
        print(f"DEBUG: Concierge process - has_clinical_summary: {has_summary}")

        # Handle conversational interaction vs specialist coordination
        if not has_summary:
            print("DEBUG: Using conversational mode")
            return self._handle_conversation(state)
        else:
            print("DEBUG: Using specialist coordination mode")
            return self._coordinate_with_specialists(state)

    def _handle_conversation(self, state: GraphState) -> GraphState:
        """Handle conversational interaction with patient"""
        conversation_history = state.get("conversation_history", [])

        messages = [SystemMessage(content=self.system_prompt)]

        # Add conversation context
        if conversation_history:
            context = "\n".join(conversation_history[-6:])  # Last 6 exchanges
            messages.append(SystemMessage(content=f"Previous conversation:\n{context}"))

        # Add latest patient message
        if state["messages"]:
            latest_msg = state["messages"][-1]
            if latest_msg.speaker == "user":
                messages.append(HumanMessage(content=latest_msg.content))
                conversation_history.append(f"Patient: {latest_msg.content}")

        response = self.llm.invoke(messages)
        content = response.content

        # Add assistant response to conversation history
        conversation_history.append(f"Concierge: {content}")
        state["conversation_history"] = conversation_history

        # Create and add the main response message
        message = self.create_message(content, state)
        state["messages"].append(message)

        # Check if we have enough information to generate clinical summary
        if self._should_generate_summary(conversation_history):
            clinical_summary = self._generate_clinical_summary(state)
            state["clinical_summary"] = clinical_summary

            # Don't start routing yet - let the script handle transition
            state["next_agent"] = None

            # Add a transition message
            transition_message = self.create_message(
                "Thank you for providing that information. I'm now going to coordinate with our medical team to develop a care plan for you.",
                state
            )
            state["messages"].append(transition_message)
        else:
            # Continue conversation
            state["next_agent"] = None
        state["current_agent"] = self.name
        state["turn_count"] += 1

        logger.info(f"Concierge conversation turn {state['turn_count']}")
        return state

    def _coordinate_with_specialists(self, state: GraphState) -> GraphState:
        """Coordinate with specialist agents using clinical summary"""
        context = self.format_context(state)
        clinical_summary = state.get("clinical_summary")
        patient_ehr = state.get("patient_ehr")

        messages = [SystemMessage(content=self.system_prompt)]

        # Add clinical summary and EHR context
        if clinical_summary and patient_ehr:
            summary_context = f"""
            You have generated a clinical summary and are now coordinating with specialists.

            Clinical Summary: {clinical_summary.summary}
            Patient: {patient_ehr.demographics.get('age', 'Unknown')}yo {patient_ehr.demographics.get('sex', 'Unknown')}
            Insurance: {patient_ehr.insurance.get('plan', 'Unknown')} ({'in-network' if patient_ehr.insurance.get('in_network') else 'out-of-network'})

            Recent specialist responses:
            {context}

            Your task:
            1. If this is the first specialist interaction, request clinical evaluation: "@UrgentCare: Please provide workup recommendations"
            2. After UrgentCare responds, check insurance: "@Insurance: Coverage for proposed studies"
            3. After Insurance responds, check scheduling: "@Coordinator: Find earliest available appointments"
            4. After all specialists respond, present final care plan and mark as DONE.
            """
            print(f"DEBUG: Adding summary context to messages")
            messages.append(SystemMessage(content=summary_context))
        else:
            print(f"DEBUG: No clinical summary or patient EHR - using basic context")
            messages.append(SystemMessage(content=f"Recent context: {context}"))

        # Add recent messages
        for msg in state["messages"][-3:]:
            if msg.speaker == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.agent == self.name:
                messages.append(SystemMessage(content=f"Your previous response: {msg.content}"))
            else:
                messages.append(SystemMessage(content=f"{msg.agent}: {msg.content}"))

        response = self.llm.invoke(messages)
        content = response.content

        next_agent = self.parse_agent_tags(content)

        message = self.create_message(content, state)
        state["messages"].append(message)

        state["current_agent"] = self.name
        state["next_agent"] = next_agent
        state["turn_count"] += 1

        if self.should_end_conversation(content) or state["turn_count"] >= state["max_turns"]:
            state["workflow_status"] = "done"

        print(f"DEBUG: Concierge specialist response: {content[:200]}...")
        print(f"DEBUG: Parsed next_agent: {next_agent}")
        logger.info(f"Concierge specialist coordination turn {state['turn_count']}, routing to: {next_agent}")
        return state

    def _should_generate_summary(self, conversation_history: list) -> bool:
        """Determine if we have enough information to generate clinical summary"""
        conversation_text = " ".join(conversation_history).lower()

        # Basic heuristics - could be improved with NLP
        has_complaint = any(word in conversation_text for word in ["pain", "hurt", "feel", "symptom", "problem"])
        has_duration = any(word in conversation_text for word in ["day", "week", "hour", "since", "ago"])
        has_enough_exchanges = len(conversation_history) >= 4  # At least 2 back-and-forth

        return has_complaint and (has_duration or has_enough_exchanges)

    def _generate_clinical_summary(self, state: GraphState) -> ClinicalSummary:
        """Generate clinical summary from conversation history"""
        conversation_history = state.get("conversation_history", [])
        patient_ehr = state.get("patient_ehr")

        conversation_text = "\n".join(conversation_history)

        messages = [
            SystemMessage(content=CLINICAL_SUMMARY_PROMPT),
            HumanMessage(content=f"Conversation:\n{conversation_text}")
        ]

        response = self.llm.invoke(messages)
        summary_content = response.content

        # Extract chief complaint from conversation (simple approach)
        chief_complaint = self._extract_chief_complaint(conversation_history)
        presenting_symptoms = self._extract_symptoms(conversation_history)
        urgency = self._assess_urgency(conversation_history)

        return ClinicalSummary(
            patient_id=patient_ehr.patient_id if patient_ehr else "unknown",
            summary=summary_content,
            chief_complaint=chief_complaint,
            presenting_symptoms=presenting_symptoms,
            urgency_level=urgency
        )

    def _extract_chief_complaint(self, conversation_history: list) -> str:
        """Extract chief complaint from conversation"""
        # Simple extraction - look for first patient statement
        for line in conversation_history:
            if line.startswith("Patient:"):
                return line.replace("Patient:", "").strip()
        return "Patient seeking medical evaluation"

    def _extract_symptoms(self, conversation_history: list) -> str:
        """Extract symptom narrative from conversation"""
        patient_statements = [line for line in conversation_history if line.startswith("Patient:")]
        return " ".join([stmt.replace("Patient:", "").strip() for stmt in patient_statements])

    def _assess_urgency(self, conversation_history: list) -> str:
        """Simple urgency assessment based on keywords"""
        conversation_text = " ".join(conversation_history).lower()

        emergent_keywords = ["severe", "chest pain", "trouble breathing", "bleeding", "emergency"]
        urgent_keywords = ["worsening", "getting worse", "concerned", "worried", "urgent"]

        if any(word in conversation_text for word in emergent_keywords):
            return "emergent"
        elif any(word in conversation_text for word in urgent_keywords):
            return "urgent"
        else:
            return "routine"