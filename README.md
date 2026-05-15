# Project Zero-Day

Multi-agent autonomous security pipeline — 100% Python.

## Structure

```
zero-day/
├── main.py              # FastAPI webhook + pipeline orchestration
├── state.py             # SharedState dataclass
├── llm.py               # Gemini / Groq LLM wrapper
├── agents/              # Agent stubs (logic in later phases)
├── tools/               # Docker + GitHub tool stubs
├── tracing/             # Omium decorator stubs
├── ui/dashboard.py      # Streamlit dashboard
└── target/              # Vulnerable Flask sandbox app
```

## Quick start

### 1. Prerequisites (manual)

- **Python 3.11+**
- **Docker Desktop** (running) — for sandbox tooling in later phases
- API keys: Gemini and/or Groq, Tavily, GitHub PAT (see `.env.example`)

### 2. Setup

```bash
cd zero-day
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your real keys
```

### 3. Run services

**API (from `zero-day/` directory):**

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Dashboard:**

```bash
streamlit run ui/dashboard.py
```

**Trigger a run:**

```bash
curl -X POST http://localhost:8000/webhook -H "Content-Type: application/json" -d "{\"source\": \"manual\"}"
```

**Health check:**

```bash
curl http://localhost:8000/health
```

### 4. Target sandbox (optional)

```bash
cd target
docker build -t zero-day-target:latest .
docker run -p 5000:5000 zero-day-target:latest
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `LLM_PROVIDER` | `gemini` or `groq` |
| `GEMINI_API_KEY` | Google AI Studio key |
| `GROQ_API_KEY` | Groq API key |
| `TAVILY_API_KEY` | Tavily search (Agent 0) |
| `GITHUB_PAT` | Personal access token |
| `GITHUB_REPO` | `owner/repo` for patches |
| `OMIUM_API_KEY` | Omium tracing (future) |
| `API_BASE_URL` | Dashboard → API URL (default `http://localhost:8000`) |

## Current phase

Scaffold only — agents and tools print stub traces and log to `agent_feed`. Implement business logic in the next phase.

## License

TBD
