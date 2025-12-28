# Project JobHunter V3 🎯

> **Autonomous AI Agent Platform** for intelligent job application automation.

A **Multi-Agent Orchestration System** with:
- **The Brain (FastAPI Backend):** Intent compilation, task planning, and AI orchestration
- **The Hands (Browser Agent):** Playwright-based execution with stealth mode
- **The Eyes (Visual Cortex):** GPT-4o-Vision for screenshot analysis
- **The Immune System (Recovery):** Error handling and self-healing
- **The Dashboard (React Frontend):** Real-time monitoring and control
- **The Extension (Chrome):** DOM interaction and page scraping

## ✨ What's New (Dec 2025)
- **Agent execution pipeline** now performs real browser automation with Playwright — tasks started from the extension or API actually open a browser and execute the plan.
- **Extension:** Added **Resume PDF upload** directly in the popup (uploads to `/api/v1/resume/upload`).
- **Extension:** Background task polling and persistent task state (tracked in the background service worker) so tasks continue to be monitored after switching tabs or closing the popup; desktop notifications on completion.
- **Fixes:** API endpoints now queue and run tasks (no more mocked responses); task status reporting is real-time.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER LAYER                               │
├─────────────────┬──────────────────────┬───────────────────────┤
│   Dashboard     │   Chrome Extension   │    CLI (Future)       │
│   (React+TS)    │   (Plasmo)           │                       │
└────────┬────────┴──────────┬───────────┴───────────────────────┘
         │                   │
         ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                          │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│  │Intent Compiler│  │ Task Planner  │  │ WebSocket Stream    │  │
│  │(GPT-4o)      │  │ (DAG Builder) │  │ (Real-time Updates) │  │
│  └──────────────┘  └───────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT LAYER (Celery)                       │
│  ┌────────────┐  ┌───────────┐  ┌────────────┐  ┌───────────┐  │
│  │ Executor   │  │  Critic   │  │  Recovery  │  │ Learning  │  │
│  │ (Browser)  │  │  (Anti-   │  │  (Error    │  │ (Self-    │  │
│  │            │  │  Halluc.) │  │  Handler)  │  │ Improve)  │  │
│  └────────────┘  └───────────┘  └────────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MEMORY LAYER                               │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│  │ PostgreSQL   │  │ Redis         │  │ ChromaDB            │  │
│  │ (World Model)│  │ (Queue/Cache) │  │ (Vector Memory)     │  │
│  └──────────────┘  └───────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
AI_JOB_AGENT/
├── backend/                    # Python FastAPI Server
│   ├── app/
│   │   ├── agents/             # Browser executor, world model
│   │   ├── api/v1/             # REST + WebSocket endpoints
│   │   ├── core/               # Config, Celery, database
│   │   ├── models/             # SQLAlchemy models
│   │   ├── services/           # Intent, planner, visual cortex
│   │   └── tasks/              # Celery tasks (executor, critic, recovery)
│   ├── scripts/                # Database seeds
│   ├── docker-compose.yml      # Infrastructure (Postgres, Redis, Qdrant)
│   └── requirements.txt
├── frontend/                   # React Dashboard
│   ├── src/
│   │   ├── components/         # UI components
│   │   ├── pages/              # Dashboard, TaskGraph, WorldModel
│   │   ├── stores/             # Zustand state management
│   │   └── services/           # API and WebSocket clients
│   └── package.json
├── extension/                  # Chrome Extension (Plasmo)
│   ├── src/
│   │   ├── background/         # Service worker
│   │   ├── contents/           # Content scripts
│   │   └── popup/              # Extension popup
│   └── package.json
└── design/                     # Architecture documentation
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Docker & Docker Compose**
- **OpenAI API Key**

### 1. Clone and Setup

```bash
git clone <repo-url>
cd AI_JOB_AGENT
```

### 2. Start Infrastructure

```bash
cd backend
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- Qdrant Vector DB (port 6333)

### 3. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Initialize database
alembic upgrade head

# Seed site configurations
python scripts/seed_sites.py

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001  # or set PORT in your environment

# In a separate terminal - Start Celery worker
celery -A app.core.celery_app worker --loglevel=info
```

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at: http://localhost:3000

### 5. Extension Setup (Optional)

```bash
cd extension
npm install
npm run dev  # development (hot reload)
# or for production build
npm run build
```

Load in Chrome:
1. Go to `chrome://extensions/`
2. Enable Developer mode
3. Click "Load unpacked"
4. Select the `extension/build/chrome-mv3-dev` folder

