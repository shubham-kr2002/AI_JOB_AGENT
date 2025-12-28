# PROJECT JOBHUNTER - AUTONOMOUS AGENT PLATFORM (V3)

## 1. System Identity
A Self-Improving, Multi-Agent Autonomous Web Platform.
- **Core Loop:** Intent -> Plan (DAG) -> Execute -> Verify -> Learn.
- **Key Differentiator:** "World Model" (Persistent database of site-specific logic, selectors, and behaviors).
- **Goal:** Shift from "Form Filling Tool" to "Autonomous Job Search & Application Agent".

## 2. Architecture Layers
1.  **Intent Compiler:** LLM-based understanding converts human prompts into structured JSON Goals & Constraints.
2.  **Task Graph (DAG):** Generates parallelizable execution plans (e.g., Search LinkedIn || Search Indeed -> Filter -> Apply).
3.  **Cognitive Core (The "Brain"):**
    - *Planner Agent:* Strategy & resource allocation.
    - *Execution Agent:* Dual-mode (Browser/API) interaction.
    - *Critic Agent:* Adversarial validation of outputs (Anti-Hallucination).
    - *Recovery Agent:* Handles runtime errors (Timeouts, CAPTCHAs).
4.  **World Model (The "Moat"):**
    - Maps Domains (`greenhouse.io`) -> Selectors, Login Configs, Performance Profiles.
    - Updates dynamically after every successful task.
5.  **Memory:**
    - *Short-Term:* Redis (Task Queues, Session State).
    - *Long-Term:* PostgreSQL (Logs, Profiles).
    - *Vector:* Qdrant (Semantic Recall of past plans).

## 3. Tech Stack
- **Backend:** FastAPI (Python 3.10+).
- **Async Orchestration:** Celery + Redis (Critical for long-running DAGs).
- **Database:** PostgreSQL (Relational/JSONB), Qdrant (Vector).
- **Browser Automation:** Playwright (Python) with stealth plugins.
- **AI Models:** - *Reasoning:* GPT-4o / Claude 3.5 Sonnet.
    - *Speed:* Groq (Llama 3).
- **Infrastructure:** Docker Compose (Redis, Postgres, Qdrant, Worker Nodes).

## 4. Key Modules & Features

### A. The "Commander" (Input)
- **Intent Engine:** Extracts `Goal`, `Constraints` (Salary, Location), `Parameters` from natural language.
- **Task Planner:** Uses `networkx` to build dependency graphs for complex workflows.

### B. The "Hunter" (Execution)
- **Stealth Browsing:** Fingerprint rotation, User-Agent randomization, "Human-like" mouse movements.
- **Visual Cortex:** Uses Vision models to analyze screenshots when code-based selectors fail.
- **Self-Healing Selectors:** If a selector fails, analyzes DOM semantics to find the new element and updates the World Model.

### C. The "Learner" (Feedback)
- **Success Capture:** Logs successful selector paths and API endpoints to the World Model.
- **Semantic Recall:** Queries Vector DB for "How did we solve this site last time?" before starting a task.

## 5. Security & Privacy
- **Zero Trust:** PII encrypted at rest in Postgres.
- **Local-First Auth:** Cookies/Session tokens stored in encrypted local storage or secure server-side vault (User opt-in).
- **Rate Limiting:** Token buckets per user to prevent API cost overruns.