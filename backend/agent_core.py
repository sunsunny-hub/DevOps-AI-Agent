# agent_core.py
import subprocess
import requests
import uuid
import os
import asyncio
from typing import Optional, List, Dict, Any
from requests.exceptions import ReadTimeout
import html
import re
import json

INCIDENT_STORE: dict = {}

PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL")
PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY")

if not PORTKEY_BASE_URL or not PORTKEY_API_KEY:
    raise RuntimeError("PORTKEY_BASE_URL and PORTKEY_API_KEY must be set")

# ---------------- COMMAND ---------------- #

def run_command(cmd: str) -> str:
    try:
        return subprocess.check_output(
            cmd, shell=True, text=True, stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as exc:
        return exc.output or str(exc)

# ---------------- AI ---------------- #

def ask_ai(prompt: str) -> str:
    url = f"{PORTKEY_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PORTKEY_API_KEY}",
    }

    payload = {
        "model": "@aws-bedrock-use2/us.anthropic.claude-sonnet-4-6",
        "messages": [
            {"role": "system", "content": "You are a Kubernetes SRE assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 500,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except ReadTimeout:
        return ""
    except Exception:
        return ""

# ---------------- INTENT (SOFT NLP ✅) ---------------- #

def parse_intent(user_input: str) -> Dict[str, Any]:
    text = user_input.lower()

    intent = {
        "intent": "unknown",
        "namespace": None,
        "filter": None
    }

    # ✅ 1. HIGH PRIORITY: RCA / Root Cause
    if any(keyword in text for keyword in ["rca", "root cause", "analysis"]):
        intent["intent"] = "rca"

    # ✅ 2. POD RELATED
    elif any(keyword in text for keyword in ["pod", "pods"]):
        intent["intent"] = "get_pods"

    # ✅ 3. HEALTH CHECK
    elif any(keyword in text for keyword in ["health", "cluster status", "cluster health"]):
        intent["intent"] = "health"

    # ✅ 4. NAMESPACE EXTRACTION (robust)
    ns_match = re.search(r"(?:in|from)\s+([a-z0-9-]+)", text)
    if ns_match:
        intent["namespace"] = ns_match.group(1)

    # ✅ 5. FAILURE FILTER
    if any(keyword in text for keyword in ["failed", "crash", "error", "not running"]):
        intent["filter"] = "failed"

    return intent

# ---------------- K8s ---------------- #

def get_pod_snapshot(namespace: Optional[str] = None) -> List[dict]:
    cmd = (
        f"kubectl get pods -n {namespace} --no-headers"
        if namespace
        else "kubectl get pods -A --no-headers"
    )

    output = run_command(cmd)
    snapshot: List[dict] = []

    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            if namespace:
                snapshot.append({
                    "namespace": namespace,
                    "pod": parts[0],
                    "status": parts[2],
                })
            else:
                snapshot.append({
                    "namespace": parts[0],
                    "pod": parts[1],
                    "status": parts[3],
                })

    return snapshot

def get_cluster_health() -> dict:
    pods_raw = run_command("kubectl get pods -A --no-headers")

    unhealthy = []
    for line in pods_raw.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[3] not in ("Running", "Completed"):
            unhealthy.append(f"{parts[0]}/{parts[1]} {parts[3]}")

    return {
        "healthy": not unhealthy,
        "confidence": 0.95 if not unhealthy else 0.9,
        "evidence": unhealthy,
    }

# ---------------- RESPONSE ---------------- #

def build_response(
    summary: str,
    category: str,
    confidence: float,
    auto_heal: bool,
    evidence: List[str],
    recommendations: List[str],
    raw_output: dict,
    analysis_status: str,
    incident_id: Optional[str] = None,
) -> dict:
    return {
        "incident_id": incident_id or str(uuid.uuid4()),
        "summary": summary,
        "category": category,
        "confidence": round(confidence, 2),
        "auto_heal": auto_heal,
        "analysis_status": analysis_status,
        "evidence": evidence,
        "recommendations": recommendations,
        "raw_output": raw_output,
    }

# ---------------- EDUCATION ---------------- #

def educate_user():
    return build_response(
        summary="I can help with Kubernetes operations like pods, logs, health checks.",
        category="Help",
        confidence=0.9,
        auto_heal=False,
        evidence=[],
        recommendations=[],
        analysis_status="COMPLETE",
        raw_output={
            "sections": [
                {
                    "type": "help",
                    "items": [
                        "Get pods (e.g. 'show pods')",
                        "Check cluster health",
                        "Fetch pod logs",
                        "Describe a pod"
                    ]
                }
            ]
        }
    )

# ---------------- AGENT (SAFE WRAPPER ✅) ---------------- #

def run_agent(user_input: str):
    intent = parse_intent(user_input)

    # ✅ HANDLE POD LISTING
    if intent["intent"] == "get_pods":
        pods = get_pod_snapshot(intent["namespace"])

        if intent["filter"] == "failed":
            pods = [
                p for p in pods
                if p["status"] not in ("Running", "Completed")
            ]

        summary = (
            "Here are failed pods"
            if intent["filter"] == "failed"
            else f"Pods in {intent['namespace']}"
            if intent["namespace"]
            else "Here are the pods"
        )

        return build_response(
            summary=summary,
            category="Pods",
            confidence=0.95,
            auto_heal=False,
            evidence=[],
            recommendations=[],
            analysis_status="COMPLETE",
            raw_output={
                "sections": [{"type": "pods", "items": pods}]
            },
        )

    # ✅ 🔥 HANDLE RCA REQUEST
    if intent["intent"] == "rca":
        # Let existing health + RCA pipeline handle it
        return None

    # ✅ HEALTH → fallback
    if intent["intent"] == "health":
        return None

    # ✅ UNKNOWN → educate
    if intent["intent"] == "unknown":
        return educate_user()

    return None

# ---------------- RCA ---------------- #

def normalize_llm_output(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    return text.strip()

async def run_background_rca(incident_id: str, evidence: List[str]) -> None:
    raw_rca = await asyncio.to_thread(
        ask_ai,
        "Cluster issues detected:\n"
        + "\n".join(evidence)
        + "\n\nProvide root cause and remediation."
    )

    rca_text = normalize_llm_output(raw_rca)

    incident = INCIDENT_STORE[incident_id]

    INCIDENT_STORE[incident_id] = {
        **incident,
        "analysis_status": "COMPLETE",
        "raw_output": {
            **incident["raw_output"],
            "sections": incident["raw_output"]["sections"] + [
                {"type": "rca", "content": rca_text}   # ✅ EXACT MATCH
            ],
        },
    }