Notes:
- The extension popup includes a **Resume PDF upload** button (PDF only). Uploaded resumes are sent to the backend `/api/v1/resume/upload` endpoint and used to tailor applications.
- Task polling runs in the **background service worker** so tasks continue to be monitored when you switch tabs or close the popup. Notifications are shown when tasks complete.
- Ensure the extension has the **Notifications** permission (added in manifest). If notifications don't appear, confirm Chrome notifications are enabled for the browser.

Using the Extension:
1. Open the popup and click **Upload Resume** (PDF). Wait for confirmation.
2. Enter a prompt like: "Apply to 5 remote Python developer jobs" and press Enter or click 🚀.
3. The popup will show task status; polling continues in the background if you close the popup.
4. When the task completes, you will receive a desktop notification and can view results in the dashboard.

---

## ⚙️ Manual Configuration Required

### 1. Environment Variables

Create `backend/.env`:

```env
# Required - OpenAI
OPENAI_API_KEY=sk-your-openai-api-key

# Required - Database
DATABASE_URL=postgresql://jobhunter:jobhunter@localhost:5432/jobhunter

# Required - Redis
REDIS_URL=redis://localhost:6379/0

# Optional - Groq (for faster LLM)
GROQ_API_KEY=your-groq-api-key

# Optional - Qdrant Cloud
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# Optional - Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
```

### 2. Upload Your Resume

Via API:
```bash
curl -X POST http://localhost:8001/api/v1/resume/upload \\
  -F "file=@your_resume.pdf"
```

Or via Dashboard: Navigate to Settings → Upload Resume

### 3. Browser Authentication (LinkedIn, etc.)

For sites requiring login:
1. Start a task that requires authentication
2. Dashboard will show "Intervention Required"
3. Complete login in the browser window
4. Click "Done" in the dashboard

### 4. Site Selector Updates

If selectors break (sites update their HTML):
1. Go to Dashboard → World Model
2. Find the site configuration
3. Update selectors manually or trigger learning mode

---

## 📋 API Reference

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/resume/upload` | Upload resume PDF |
| POST | `/api/v1/agent/process` | Submit natural language command |
| GET | `/api/v1/agent/tasks` | List all tasks |
| GET | `/api/v1/agent/tasks/{id}` | Get task details |
| POST | `/api/v1/agent/tasks/{id}/pause` | Pause task |
| POST | `/api/v1/agent/tasks/{id}/resume` | Resume task |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `ws://localhost:8001/api/v1/ws` | Main WebSocket (subscribe to tasks) |
| `ws://localhost:8001/api/v1/ws/task/{id}` | Task-specific stream |

### Intervention Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/interventions` | List pending interventions |
| POST | `/api/v1/interventions/{id}/respond` | Submit intervention response |

---

## 🧪 Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | FastAPI, Python 3.10+, SQLAlchemy |
| **Task Queue** | Celery, Redis |
| **Database** | PostgreSQL |
| **Vector Store** | ChromaDB / Qdrant |
| **Browser Automation** | Playwright (stealth mode) |
| **LLM** | GPT-4o, GPT-4o-Vision, Groq (Llama 3) |
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS |
| **State Management** | Zustand |
| **Extension** | Plasmo, Chrome Manifest V3 |

---

## 🔧 Troubleshooting

### Docker Issues
```bash
# Reset all containers
docker-compose down -v
docker-compose up -d
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

### Celery Worker Not Processing
```bash
# Check Redis connection
redis-cli ping

# Restart worker with verbose logging
celery -A app.core.celery_app worker --loglevel=debug
```

### Playwright Browser Issues
```bash
# Install browsers
playwright install chromium

# Install system dependencies (Linux)
playwright install-deps
```

---

## 📚 Documentation

- [agentflow.md](design/agentflow.md) - Autonomous agent flow
- [Architecture.md](design/Architecture.md) - System architecture
- [BTD.md](design/BTD.md) - Backend technical design
- [Prd.md](design/Prd.md) - Product requirements

---

## ✅ Feature Status

- [x] Intent Compiler (NL → Structured Plan)
- [x] Task Planner (DAG Construction)
- [x] Browser Executor (Playwright + Stealth)
- [x] World Model Service (Site Configurations)
- [x] Critic Agent (Anti-Hallucination)
- [x] Recovery Agent (Error Handling)
- [x] Visual Cortex (GPT-4o-Vision)
- [x] Learning Service (Self-Improvement)
- [x] WebSocket Streaming (Real-time Updates)
- [x] Human-in-the-Loop (2FA, CAPTCHA)
- [x] React Dashboard (20+ Components)
- [x] Site Selectors (LinkedIn, Greenhouse, Lever, Workday)
- [ ] OAuth Authentication
- [ ] Multi-user Support
- [ ] Analytics Dashboard

---

## 📝 License

MIT License - See LICENSE file for details.
