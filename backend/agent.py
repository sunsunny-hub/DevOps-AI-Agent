import subprocess
import requests
from langchain_core.tools import tool

# -------------------------------
# Run command safely
# -------------------------------
def run_command(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True)
    except subprocess.CalledProcessError as e:
        return e.output if e.output else str(e)


# -------------------------------
# ✅ LLM (SRE-grade reasoning)
# -------------------------------
def ask_ai(prompt):
    url = "http://localhost:11434/api/generate"

    payload = {
        "model": "llama3.1:8b",   # ✅ upgraded model
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 300,   # allow deeper answers
        },
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()["response"]


# -------------------------------
# LangChain TOOLS
# -------------------------------
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

        # -------- CrashLoopBackOff → use previous logs
        if status == "CrashLoopBackOff":
            logs = run_command(
                f"kubectl logs -n {namespace} {pod} --previous"
            )

            if logs.strip():
                analysis = ask_ai(f"""
You are a Kubernetes SRE.

The following logs are from a pod that crashed:

{logs[:3000]}

Explain:
1. Likely root cause
2. Why the pod keeps restarting
3. What should be fixed
""")
                findings.append(f"🟥 CrashLoopBackOff pod {pod}:\n{analysis}")
            else:
                findings.append(
                    f"🟥 CrashLoopBackOff pod {pod}: No previous logs available."
                )

        # -------- OOM / Error / ContainerCreating → use describe
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
2. Whether logs would exist
3. What remediation steps are appropriate
""")
            findings.append(f"🟧 Pod {pod} ({status}):\n{analysis}")

        # -------- Running → normal logs
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

Explain the impact and remediation.
""")
                findings.append(f"🟨 Running pod {pod} log issues:\n{analysis}")

    if not findings:
        return (
            "✅ No actionable logs found. "
            "If pods are failing without logs, inspect pod events and resource limits."
        )

    return "\n\n".join(findings)


# -------------------------------
# ✅ Auto-heal (Root-cause aware)
# -------------------------------
@tool
def auto_heal_failed_pods() -> str:
    """
    Root-cause-aware auto healing:
    - NO blind restarts
    - Explains why healing is or isn't possible
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

Respond with:
1. Evidence from the pod description
2. Root cause (why it keeps crashing)
3. At least 3 remediation options
4. Explicitly state whether auto-healing is appropriate
5. What actions WILL NOT fix the issue
""")

    return "✅ No auto-healable issues detected."


# -------------------------------
# ✅ Incident Classification
# -------------------------------
@tool
def classify_incident() -> str:
    """Classify Kubernetes issues with deep remediation"""
    problems = get_problem_pods.invoke({})

    if "✅" in problems:
        return problems

    return ask_ai(f"""
You are a senior Kubernetes SRE.

Cluster issues detected:
{problems}

Provide:
1. Failure type classification
2. Evidence used for classification
3. At least 3–5 concrete remediation steps
4. Auto-heal decision (Yes/No + why)
5. What NOT to do
""")


# -------------------------------
# Tool registry
# -------------------------------
TOOLS = {
    "get_pods": get_pods,
    "get_problem_pods": get_problem_pods,
    "get_logs": get_logs,
    "auto_heal": auto_heal_failed_pods,
    "classify_incident": classify_incident,
}


# -------------------------------
# Intent detection
# -------------------------------
def detect_intent(user_input):
    ui = user_input.lower()

    if any(w in ui for w in ["heal", "fix", "recover", "auto heal"]):
        return "auto_heal"

    if "classify" in ui or "root cause" in ui:
        return "classify_incident"

    if "log" in ui:
        return "get_logs"

    if "issue" in ui or "problem" in ui:
        return "get_problem_pods"

    if "pod" in ui and ("get" in ui or "show" in ui):
        return "get_pods"

    return "general"


# -------------------------------
# MAIN AGENT
# -------------------------------
def agent(user_input):
    intent = detect_intent(user_input)
    print("\n🧠 Intent:", intent)

    if intent in TOOLS:
        return TOOLS[intent].invoke({})

    return ask_ai(user_input)


# -------------------------------
# LOOP
# -------------------------------
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