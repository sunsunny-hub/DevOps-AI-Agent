# app.py
import asyncio
import re
from typing import List, Optional, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent_core import (
    get_cluster_health,
    get_pod_snapshot,
    build_response,
    run_background_rca,
    INCIDENT_STORE,
)

app = FastAPI(title="K8s DevOps AI Agent", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

# ✅ FIX: incident_id MUST be part of response_model
class SREAgentResponse(BaseModel):
    incident_id: str
    summary: str
    category: str
    confidence: float
    auto_heal: bool
    analysis_status: str
    evidence: List[str]
    recommendations: List[str]
    raw_output: Optional[Dict[str, Any]]

def extract_namespace(text: str) -> Optional[str]:
    match = re.search(r"(?:from|in)\s+([a-z0-9-]+)", text.lower())
    return match.group(1) if match else None

@app.post("/chat", response_model=SREAgentResponse)
async def chat(req: ChatRequest):
    health = get_cluster_health()
    namespace = extract_namespace(req.message)
    pods = get_pod_snapshot(namespace)

    if health["healthy"]:
        return build_response(
            summary="Cluster is healthy",
            category="Healthy",
            confidence=health["confidence"],
            auto_heal=False,
            evidence=[],
            recommendations=[],
            analysis_status="COMPLETE",
            raw_output={
                "title": "✅ Cluster is healthy",
                "sections": [
                    {"type": "pods", "items": pods},
                ],
            },
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
            "Review recent deployments",
        ],
        analysis_status="PENDING",
        raw_output={
            "title": "⚠️ Cluster unhealthy",
            "sections": [
                {"type": "problems", "items": health["evidence"]},
                {"type": "pods", "items": pods},
                {"type": "status", "message": "DevOps AI is analyzing root cause…"},
            ],
        },
    )

    INCIDENT_STORE[response["incident_id"]] = response
    asyncio.create_task(
        run_background_rca(response["incident_id"], health["evidence"])
    )

    return response

@app.get("/incident/{incident_id}")
def get_incident(incident_id: str):
    return INCIDENT_STORE.get(incident_id)

@app.get("/health")
def health():
    return {"status": "ok"}