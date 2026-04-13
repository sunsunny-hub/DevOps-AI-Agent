# agent_core.py
import subprocess
import requests
import uuid
import asyncio
from langchain_core.tools import tool
from typing import Optional

# -------------------------------
# Run command safely
# -------------------------------
def run_command(cmd: str) -> str:
    """
    Execute a shell command safely and return stdout or error output.

    Args:
        cmd: Shell command to execute.

    Returns:
        Command output as string.
    """
    try:
        return subprocess.check_output(
            cmd, shell=True, text=True, stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as e:
        return e.output or str(e)


# -------------------------------
# LLM (SRE-grade reasoning)
# -------------------------------
def ask_ai(prompt: str) -> str:
    """
    Send a prompt to the local Ollama LLM for SRE-grade reasoning.

    Args:
        prompt: Instruction or context for the LLM.

    Returns:
        Model-generated response as string.
    """
    url = "http://localhost:11434/api/generate"

    payload = {
        "model": "llama3.1:8b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 300,
        },
    }

    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()["response"]


def build_response(
    summary: str,
    category: str,
    confidence: float,
    auto_heal: bool,
    evidence: list,
    recommendations: list,
    raw_output: str = "",
    analysis_status: str = "COMPLETE",
    incident_id: Optional[str] = None
):
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


def get_cluster_health():
    """
    Deterministic cluster health check (NO LLM, sub-second).
    This function is the SOURCE OF TRUTH for health.
    """
    pods_raw = run_command("kubectl get pods -A --no-headers")

    unhealthy = []
    restart_warnings = []

    for line in pods_raw.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue

        namespace, pod, status = parts[0], parts[1], parts[3]

        if status not in ["Running", "Completed"]:
            unhealthy.append(f"{namespace}/{pod} {status}")

        # Restart count check (important!)
        describe = run_command(f"kubectl describe pod {pod} -n {namespace}")
        for l in describe.splitlines():
            if "Restart Count:" in l:
                count = int(l.split(":")[-1].strip())
                if count >= 3:
                    restart_warnings.append(
                        f"{namespace}/{pod} restarts={count}"
                    )

    if unhealthy:
        return {
            "healthy": False,
            "confidence": 0.9,
            "evidence": unhealthy + restart_warnings
        }

    return {
        "healthy": True,
        "confidence": 0.95,
        "evidence": []
    }


def summarize_evidence_for_llm(evidence: list) -> str:
    """
    Compress cluster evidence into LLM-friendly summary.
    Keeps context small but meaningful.
    """
    summary_lines = []

    for item in evidence[:5]:  # limit context intentionally
        summary_lines.append(f"- Issue observed: {item}")

    return "\n".join(summary_lines)



async def notify_clients(message: dict):
    for ws in list(ACTIVE_CONNECTIONS):
        try:
            await ws.send_json(message)
        except:
            ACTIVE_CONNECTIONS.remove(ws)


def run_background_rca(incident_id: str, evidence: list):
    summary = summarize_evidence_for_llm(evidence)

    rca = ask_ai(f"""
You are a Kubernetes SRE.

Issues detected:
{summary}

Provide:
1. Root cause
2. Remediation steps
3. What NOT to do
""")

    INCIDENT_STORE[incident_id]["analysis_status"] = "COMPLETE"
    INCIDENT_STORE[incident_id]["raw_output"] = rca

    asyncio.run(
        notify_clients(INCIDENT_STORE[incident_id])
    )



# -------------------------------
# LangChain TOOLS
# -------------------------------
@tool
def get_pods() -> str:
    """
    Retrieve all Kubernetes pods across all namespaces.

    Returns:
        A string containing the output of `kubectl get pods -A`.
    """
    return run_command("kubectl get pods -A")


@tool
def get_problem_pods() -> str:
    """
    Identify Kubernetes pods that are not in Running or Completed state.

    Returns:
        A formatted list of problematic pods, or a healthy cluster message.
    """
    output = run_command("kubectl get pods -A --no-headers")

    problems = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[3] not in ["Running", "Completed"]:
            problems.append(line)

    return "\n".join(problems) if problems else "✅ No problematic pods found."


