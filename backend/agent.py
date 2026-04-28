import subprocess
import requests
import os
from typing import Optional
from langchain_core.tools import tool
from requests.exceptions import ReadTimeout

# =========================================================
# ENVIRONMENT VARIABLES (DO NOT HARDCODE)
# =========================================================

PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL")
PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY")

if not PORTKEY_BASE_URL or not PORTKEY_API_KEY:
    raise RuntimeError("PORTKEY_BASE_URL and PORTKEY_API_KEY must be set")


# =========================================================
# Run command safely
# =========================================================
def run_command(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True, text=True)
    except subprocess.CalledProcessError as e:
        return e.output if e.output else str(e)


# =========================================================
# ✅ LLM (SRE‑grade reasoning via Portkey)
# =========================================================

def ask_ai(prompt: str) -> str:
    """
    SRE-grade AI inference via Portkey Gateway (Azure OpenAI).
    Mirrors the provided JS Portkey example.
    """

    url = f"{PORTKEY_BASE_URL}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PORTKEY_API_KEY}",
    }

    payload = {
        "model": "@azure-openai/gpt-4o-mini",  # ✅ same as JS example
        "messages": [
            {
                "role": "system",
                "content": "You are a senior Kubernetes SRE. Provide clear RCA and remediation."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 512,
        "temperature": 0.2
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    except ReadTimeout:
        return (
            "⚠️ RCA analysis timed out. "
            "Cluster issues are detected; detailed analysis is still in progress."
        )

    except Exception as e:
        return f"⚠️ AI analysis failed: {str(e)}"



# =========================================================
# LangChain TOOLS
# =========================================================
@tool
def get_pods() -> str:
    """Get all pods in Kubernetes cluster"""
    return run_command("kubectl get pods -A")


@tool
def get_problem_pods() -> str:
    """Get pods that are not in Running or Completed state"""
    output = run_command("kubectl get pods -A --no-headers")

    problems = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue

        status = parts[3]
        if status not in ["Running", "Completed"]:
            problems.append(line)

    return "\n".join(problems) if problems else "✅ No problematic pods found."


@tool
def get_logs() -> str:
    """
    Analyze application issues using logs OR pod descriptions
    depending on pod lifecycle state.
    """
    pods = run_command("kubectl get pods -A --no-headers")
    findings = []

    for line in pods.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue

        namespace, pod, status = parts[0], parts[1], parts[3]

        if namespace in ["kube-system", "local-path-storage"]:
            continue

        # ---- CrashLoopBackOff → previous logs
        if status == "CrashLoopBackOff":
            logs = run_command(f"kubectl logs -n {namespace} {pod} --previous")

            if logs.strip():
                analysis = ask_ai(f"""
Pod {pod} in namespace {namespace} is crashing.

Logs:
{logs[:3000]}

Explain:
1. Root cause
2. Why it keeps restarting
3. Correct remediation
""")
                findings.append(f"🟥 CrashLoopBackOff {pod}:\n{analysis}")
            else:
                findings.append(f"🟥 CrashLoopBackOff {pod}: No logs available")

        # ---- Error / ContainerCreating → describe pod
        elif status in ["Error", "ContainerCreating"]:
            describe = run_command(f"kubectl describe pod {pod} -n {namespace}")

            analysis = ask_ai(f"""
Pod {pod} is in state {status}.

Description:
{describe}

Explain cause and remediation.
""")
            findings.append(f"🟧 Pod {pod} ({status}):\n{analysis}")

        # ---- Running → inspect logs
        elif status == "Running":
            logs = run_command(f"kubectl logs -n {namespace} {pod}")

            keywords = ["error", "panic", "fatal", "exception", "timeout"]
            important = [
                l for l in logs.splitlines()
                if any(k in l.lower() for k in keywords)
            ]

            if important:
                analysis = ask_ai(f"""
Application errors detected in pod {pod}:

{chr(10).join(important[:20])}

Explain impact and remediation.
""")
                findings.append(f"🟨 Running pod {pod} issues:\n{analysis}")

    if not findings:
        return (
            "✅ No actionable logs found. "
            "If issues persist, inspect pod events and resource limits."
        )

    return "\n\n".join(findings)


# =========================================================
# ✅ Auto‑heal (Root‑cause aware)
# =========================================================
@tool
def auto_heal_failed_pods() -> str:
    """
    Root‑cause‑aware auto healing.
    CrashLoopBackOff is intentionally NOT auto‑healed.
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
            describe = run_command(f"kubectl describe pod {pod} -n {namespace}")

            return ask_ai(f"""
Pod {pod} is in CrashLoopBackOff.

Description:
{describe}

Explain:
1. Root cause
2. Why auto‑healing is unsafe
3. Correct remediation steps
""")

    return "✅ No auto‑healable issues detected."


# =========================================================
# ✅ Incident Classification
# =========================================================
@tool
def classify_incident() -> str:
    """Classify Kubernetes issues with SRE‑grade remediation"""
    problems = get_problem_pods.invoke({})

    if "✅" in problems:
        return problems

    return ask_ai(f"""
Cluster issues detected:
{problems}

Provide:
1. Failure classification
2. Evidence
3. Remediation steps
4. Auto‑heal decision
5. What NOT to do
""")


# =========================================================
# Tool registry
# =========================================================
TOOLS = {
    "get_pods": get_pods,
    "get_problem_pods": get_problem_pods,
    "get_logs": get_logs,
    "auto_heal": auto_heal_failed_pods,
    "classify_incident": classify_incident,
}


# =========================================================
# Intent detection
# =========================================================
def detect_intent(user_input: str) -> str:
    ui = user_input.lower()

    if any(w in ui for w in ["heal", "fix", "recover", "auto heal"]):
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


# =========================================================
# MAIN AGENT
# =========================================================
def agent(user_input: str) -> str:
    intent = detect_intent(user_input)
    print("\n🧠 Intent:", intent)

    if intent in TOOLS:
        return TOOLS[intent].invoke({})

    return ask_ai(user_input)


# =========================================================
# CLI LOOP (Optional for local testing)
# =========================================================
if __name__ == "__main__":
    while True:
        try:
            user_input = input("\nAsk DevOps AI > ")
            if user_input.lower() in ["exit", "quit"]:
                break
            print("\n🤖 AI:", agent(user_input))
        except KeyboardInterrupt:
            print("\nExiting...")
            break