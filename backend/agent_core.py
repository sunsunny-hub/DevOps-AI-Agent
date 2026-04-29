# agent_core.py
import subprocess
import requests
import uuid
import os
import asyncio
from typing import Optional, List
from requests.exceptions import ReadTimeout
import html
import re


INCIDENT_STORE: dict = {}

PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL")
PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY")

if not PORTKEY_BASE_URL or not PORTKEY_API_KEY:
    raise RuntimeError("PORTKEY_BASE_URL and PORTKEY_API_KEY must be set")

def run_command(cmd: str) -> str:
    try:
        return subprocess.check_output(
            cmd, shell=True, text=True, stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as exc:
        return exc.output or str(exc)

def ask_ai(prompt: str) -> str:
    url = f"{PORTKEY_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PORTKEY_API_KEY}",
    }
    payload = {
        "model": "@aws-bedrock-use2/us.anthropic.claude-sonnet-4-6",
        "messages": [
            {"role": "system", "content": "You are a senior Kubernetes SRE."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 800,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except ReadTimeout:
        return "⚠️ RCA timed out. Manual investigation required."
    except Exception as exc:
        return f"⚠️ AI failure: {exc}"

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

def normalize_llm_output(text: str) -> str:
    # Decode HTML entities (&amp; &lt; &gt;)
    text = html.unescape(text)

    # Remove Markdown headings (#, ##, ###)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)

    # Remove blockquote markers (>)
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)

    # Remove Markdown table pipes
    text = re.sub(r"\|", "", text)

    # Remove horizontal rules
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)

    return text.strip()

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
    unhealthy: List[str] = []

    for line in pods_raw.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[3] not in ("Running", "Completed"):
            unhealthy.append(f"{parts[0]}/{parts[1]} {parts[3]}")

    return {
        "healthy": not unhealthy,
        "confidence": 0.95 if not unhealthy else 0.9,
        "evidence": unhealthy,
    }

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
            "sections": incident["raw_output"]["sections"]
            + [{"type": "rca", "content": rca_text}],
        },
    }
