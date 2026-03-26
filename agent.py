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
# LLM (ONLY for reasoning/explanation)
# -------------------------------
def ask_ai(prompt):
    url = "http://localhost:11434/api/generate"

    payload = {
        "model": "phi3:mini",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 100
        }
    }

    response = requests.post(url, json=payload)
    return response.json()["response"]


# -------------------------------
# LangChain TOOLS (clean abstraction)
# -------------------------------
@tool
def get_pods() -> str:
    """Get all pods in Kubernetes cluster"""
    return run_command("kubectl get pods -A")


@tool
def get_problem_pods() -> str:
    """Get pods that are not in Running state"""
    output = run_command("kubectl get pods -A")

    problems = []
    for line in output.splitlines():
        if "Running" not in line and "NAME" not in line:
            problems.append(line)

    return "\n".join(problems) if problems else "✅ No problematic pods found."


@tool
def get_logs() -> str:
    """Analyze logs only for user workloads (ignore system noise)"""

    pods = run_command("kubectl get pods -A --no-headers")

    for line in pods.splitlines():
        parts = line.split()

        if len(parts) < 4:
            continue

        namespace = parts[0]
        pod = parts[1]
        status = parts[3]

        # Ignore system namespaces
        if namespace in ["kube-system", "local-path-storage"]:
            continue

        if status == "Running":
            logs = run_command(f"kubectl logs -n {namespace} {pod}")

            #  Only critical signals
            critical_keywords = ["error", "panic", "crash", "backoff", "fatal"]

            important = []
            for l in logs.splitlines():
                if any(k in l.lower() for k in critical_keywords):
                    important.append(l)

            if not important:
                return "✅ No critical issues found in application logs."

            return ask_ai(
                "Analyze this application error and explain root cause briefly:\n"
                + "\n".join(important[:20])
            )

    return "✅ No application pods found (only system pods running)."


# -------------------------------
# Tool registry
# -------------------------------
TOOLS = {
    "get_pods": get_pods,
    "get_problem_pods": get_problem_pods,
    "get_logs": get_logs
}


# -------------------------------
# Intent detection (fast + reliable)
# -------------------------------
def detect_intent(user_input):
    user_input = user_input.lower()

    if "pod" in user_input and ("get" in user_input or "show" in user_input):
        return "get_pods"

    if "issue" in user_input or "problem" in user_input:
        return "get_problem_pods"

    if "log" in user_input:
        return "get_logs"

    return "general"


# -------------------------------
# MAIN AGENT (Hybrid + Tools)
# -------------------------------
def agent(user_input):
    intent = detect_intent(user_input)

    print("\n🧠 Intent:", intent)

    if intent in TOOLS:
        return TOOLS[intent].invoke({})

    # fallback → LLM
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