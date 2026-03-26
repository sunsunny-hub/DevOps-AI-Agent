# 🚀 AI-Powered DevOps Agent (Kubernetes + Ollama)

## 📌 Overview

This project is a **Hybrid AI DevOps Agent** designed to monitor and debug Kubernetes clusters using a combination of:

* ⚡ Rule-based automation (Python)
* 🧠 Local LLM (Ollama - Phi3 Mini)
* 🔧 LangChain Tools (for clean abstraction)

Unlike traditional AI agents, this system avoids hallucination and instability by using a **hybrid architecture**, making it fast, reliable, and production-ready.

---

## 🧠 Key Features

### ✅ Kubernetes Observability

* Fetch all pods across namespaces
* Detect non-running / problematic pods

### ✅ Intelligent Log Analysis

* Multi-namespace log fetching
* Filters noisy system logs
* AI-based root cause explanation (only for real issues)

### ✅ Hybrid AI Architecture

* Rule-based intent detection (fast ⚡)
* LangChain tools for modular design
* LLM used only for reasoning (no over-reliance)

### ✅ Noise-Aware System

* Ignores Kubernetes system components (`kube-system`)
* Focuses only on application workloads

---

## 🏗️ Architecture

```
User Input
   ↓
Intent Detection (Python)
   ↓
LangChain Tool Execution
   ↓
(Kubernetes Commands)
   ↓
Optional LLM Analysis (Phi3 via Ollama)
   ↓
Response
```

---

## ⚙️ Tech Stack

* **Python**
* **Kubernetes (Kind)**
* **Ollama (Phi3 Mini)**
* **LangChain (Tools only)**
* **WSL / Linux**

---

## 🚀 Setup Instructions

### 1. Clone Repo

```bash
git clone https://github.com/YOUR_USERNAME/devops-ai-agent.git
cd devops-ai-agent
```

---

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Install Ollama & Model

```bash
ollama pull phi3:mini
ollama serve
```

---

### 5. Run Kubernetes Cluster (Kind)

```bash
kind create cluster --name devops-ai-cluster
kubectl get nodes
```

---

### 6. Run the Agent

```bash
python agent.py
```

---

## 🧪 Example Commands

```
get pods
any issues?
get logs
```

---

## 🧠 Why Hybrid Architecture?

Traditional AI agents (ReAct) often:

* ❌ Hallucinate
* ❌ Break on small models
* ❌ Are slow on local machines

This project solves that by:

* Using **Python for execution**
* Using **LLM only where needed**
* Ensuring **deterministic + fast responses**

---

## ⚠️ Challenges & Issues Encountered

During development, several real-world challenges were faced while building a local AI-powered DevOps agent:

---

### 1. ❌ LLM Hallucination with Small Models

* Initial models like `phi` produced:

  * Irrelevant responses
  * Broken reasoning loops
  * Incorrect tool usage

**Solution:**

* Switched to `phi3:mini`
* Reduced reliance on LLM for decision-making
* Introduced hybrid architecture (rule-based + AI)

---

### 2. ❌ LangChain Agent Instability

* `ReAct` agents failed with:

  * Output parsing errors
  * Infinite loops
  * Incorrect tool invocation

**Solution:**

* Avoided full agent-based approach
* Used LangChain only for **tool abstraction**
* Built controlled execution using Python logic

---

### 3. ❌ High Resource Usage (Llama 3 Failure)

* Attempted to use `llama3:8b`
* Resulted in:

  * CPU overload (~100%)
  * Model startup timeouts
  * System unresponsiveness

**Solution:**

* Replaced with lightweight model (`phi3:mini`)
* Optimized for 8GB RAM environments

---

### 4. ❌ GPU Not Utilized

* Ollama did not use GPU in WSL environment
* All computation ran on CPU

**Solution:**

* Accepted CPU-based execution
* Optimized model size instead of forcing GPU usage

---

### 5. ❌ Kubernetes Log Noise (False Positives)

* System logs (e.g., CoreDNS) contained:

  * Warnings
  * Non-critical errors

* AI misinterpreted these as real issues

**Solution:**

* Implemented log filtering:

  * Ignored `kube-system` namespace
  * Focused only on application workloads
  * Filtered only critical keywords (error, crash, fatal)

---

### 6. ❌ Namespace Handling Issues

* Initial implementation only checked `default` namespace
* Missed system and other namespace pods

**Solution:**

* Updated all commands to use:

  ```bash
  kubectl get pods -A
  ```

---

### 7. ❌ Over-Reliance on AI for Simple Tasks

* Using LLM for all operations caused:

  * Slow response times
  * Unnecessary complexity

**Solution:**

* Introduced hybrid architecture:

  * Python → execution (fast)
  * LLM → reasoning only when needed

---

## 💡 Key Learnings

* Smaller models require **controlled architectures**
* AI agents should not blindly control execution
* Hybrid systems are more **stable, efficient, and production-ready**
* Observability tools must filter **signal vs noise**

---


## 📈 Future Improvements (v2 Roadmap)

* 🔥 Auto-healing (restart pods, fix failures)
* 📊 Prometheus + Grafana integration
* 📩 Slack / Email alerts
* 🧠 Memory (learning from past issues)
* ☁️ Multi-cluster support

---

## 👨‍💻 Author

**Nirmalya Das**   
DevOps Engineer | AI + Cloud Enthusiast

---

## ⭐ If you like this project

Give it a ⭐ on GitHub and share feedback!
