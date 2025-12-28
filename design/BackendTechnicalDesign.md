Backend Technical Design Document (V3)

System: Project JobHunter - Autonomous Cognitive Core Version: 3.0 Architecture Style: Event-Driven Multi-Agent System
1. High-Level Architecture (The "Nervous System")

The backend is no longer just a request-response API. It is an asynchronous orchestration engine. The API Gateway accepts a high-level goal, compiles it into a plan, and dispatches workers to execute it over minutes or hours.
Code snippet

graph TD
    User[User Dashboard/API] -->|POST /tasks| API[FastAPI Gateway]
    
    subgraph "The Brain (Synchronous)"
        API --> Intent[Intent Compiler]
        Intent --> Plan[Task Graph Generator]
        Plan -->|DAG Plan| DB[(PostgreSQL)]
        Plan -->|Task Nodes| Redis[Redis Queue]
    end
    
    subgraph "The Body (Asynchronous Workers)"
        Redis --> Worker[Celery Worker]
        
        Worker -->|Decision| Planner[Planner Agent]
        Worker -->|Action| Exec[Executor Agent]
        Worker -->|Validation| Critic[Critic Agent]
        
        Exec -->|Browser Control| PW[Playwright]
        Exec -->|API Request| HTTP[Requests/httpx]
    end
    
    subgraph "Memory & Learning"
        Exec <-->|Read/Write Selectors| WorldModel[(PostgreSQL JSONB)]
        Planner <-->|Semantic Recall| VectorDB[(Qdrant)]
        Critic <-->|Resume Facts| VectorDB
    end

2. Tech Stack & Infrastructure (V3 Upgrades)
Component	Technology	Rationale
Orchestration	Celery + Redis	Essential for managing the execution of complex DAGs (Directed Acyclic Graphs).
API Framework	FastAPI	Handles the synchronous "Planning" phase and websocket status updates.
Database (Relational)	PostgreSQL	Stores Users, Task Logs, and the World Model (JSONB).
Database (Vector)	Qdrant	High-speed semantic search for "Resume Context" and "Task Memory".
Browser Engine	Playwright (Python)	Headless browser automation with stealth plugins.
LLM Inference	Groq (Llama 3)	Ultra-low latency for "Internal Monologue" (DOM analysis).
Reasoning Model	GPT-4o / Claude 3.5	High intelligence for Intent Compilation and Critic verification.
Observability	Flower	Real-time monitoring of Celery worker queues.
3. Database Schema (The "World Model" & Memory)
A. Core Tables (PostgreSQL)

    tasks: id, user_id, raw_prompt, status (queued/running/completed/failed), created_at.

    task_steps: id, task_id, step_order, action_type (search/scrape/apply), status, payload (JSON).

    execution_logs: id, step_id, log_level, message, screenshot_path.

B. The World Model (PostgreSQL - JSONB)

    sites:

        domain (Primary Key): e.g., "linkedin.com"

        login_config: {"requires_2fa": true, "login_url": "/login"}

        selectors: A growing library of what works.
        JSON

        {
          "job_card": ".job-search-card",
          "apply_button": "button[aria-label='Easy Apply']",
          "next_page": ".pagination-next"
        }

C. Vector Memory (Qdrant)

    resume_facts: Chunks of the user's resume (skills, experience).

    task_history: Embeddings of past successful plans. Used to answer: "How did we solve the 'Greenhouse' application last time?"

4. API Endpoints (The Control Plane)
A. Autonomous Task Trigger

    POST /agent/tasks

        Input: {"prompt": "Find 5 remote python jobs and apply."}

        Process:

            Intent Compiler: LLM converts prompt → JSON Goal.

            Planner: Generates a DAG of 10+ steps.

            Queue: Pushes initial steps to Redis.

        Output: {"task_id": "uuid-123", "plan_summary": "Searching LinkedIn & Indeed..."}

B. Real-Time Status

    WS /agent/tasks/{task_id}/stream

        Action: Opens a WebSocket connection.

        Data: Streams live logs ("Scraping Page 1...", "Found 5 jobs...") and screenshots to the frontend.

C. Manual Intervention

    POST /agent/tasks/{task_id}/intervene

        Input: {"step_id": 5, "action": "retry", "human_input": "123456" (2FA Code)}

        Action: Unblocks a "Paused" worker waiting for human help.

5. The "Cognitive Core" Logic Flow

This is the Python logic running inside the Celery Workers.
Phase 1: The Planner (The General)

    Context Retrieval: Query Qdrant for similar past tasks.

        Match: "We applied to a job on this domain 2 days ago."

        Optimization: Reuse the successful selector path from memory.

    Strategy Selection:

        Check: Does World Model have an API endpoint for this site?

        Decision: If Yes → Dispatch API Agent (Fast). If No → Dispatch Browser Agent.

Phase 2: The Executor (The Soldier)

    Navigation: Playwright launches with stealth_mode=True.

    Perception (The "Vision" Loop):

        Try WorldModel selectors first.

        If failed → Capture HTML snippet → Send to Groq LLM: "Find the CSS selector for the 'Submit' button in this HTML."

    Action: await page.click(selector) with randomized human delays.

Phase 3: The Critic (The Auditor)

    Trigger: Before any form submission or data save.

    Input: The filled form data + User Resume.

    Prompt: "You are a strict auditor. Does the form data accurately reflect the resume? Are there hallucinations?"

    Result:

        Pass: Allow submission.

        Fail: Throw ValidationException, trigger Recovery Agent to fix the specific field.

Phase 4: The Learner (The Scientist)

    Trigger: Task Success.

    Action: Extract the selectors and logic that actually worked.

    Update: UPDATE sites SET selectors = ... WHERE domain = ...

    Impact: The system gets faster and more reliable with every single job it runs.