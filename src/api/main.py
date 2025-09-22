from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime
import json
from pathlib import Path

from ..graph.workflow import MASHWorkflow
from ..graph.state import GraphState, PatientCase, Message
from ..utils.logger import get_logger, TranscriptLogger

app = FastAPI(
    title="MASH Healthcare System",
    description="Multi-Agent System for Healthcare - Initial Presentation and Evaluation",
    version="0.1.0"
)

logger = get_logger(__name__)

# Global workflow instance
workflow = None


class ConsultationRequest(BaseModel):
    """Request model for starting a consultation"""
    case_file: Optional[str] = Field(None, description="Path to case JSON file")
    case_data: Optional[Dict[str, Any]] = Field(None, description="Direct case data")
    chief_complaint: Optional[str] = Field(None, description="Chief complaint if not in case data")
    session_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))


class ConsultationResponse(BaseModel):
    """Response model for consultation"""
    session_id: str
    status: str
    final_plan: Optional[Dict[str, Any]]
    transcript: List[Dict[str, Any]]
    turn_count: int
    workflow_status: str


@app.on_event("startup")
async def startup_event():
    """Initialize the workflow on startup"""
    global workflow
    workflow = MASHWorkflow()
    logger.info("MASH workflow initialized")


@app.get("/")
async def root():
    return {
        "service": "MASH Healthcare System",
        "version": "0.1.0",
        "status": "operational",
        "endpoints": {
            "consultation": "/consultation",
            "health": "/health",
            "transcript": "/transcript/{session_id}"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/consultation", response_model=ConsultationResponse)
async def start_consultation(
    request: ConsultationRequest,
    background_tasks: BackgroundTasks
):
    """Start a new consultation workflow"""
    try:
        # Load case data
        if request.case_file:
            case_path = Path(request.case_file)
            if not case_path.exists():
                raise HTTPException(status_code=404, detail=f"Case file not found: {request.case_file}")
            
            with open(case_path, 'r') as f:
                case_data = json.load(f)
        elif request.case_data:
            case_data = request.case_data
        else:
            # Create minimal case from chief complaint
            case_data = {
                "case_id": f"auto_{request.session_id[:8]}",
                "demographics": {"age": 40, "sex": "U"},
                "chief_complaint": request.chief_complaint or "General consultation",
                "symptoms": [],
                "vitals": {},
                "history": [],
                "insurance": {"plan": "Standard", "in_network": True},
                "constraints": {},
                "availability": {}
            }
        
        # Create patient case
        patient_case = PatientCase(**case_data)
        
        # Initialize state
        initial_state: GraphState = {
            "messages": [],
            "case_data": patient_case,
            "current_agent": "supervisor",
            "next_agent": None,
            "turn_count": 0,
            "max_turns": workflow.max_turns,
            "workflow_status": "active",
            "current_plan": None,
            "internal_context": {},
            "session_id": request.session_id
        }
        
        # Add initial user message with chief complaint
        initial_message = Message(
            id=str(uuid.uuid4()),
            session_id=request.session_id,
            turn_id=0,
            speaker="user",
            role="user",
            content=patient_case.chief_complaint,
            timestamp=datetime.now()
        )
        initial_state["messages"].append(initial_message)
        
        # Initialize transcript logger
        transcript_logger = TranscriptLogger(request.session_id)
        
        # Run workflow
        logger.info(f"Starting consultation for session {request.session_id}")
        final_state = workflow.run(initial_state)
        
        # Log all messages to transcript
        for msg in final_state["messages"]:
            transcript_logger.log_message(msg.dict())
        
        # Prepare response
        transcript = [msg.dict() for msg in final_state["messages"]]
        
        # Extract final plan from last Concierge message
        final_plan = None
        for msg in reversed(final_state["messages"]):
            if msg.agent == "Concierge" and any(
                keyword in msg.content.lower() 
                for keyword in ["plan", "recommend", "schedule", "next step"]
            ):
                final_plan = {
                    "summary": msg.content,
                    "workup": final_state["internal_context"].get("workup_recommendations"),
                    "insurance": final_state["internal_context"].get("insurance_decision"),
                    "appointment": final_state["internal_context"].get("scheduled_appointment")
                }
                break
        
        return ConsultationResponse(
            session_id=request.session_id,
            status="completed",
            final_plan=final_plan,
            transcript=transcript,
            turn_count=final_state["turn_count"],
            workflow_status=final_state["workflow_status"]
        )
        
    except Exception as e:
        logger.error(f"Consultation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transcript/{session_id}")
async def get_transcript(session_id: str):
    """Retrieve a session transcript"""
    transcript_logger = TranscriptLogger(session_id)
    transcript = transcript_logger.get_transcript()
    
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found for session {session_id}")
    
    return {
        "session_id": session_id,
        "transcript": transcript,
        "message_count": len(transcript)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)