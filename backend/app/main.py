from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.db.session import engine, Base
from app.db import models  # noqa: F401 ensure models imported for create_all
from app.api import routes
from app.api import auth as auth_routes
from sqlalchemy import inspect as sa_inspect, text


def _run_migrations() -> None:
    """Add columns that were added after the tables were first created.

    SQLite's create_all won't ALTER existing tables, so we add new columns
    defensively here (idempotent — no-op if they already exist).
    """
    migrations = {
        "flashcards": {
            "ease": "FLOAT NOT NULL DEFAULT 2.5",
            "interval": "INTEGER NOT NULL DEFAULT 0",
            "reps": "INTEGER NOT NULL DEFAULT 0",
            "lapses": "INTEGER NOT NULL DEFAULT 0",
            "due_at": "DATETIME",
        },
        "bookmarks": {
            "folder": "VARCHAR(64)",
            "tags": "TEXT",
        },
        "users": {
            "is_admin": "BOOLEAN NOT NULL DEFAULT FALSE",
        },
        "questions": {
            "updated_at": "TIMESTAMP",
            "marks": "INTEGER NOT NULL DEFAULT 1",
            "qtype": "VARCHAR(8) NOT NULL DEFAULT 'MCQ'",
            "answer_list": "JSON",
            "answer_num": "FLOAT",
            "answer_tol": "FLOAT",
        },
    }
    inspector = sa_inspect(engine)
    present = set(inspector.get_table_names())
    with engine.connect() as conn:
        for table, cols in migrations.items():
            if table not in present:
                # Fresh DB: create_all will add these columns below.
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for col, ddl in cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        # Grant the demo account admin so the admin UI is usable out of the box.
        if "users" in present:
            conn.execute(
                text("UPDATE users SET is_admin = TRUE WHERE email = 'demo@gatetest.com'")
            )
        # Widen questions.source (64 -> 256) so test-series provenance fits.
        # SQLite ignores VARCHAR lengths, so only Postgres needs the ALTER.
        if "questions" in present and engine.dialect.name == "postgresql":
            cur = conn.execute(
                text(
                    "SELECT character_maximum_length FROM information_schema.columns "
                    "WHERE table_name='questions' AND column_name='source'"
                )
            ).scalar()
            if cur is not None and cur < 256:
                conn.execute(
                    text("ALTER TABLE questions ALTER COLUMN source TYPE VARCHAR(256)")
                )
        # Hot-path indexes (create_all covers fresh DBs; this covers upgrades).
        # CREATE INDEX IF NOT EXISTS is valid on both Postgres and SQLite.
        # Skip tables that don't exist yet (fresh DB: create_all adds them below).
        for table, stmt in (
            ("test_attempts",
             "CREATE INDEX IF NOT EXISTS ix_test_attempts_user_paper "
             "ON test_attempts (user_id, paper)"),
            ("test_attempts",
             "CREATE INDEX IF NOT EXISTS ix_test_attempts_paper "
             "ON test_attempts (paper)"),
            ("generated_questions",
             "CREATE INDEX IF NOT EXISTS ix_generated_questions_user "
             "ON generated_questions (user_id)"),
        ):
            if table in present:
                conn.execute(text(stmt))
        conn.commit()


_run_migrations()
Base.metadata.create_all(bind=engine)

if settings.jwt_secret == "dev-secret-change-me" or settings.admin_key == "admin-dev-key":
    print("WARNING: running with default JWT_SECRET/ADMIN_KEY — set real values in production!")

# Seed the DB-backed question bank from questions.py on first run.
_inspector = sa_inspect(engine)
if "questions" in set(_inspector.get_table_names()):
    from app.db.session import SessionLocal
    from app.data import questions as _qb
    from app.db.models import User
    from app.core.security import hash_password

    _s = SessionLocal()
    try:
        _qb.seed_questions(_s)
        # Ensure the bundled demo account exists (and is an admin) on every DB.
        _demo = _s.query(User).filter(User.email == "demo@gatetest.com").first()
        if _demo is None:
            _s.add(
                User(
                    email="demo@gatetest.com",
                    password_hash=hash_password("test1234"),
                    is_admin=True,
                )
            )
            _s.commit()
    finally:
        _s.close()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Tiny in-memory limiter for expensive LLM endpoints (per-IP)."""

    def __init__(self, app, limit: int = 40, window: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window = window
        self.hits: dict[tuple[str, str], list[float]] = {}

    async def dispatch(self, request, call_next):
        path = request.url.path
        if path.startswith("/api/chat") or path.startswith("/api/generate"):
            import time

            ip = request.client.host if request.client else "anon"
            now = time.time()
            key = (ip, path)
            buf = [t for t in self.hits.get(key, []) if now - t < self.window]
            if len(buf) >= self.limit:
                return JSONResponse(
                    status_code=429, content={"detail": "Rate limit exceeded. Try again shortly."}
                )
            if buf:
                buf.append(now)
                self.hits[key] = buf
            else:
                # Don't retain idle keys; sweep when the map gets large.
                self.hits.pop(key, None)
                self.hits[key] = [now]
                if len(self.hits) > 10000:
                    self.hits = {
                        k: [t for t in v if now - t < self.window]
                        for k, v in self.hits.items()
                    }
                    self.hits = {k: v for k, v in self.hits.items() if v}
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

app.include_router(auth_routes.auth, prefix="/api")
app.include_router(routes.api, prefix="/api")


@app.get("/")
def root():
    return {"message": settings.app_name, "docs": "/docs"}
