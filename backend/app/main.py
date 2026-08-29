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
            "is_admin": "BOOLEAN NOT NULL DEFAULT 0",
        },
        "questions": {
            "updated_at": "TIMESTAMP",
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
                text("UPDATE users SET is_admin = 1 WHERE email = 'demo@gatetest.com'")
            )
        conn.commit()


_run_migrations()
Base.metadata.create_all(bind=engine)

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
            buf.append(now)
            self.hits[key] = buf
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

app.include_router(auth_routes.auth, prefix="/api")
app.include_router(routes.api, prefix="/api")


@app.get("/")
def root():
    return {"message": settings.app_name, "docs": "/docs"}
