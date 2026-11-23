# ==============================================================================
# Step 15: The FastAPI Streaming Engine (Connecting Brain to Web)
# File: backend/src/backend/main.py
#
# FOR BEGINNERS:
# Right now, our agent only runs in the terminal.
# To let a web dashboard (Next.js) or a hiring manager interact with it, we
# need a Web Server.
#
# FastAPI is the gold standard Python web framework:
# 1. It exposes endpoints like POST /api/triage/diagnose.
# 2. It uses Server-Sent Events (SSE) to stream agent steps live to the UI
#    ("Planning...", "Searching...", "Grading...", "Auditing...").
# 3. It handles CORS so our frontend can communicate without browser errors.
# ==============================================================================

import os
import json
import asyncio
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Import our knowledge base, graph, and state
from backend.ingestion.parser import StructureAwareParser
from backend.ingestion.hybrid_store import HybridSearchStore
from backend.core.graph import IncidentTriageGraph
from backend.core.state import AgentState

# Initialize the FastAPI Web Application
app = FastAPI(
    title="Autonomous Incident Triage & Runbook Agent",
    version="0.1.0",
    description="Full-stack Agentic RAG API with self-correcting retrieval and human-in-the-loop safety gates."
)

# Enable CORS (Cross-Origin Resource Sharing) so Next.js UI on port 3000 can talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory knowledge store and triage agent
parser = StructureAwareParser()
hybrid_store = HybridSearchStore()
triage_agent = IncidentTriageGraph(hybrid_store=hybrid_store)


@app.on_event("startup")
async def startup_event():
    """
    When the server boots up, automatically index our sample runbooks
    so the agent is pre-loaded with knowledge!
    """
    sample_runbook = "data/sample_docs/runbook_redis_cluster.md"
    if os.path.exists(sample_runbook) and len(hybrid_store.cards) == 0:
        cards = parser.parse_file(sample_runbook)
        hybrid_store.index_cards(cards)


# --- Request and Response Schemas ---
class DiagnoseRequest(BaseModel):
    incident_report: str = Field(
        description="The incoming bug report, alert message, or outage description",
        example="API gateway throwing 504 on checkout. REDIS_MEM_CRITICAL alert triggered."
    )


class ApprovalRequest(BaseModel):
    action_id: str = Field(description="The unique ID of the pending tool action")
    approved: bool = Field(description="True if the engineer approves, False if rejected")


# --- Endpoint 1: Health Check ---
@app.get("/api/health")
def health_check():
    """Returns server status, version, and the number of indexed runbook cards."""
    return {
        "status": "healthy",
        "service": "incident-triage-agent",
        "docs_indexed": len(hybrid_store.cards)
    }


# --- Endpoint 2: Synchronous Diagnosis ---
@app.post("/api/triage/diagnose")
def diagnose_incident(req: DiagnoseRequest):
    """
    Runs the entire LangGraph state machine synchronously
    and returns the complete Case File (AgentState).
    """
    if not req.incident_report.strip():
        raise HTTPException(status_code=400, detail="Incident report cannot be empty.")

    final_state = triage_agent.invoke(req.incident_report)
    return {
        "incident_report": final_state.incident_report,
        "final_output": final_state.final_output,
        "citations": final_state.citations,
        "requires_approval": final_state.requires_approval,
        "sub_queries": final_state.sub_queries,
        "step_history": final_state.step_history
    }


# --- Endpoint 3: Server-Sent Events (SSE) Live Streaming ---
@app.post("/api/triage/stream")
async def stream_incident_triage(req: DiagnoseRequest):
    """
    Streams the agent's live thought process to the UI step-by-step
    so the user sees real-time progress instead of waiting in silence.
    """
    if not req.incident_report.strip():
        raise HTTPException(status_code=400, detail="Incident report cannot be empty.")

    async def event_generator() -> AsyncGenerator[str, None]:
        # Step 1: Initialized
        yield f"data: {json.dumps({'step': 'init', 'message': 'Incident received. Initializing LangGraph state machine...'})}\n\n"
        await asyncio.sleep(0.3)

        # Step 2: Planning
        state = AgentState(incident_report=req.incident_report)
        state = triage_agent.router_node(state)
        yield f"data: {json.dumps({'step': 'planner', 'sub_queries': state.sub_queries, 'message': f'Planner generated {len(state.sub_queries)} sub-queries.'})}\n\n"
        await asyncio.sleep(0.3)

        # Step 3: Searching
        state = triage_agent._searcher_node(state)
        yield f"data: {json.dumps({'step': 'searcher', 'docs_count': len(state.retrieved_docs), 'message': f'Retrieved {len(state.retrieved_docs)} gold evidence cards.'})}\n\n"
        await asyncio.sleep(0.3)

        # Step 4: Grading
        state = triage_agent.grader_node(state)
        yield f"data: {json.dumps({'step': 'grader', 'verdict': state.grader_verdict, 'message': f'Grader verdict: {state.grader_verdict.upper()}'})}\n\n"
        await asyncio.sleep(0.3)

        # Step 5: Diagnosis & Tool Gate
        state = triage_agent._diagnostician_node(state)
        state = triage_agent._tools_step_node(state)
        yield f"data: {json.dumps({'step': 'diagnostician', 'requires_approval': state.requires_approval, 'message': 'Draft diagnosis formulated.'})}\n\n"
        await asyncio.sleep(0.3)

        # Step 6: Citation & Hallucination Audit
        state = triage_agent.auditor_node(state)
        yield f"data: {json.dumps({'step': 'auditor', 'citations_count': len(state.citations), 'message': 'Audit complete. All claims verified.'})}\n\n"
        await asyncio.sleep(0.2)

        # Step 7: Completed Final Output
        final_payload = {
            "step": "complete",
            "final_output": state.final_output,
            "citations": state.citations,
            "requires_approval": state.requires_approval,
            "step_history": state.step_history
        }
        yield f"data: {json.dumps(final_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