@tool
def get_logs() -> str:
    """
    Analyze application issues using logs or pod descriptions
    depending on the pod lifecycle state.

    Logic:
    - CrashLoopBackOff  → `kubectl logs --previous`
    - Error / ContainerCreating → `kubectl describe pod`
    - Running           → live logs with error filtering

    Returns:
        SRE-style analysis of detected issues.
    """
    pods = run_command("kubectl get pods -A --no-headers")
    findings = []

    for line in pods.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue

        namespace, pod, status = parts[0], parts[1], parts[3]

        # Skip system namespaces
        if namespace in ["kube-system", "local-path-storage"]:
            continue

        # ---- CrashLoopBackOff: previous logs
        if status == "CrashLoopBackOff":
            logs = run_command(
                f"kubectl logs -n {namespace} {pod} --previous"
            )

            if logs.strip():
                analysis = ask_ai(f"""
You are a Kubernetes SRE.

The following logs are from a crashing pod:

{logs[:3000]}

Explain:
1. Likely root cause
2. Why the pod keeps restarting
3. Correct remediation steps
""")
                findings.append(f"🟥 CrashLoopBackOff pod {pod}:\n{analysis}")
            else:
                findings.append(
                    f"🟥 CrashLoopBackOff pod {pod}: No previous logs available."
                )

        # ---- Error / ContainerCreating: describe pod
        elif status in ["Error", "ContainerCreating"]:
            describe = run_command(
                f"kubectl describe pod {pod} -n {namespace}"
            )

            analysis = ask_ai(f"""
You are a Kubernetes SRE.

The pod is in state '{status}'.

Pod description:
{describe}

Explain:
1. What caused this state
2. Whether logs are expected to exist
3. Recommended remediation steps
""")
            findings.append(f"🟧 Pod {pod} ({status}):\n{analysis}")

        # ---- Running: inspect live logs for errors
        elif status == "Running":
            logs = run_command(f"kubectl logs -n {namespace} {pod}")

            critical_keywords = [
                "error", "panic", "fatal", "exception", "timeout"
            ]

            important = [
                l for l in logs.splitlines()
                if any(k in l.lower() for k in critical_keywords)
            ]

            if important:
                analysis = ask_ai(f"""
You are a Kubernetes SRE.

The following application errors were found:

{chr(10).join(important[:20])}

Explain impact and remediation.
""")
                findings.append(
                    f"🟨 Running pod {pod} log issues:\n{analysis}"
                )

    if not findings:
        return (
            "✅ No actionable logs found. "
            "If pods are failing without logs, inspect pod events and resource limits."
        )

    return "\n\n".join(findings)


@tool
def classify_incident() -> dict:
    """
    Classify Kubernetes incidents and provide SRE-grade remediation guidance.
    """
    problems = get_problem_pods.invoke({})

    if "✅" in problems:
        return build_response(
            summary="Cluster is healthy",
            category="Healthy",
            confidence=0.95,
            auto_heal=False,
            evidence=[],
            recommendations=[],
            raw_output=problems
        )

    # Ask LLM only for reasoning text
    analysis = ask_ai(f"""
You are a senior Kubernetes SRE.

Analyze the following Kubernetes issues:
{problems}

Return:
- root cause
- remediation steps
""")

    return build_response(
        summary="Kubernetes issues detected",
        category="ClusterIssue",
        confidence=0.85,
        auto_heal=False,
        evidence=[problems],
        recommendations=[
            "Inspect pod logs",
            "Describe affected pods",
            "Validate recent deployments",
            "Check resource limits"
        ],
        raw_output=analysis
    )


@tool
def auto_heal_failed_pods() -> str:
    """
    Determine whether failed pods can be auto-healed safely.

    This tool:
    - Avoids blind restarts
    - Explains why auto-healing is or is not appropriate
    - Provides human-level remediation guidance

    Returns:
        An SRE-style explanation and auto-heal decision.
    """
    pods = run_command("kubectl get pods -A --no-headers")

    for line in pods.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue

        namespace, pod, status = parts[0], parts[1], parts[3]

        if namespace in ["kube-system", "local-path-storage"]:
            continue

        if status == "CrashLoopBackOff":
            describe = run_command(
                f"kubectl describe pod {pod} -n {namespace}"
            )

            return ask_ai(f"""
You are a senior Kubernetes SRE.

A pod is in CrashLoopBackOff.

Pod description:
{describe}

Explain:
1. Root cause
2. Why auto-healing will not work
3. Correct remediation approach
""")

    return "✅ No auto-healable issues detected."


# -------------------------------
# Tool registry
# -------------------------------
TOOLS = {
    "get_pods": get_pods,
    "get_problem_pods": get_problem_pods,
    "get_logs": get_logs,
    "classify_incident": classify_incident,
    "auto_heal": auto_heal_failed_pods,
}


# -------------------------------
# Intent detection
# -------------------------------
def detect_intent(user_input: str) -> str:
    """
    Detect user intent from natural-language input.

    Args:
        user_input: Chat input string.

    Returns:
        Intent key corresponding to a tool or general AI query.
    """
    ui = user_input.lower()

    if any(w in ui for w in ["heal", "fix", "recover"]):
        return "auto_heal"
    if "classify" in ui or "root cause" in ui:
        return "classify_incident"
    if "log" in ui:
        return "get_logs"
    if "issue" in ui or "problem" in ui:
        return "get_problem_pods"
    if "pod" in ui:
        return "get_pods"

    return "general"



# -------------------------------
# Main agent entry
# -------------------------------
def agent(prompt: str) -> dict:
    """
    Main SRE agent entry point.
    Always returns structured JSON.
    """
    intent = detect_intent(prompt)

    if intent in TOOLS:
        result = TOOLS[intent].invoke({})

        # If tool already returns structured response
        if isinstance(result, dict):
            return result

        # Fallback: wrap text output
        return build_response(
            summary="SRE Analysis",
            category="General",
            confidence=0.7,
            auto_heal=False,
            evidence=[],
            recommendations=[],
            raw_output=result
        )

    # General AI fallback
    ai_response = ask_ai(prompt)

    return build_response(
        summary="General SRE Response",
        category="General",
        confidence=0.6,
        auto_heal=False,
        evidence=[],
        recommendations=[],
        raw_output=ai_response
    )


