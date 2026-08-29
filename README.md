# GATE 2027 — DA & CS Prep Platform (AI-native)

A focused web app to prepare for **GATE 2027 Data Analytics (DA)** and
**Computer Science (CS)** papers, with syllabus guides, mock tests, and an
integrated **AI tutor** (RAG over the syllabus + question bank).

## Architecture

```
gate-2027-platform/
├── backend/      FastAPI + SQLAlchemy + LLM wrapper
│   ├── app/core/   config + provider-agnostic LLM client (OpenAI/Google/Mock)
│   ├── app/db/     models + session (SQLite/Postgres ready)
│   ├── app/data/   GATE DA/CS syllabus + question bank
│   ├── app/services/  mock-test scoring + AI chat (RAG-lite retrieval)
│   └── app/api/    REST routes
└── frontend/     Next.js (App Router) + TypeScript
    └── app/        home, guide/[paper], test/[paper], chat
```

The AI tutor is a first-class feature: the `/api/chat` endpoint retrieves
relevant syllabus/PYQ chunks and sends them as context to the LLM.

## Quick start

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # edit LLM_PROVIDER / LLM_API_KEY for live AI
uvicorn app.main:app --port 8000 --reload
```
API docs: http://localhost:8000/docs

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000

The frontend proxies `/api/*` to the backend on port 8000.

## Features (MVP)
- **Auth:** register/login (JWT), attempts tied to users (`/api/auth/register`, `/api/auth/login`, `/api/me`)
- **Syllabus guides:** DA & CS sections with topic chips + study pointers
- **Mock tests:** full-length timed tests (30 min) with countdown + auto-submit,
  plus section-wise practice (`/api/test/{paper}?section=<id>`)
- **Instant scoring:** per-question correct/wrong + explanations, saved to DB
- **AI tutor:** RAG over syllabus + PYQs (vector TF-IDF/cosine retrieval), Groq/OpenAI/Gemini/Mock
- **Streaming chat:** token-by-token SSE responses (`/api/chat/stream`)
- **Chat memory:** per-session history stored and fed back as context
- **On-demand questions:** `/api/generate` produces JSON MCQs; save to "My Questions"
- **Progress analytics:** per-user attempt history + section-wise breakdown + score-trend chart (`/api/analytics`, `/progress`)
- **Verified PYQ badges:** test UI shows `✓ Verified · GATE <year> · <source>` for official questions
- **Bookmark / flag + review:** star any question (`/api/bookmark`), review bookmarks and all past wrong answers (`/api/review/wrong`, `/review`)
- **Notes → flashcards:** paste or upload `.txt`/`.pdf` notes; AI generates revision flashcards (`/api/notes/import`, `/api/flashcards`, `/notes`)
- **Resilient AI:** chat falls back to the mock tutor on any LLM/network error (never 500s)
- **Expanded bank:** 32 DA + 38 CS questions across all sections, including a curated set of **verified official GATE PYQs** (`verified:true`, `year`, `source` metadata)

## Enable a real LLM

In `backend/.env`:
```
LLM_PROVIDER=groq          # free, no credit card: https://console.groq.com/keys
LLM_API_KEY=gsk_xxx
GROQ_MODEL=llama-3.3-70b-versatile
```
Free options: `groq` (recommended), `google` (Gemini free tier), or `openai` (paid).
Without a key it runs in **mock mode** so the whole app works offline.

## API summary
- `GET  /api/papers` — list papers
- `GET  /api/syllabus/{paper}` — full syllabus guide
- `GET  /api/test/{paper}` — fetch mock test questions
- `POST /api/test/submit` — submit answers, get score + explanations
- `GET  /api/attempts/{paper}` — past attempt scores
- `POST /api/chat` — AI tutor `{ paper, message }` → `{ reply }`

## Roadmap
- Vector-DB backed RAG (e.g. pgvector / FAISS) to replace TF-IDF
- Larger verified PYQ bank (DA & CS) with official answer keys
- Filter tests by verified-only / weak sections
- Public deployment (currently localhost only)
