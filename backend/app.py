# app.py
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from fastapi import WebSocket, WebSocketDisconnect

# ✅ IMPORT REQUIRED AGENT FUNCTIONS
from agent_core import (
    agent,
    get_cluster_health,
    build_response,
    run_background_rca,
)


app = FastAPI(
    title="DevOps AI SRE Agent",
    description="SRE-grade Kubernetes AI assistant for AKS/EKS/local clusters",
    version="1.0.0"
)

# -------------------------------
# Request / Response Models
# -------------------------------
class ChatRequest(BaseModel):
    message: str


class SREAgentResponse(BaseModel):
    summary: str
    category: str
    confidence: float
    auto_heal: bool
    analysis_status: str
    evidence: List[str]
    recommendations: List[str]
    raw_output: Optional[str] = ""


# -------------------------------
# Health Endpoint
# -------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


# -------------------------------
# Chat Endpoint
# -------------------------------
@app.post("/chat", response_model=SREAgentResponse)
def chat(req: ChatRequest, bg_tasks: BackgroundTasks):
    health = get_cluster_health()

    if health["healthy"]:
        return build_response(
            summary="Cluster is healthy",
            category="Healthy",
            confidence=health["confidence"],
            auto_heal=False,
            evidence=[],
            recommendations=[],
            analysis_status="COMPLETE"
        )

    response = build_response(
        summary="Cluster unhealthy – analysis in progress",
        category="ClusterIssue",
        confidence=health["confidence"],
        auto_heal=False,
        evidence=health["evidence"],
        recommendations=[
            "Inspect failing pods",
            "Check pod events",
            "Review recent deployments"
        ],
        analysis_status="PENDING"
    )

    INCIDENT_STORE[response["incident_id"]] = response

    bg_tasks.add_task(run_background_rca, response["incident_id"], health["evidence"])

    return response


INCIDENT_STORE = {}
ACTIVE_CONNECTIONS = set()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ACTIVE_CONNECTIONS.add(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        ACTIVE_CONNECTIONS.remove(ws)


# -------------------------------
# Root Endpoint (Optional UX)
# -------------------------------
@app.get("/")
def root():
    return {
        "message": "DevOps AI SRE Agent is running",
        "usage": {
            "health": "/health",
            "chat": "POST /chat",
            "docs": "/docs"
        }
    }