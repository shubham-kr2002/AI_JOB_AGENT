Project JobHunter V3: Autonomous Agent Flow
1. The Initialization Flow (Intent to Strategy)

This phase translates a vague human command into a machine-executable strategy.

User Action → System Process → Outcome

    Trigger: User types a command into the Dashboard: "Find and apply to 20 AI Engineering jobs in San Francisco that don't require 5+ years of experience."

    Intent Compilation:

        LLM Analysis: Parses text into structured JSON.

        Extraction: Identifies Goal ("Apply"), Filters ("< 5 years exp", "San Francisco"), Count ("20").

    Strategy Generation:

        Planner Agent: Queries Vector Memory ("Have we done this before?").

        DAG Construction: Builds a Directed Acyclic Graph of tasks:

            Node A: Search LinkedIn (Parallel).

            Node B: Search YCombinator (Parallel).

            Node C: Filter Results (Dependent on A & B).

            Node D: Apply to Job 1... N (Dependent on C).

    Queue Injection: The DAG nodes are pushed to Redis for asynchronous processing.

2. The Cognitive Execution Loop (The "Worker" Phase)

This loop runs for EACH node in the graph (e.g., for every single job application).

Step A: Context Loading

    Worker Wakeup: Celery worker picks up Task #101: Apply to Company X.

    World Model Lookup: System queries the Postgres World Model:

        Question: "Do we know the login URL for Company X's ATS (e.g., Lever)?"

        Question: "What CSS selectors worked last time?"

    Strategy Selection:

        If API known: Switch to Fast Mode (Direct HTTP Request).

        If Unknown: Switch to Browser Mode (Playwright).

Step B: Execution (The "Hands") 4. Action: Execution Agent launches Browser/Request. 5. Perception: * DOM Analysis: Agent scans page. * Selector matching: Uses "Known Selectors" from World Model. If they fail, uses Visual/Semantic Analysis to find new inputs. 6. Interaction: Fills forms using Human-Like Typing (random delays, mouse movements). 7. Hallucination Check: Before clicking submit, Critic Agent reads the filled form: * Check: "Did we put '5 years' exp when the resume says '3'?" * Result: If mismatch -> Trigger Recovery Agent to fix.

Step C: Recovery (If needed)

    Scenario: "Submit" button is blocked by a popup.

    Reaction: Recovery Agent detects ElementClickInterceptedError.

    Fix: Closes popup, waits 2s, retries action.

3. The Verification & Output Flow

    Completion: Form submitted successfully.

    Verification:

        Agent takes a screenshot of the "Success" screen.

        Scrapes the text "Application Received".

    Result Logging: Updates the Task Graph status to "Success".

    Notification: User receives a real-time update on the dashboard: "Applied to OpenAI (1/20)".

4. The Learning Loop (Self-Improvement)

This is the most critical phase where the "Moat" is built.

    Trigger: Task marked as "Success".

    Data Capture: System collects:

        The URL structure.

        The Selectors that actually worked (e.g., input[name="full_name"]).

        The Steps taken (Login -> Click Job -> Apply).

    World Model Update:

        Upsert: Saves these selectors to the World Model DB for the domain jobs.lever.co.

        Benefit: Next time any user applies via Lever, the agent is 10x faster because it doesn't need to "guess" selectors.

    Vector Memory Update:

        Embeds the successful workflow.

        Benefit: If asked "Apply to a similar job," it recalls this specific plan.

Visual Logic Summary (Mermaid Graph)
Code snippet
graph TD
    %% Phase 1: Planning
    User[User Prompt] -->|Intent Compiler| Plan[Task Graph (DAG)]
    Plan -->|Push Nodes| Queue[Redis Task Queue]

    %% Phase 2: Execution Loop
    subgraph "Cognitive Core (Worker)"
        Queue -->|Fetch Task| Planner[Planner Agent]
        Planner -->|Query| WM[(World Model DB)]
        WM -->|Context| Exec[Execution Agent]
        
        Exec -->|Action| Browser[Playwright / API]
        Browser -->|Feedback| DOM[Page State]
        
        DOM -->|Validation| Critic{Critic Agent}
        Critic -- Fail --> Recovery[Recovery Agent]
        Recovery -->|Fix Strategy| Exec
        
        Critic -- Pass --> Success[Task Complete]
    end

    %% Phase 3: Learning
    Success -->|New Selectors| UpdateWM[Update World Model]
    UpdateWM -->|Better Logic| WM
    Success -->|Log Result| Dashboard[User Dashboard]

    %% Styles
    classDef brain fill:#f9f,stroke:#333,stroke-width:2px;
    classDef memory fill:#ff9,stroke:#333,stroke-width:2px;
    class User,Dashboard brain;
    class WM,Queue memory;