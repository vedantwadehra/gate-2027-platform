from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _now() -> datetime:
    # Naive UTC everywhere: columns are TIMESTAMP WITHOUT TIME ZONE, and
    # psycopg2 already persisted aware values as naive UTC. Naive keeps SQL
    # comparisons (flashcards due) independent of the session time zone.
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    attempts: Mapped[list["TestAttempt"]] = relationship(back_populates="user")


class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    paper: Mapped[str] = mapped_column(String(10))  # "DA" or "CS"
    score: Mapped[float] = mapped_column(Float)
    total: Mapped[int] = mapped_column(Integer)
    correct: Mapped[int] = mapped_column(Integer)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped["User | None"] = relationship(back_populates="attempts")

    __table_args__ = (
        Index("ix_test_attempts_user_paper", "user_id", "paper"),
        Index("ix_test_attempts_paper", "paper"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    paper: Mapped[str] = mapped_column(String(10))
    role: Mapped[str] = mapped_column(String(10))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(String(8000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class GeneratedQuestion(Base):
    __tablename__ = "generated_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    paper: Mapped[str] = mapped_column(String(10))
    topic: Mapped[str] = mapped_column(String(255))
    section: Mapped[str | None] = mapped_column(String(64), nullable=True)
    question: Mapped[str] = mapped_column(String(2000))
    options: Mapped[list] = mapped_column(JSON)
    answer_index: Mapped[int] = mapped_column(Integer, default=-1)
    explanation: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    paper: Mapped[str] = mapped_column(String(10))
    qid: Mapped[str] = mapped_column(String(64), index=True)
    section: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text: Mapped[str] = mapped_column(String(2000))
    options: Mapped[list] = mapped_column(JSON)
    answer: Mapped[int] = mapped_column(Integer, default=-1)
    explanation: Mapped[str] = mapped_column(String(2000), default="")
    folder: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    paper: Mapped[str] = mapped_column(String(10))
    front: Mapped[str] = mapped_column(String(1000))
    back: Mapped[str] = mapped_column(String(2000))
    source: Mapped[str] = mapped_column(String(255), default="notes")
    # SM-2 spaced-repetition scheduling fields.
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Explanation(Base):
    __tablename__ = "explanations"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper: Mapped[str] = mapped_column(String(10))
    qid: Mapped[str] = mapped_column(String(64), index=True)
    text: Mapped[str] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Question(Base):
    """DB-backed question bank (replaces the static questions.py at runtime)."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper: Mapped[str] = mapped_column(String(10), index=True)
    qid: Mapped[str] = mapped_column(String(64), index=True)
    section: Mapped[str] = mapped_column(String(64), index=True)
    text: Mapped[str] = mapped_column(String(4000))
    options: Mapped[list] = mapped_column(JSON)
    answer: Mapped[int] = mapped_column(Integer, default=0)
    marks: Mapped[int] = mapped_column(Integer, default=1)
    qtype: Mapped[str] = mapped_column(String(8), default="MCQ")
    answer_list: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answer_num: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_tol: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str] = mapped_column(String(4000), default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String(256), nullable=True)
    verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = ({"sqlite_autoincrement": False},)

    def to_dict(self) -> dict:
        return {
            "id": self.qid,
            "db_id": self.id,
            "paper": self.paper,
            "section": self.section,
            "text": self.text,
            "options": self.options,
            "answer": self.answer,
            "marks": self.marks if self.marks is not None else 1,
            "qtype": self.qtype or "MCQ",
            "answer_list": self.answer_list,
            "answer_num": self.answer_num,
            "answer_tol": self.answer_tol,
            "explanation": self.explanation,
            "year": self.year,
            "source": self.source,
            "verified": self.verified,
        }


class ResponseCache(Base):
    """Caches LLM tutor responses keyed by a hash of the prompt/model."""

    __tablename__ = "response_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    value: Mapped[str] = mapped_column(String(8000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
