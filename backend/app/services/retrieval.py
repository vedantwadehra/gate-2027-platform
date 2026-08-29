"""Vector retrieval over syllabus + questions (TF-IDF + cosine, no external deps).

This is a lightweight, dependency-free stand-in for a full vector DB (pgvector /
FAISS). It builds term-frequency inverse-document-frequency vectors for each
chunk and returns the top-k most similar to the query.
"""

import math
import re
from collections import Counter

import numpy as np

from app.data import syllabus
from app.data import questions as qb

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _build_chunks(paper: str) -> list[dict]:
    chunks = []
    for sec in syllabus.get_sections(paper):
        body = (
            f"Section: {sec['name']}\nGuide: {sec['guide']}\n"
            f"Study notes: {sec.get('notes', '')}\nTopics:\n"
            + "\n".join(f"- {t}" for t in sec["topics"])
        )
        chunks.append({"paper": paper, "section": sec["name"], "text": body})
    # Prefer the DB-backed bank (reflects admin edits); fall back to seed.
    try:
        from app.db.session import SessionLocal
        from app.db import models

        db = SessionLocal()
        try:
            qs = db.query(models.Question).filter_by(paper=paper).all()
        finally:
            db.close()
        qlist = [q.to_dict() for q in qs]
    except Exception:
        qlist = qb.QUESTIONS.get(paper, [])
    for q in qlist:
        body = (
            f"Practice question ({q['section']}): {q['text']}\n"
            f"Options: {q['options']}\n"
            f"Answer: {q['options'][q['answer']]}\n"
            f"Explanation: {q['explanation']}"
        )
        chunks.append({"paper": paper, "section": q["section"], "text": body})
    return chunks


def invalidate_index(paper: str) -> None:
    """Drop the cached retrieval index so edits show up on next query."""
    _INDEXES.pop(paper, None)


class _Index:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        docs = [_tokenize(c["text"]) for c in chunks]
        df = Counter()
        for tokens in docs:
            for term in set(tokens):
                df[term] += 1
        self.df = df
        self.idf = {
            term: math.log((len(docs) + 1) / (cnt + 1)) + 1
            for term, cnt in df.items()
        }
        self.vectors = np.array(
            [self._tfidf_vec(tokens) for tokens in docs], dtype=np.float32
        )
        # Normalize for cosine similarity.
        norms = np.linalg.norm(self.vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.vectors /= norms

    def _tfidf_vec(self, tokens: list[str]) -> np.ndarray:
        tf = Counter(tokens)
        dim = max(self.df.keys(), default="")
        size = len(self.df)
        vec = np.zeros(size, dtype=np.float32)
        if size == 0:
            return vec
        term_to_idx = {t: i for i, t in enumerate(self.df.keys())}
        for term, cnt in tf.items():
            if term in term_to_idx:
                vec[term_to_idx[term]] = (1 + math.log(cnt)) * self.idf[term]
        return vec


_INDEXES: dict[str, _Index] = {}
_INDEX_TIMES: dict[str, float] = {}
_INDEX_TTL_SECONDS = 300  # rebuild at most every 5 min even without explicit invalidation


def _get_index(paper: str) -> _Index:
    import time

    stale = (
        paper not in _INDEXES
        or (time.time() - _INDEX_TIMES.get(paper, 0)) > _INDEX_TTL_SECONDS
    )
    if stale:
        _INDEXES[paper] = _Index(_build_chunks(paper))
        _INDEX_TIMES[paper] = time.time()
    return _INDEXES[paper]


def retrieve(paper: str, query: str, k: int = 4) -> list[str]:
    index = _get_index(paper)
    if not index.chunks:
        return []
    q_vec = index._tfidf_vec(_tokenize(query))
    q_norm = np.linalg.norm(q_vec)
    if q_norm > 0:
        q_vec = q_vec / q_norm
    sims = index.vectors @ q_vec
    top = np.argsort(-sims)[:k]
    return [index.chunks[int(i)]["text"] for i in top if sims[i] > 0]
