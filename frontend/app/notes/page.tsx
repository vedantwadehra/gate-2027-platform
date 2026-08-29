'use client';

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getToken } from "../lib/auth";

type Card = {
  id: number;
  paper: string;
  front: string;
  back: string;
  source: string;
  created_at: string;
  ease?: number;
  interval?: number;
  reps?: number;
  lapses?: number;
  due_at?: string | null;
};

export default function NotesPage() {
  const [paper, setPaper] = useState("DA");
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [noAuth, setNoAuth] = useState(false);
  const [flipped, setFlipped] = useState<Record<number, boolean>>({});
  const [order, setOrder] = useState<"newest" | "oldest" | "random">("oldest");
  const [editing, setEditing] = useState<number | null>(null);
  const [editFront, setEditFront] = useState("");
  const [editBack, setEditBack] = useState("");
  const [dueMode, setDueMode] = useState(false);
  const [dueCount, setDueCount] = useState(0);

  function visibleCards(): Card[] {
    const list = [...cards];
    if (order === "oldest") return list.sort((a, b) => a.id - b.id);
    if (order === "random") return list.sort(() => Math.random() - 0.5);
    return list; // newest first (API returns desc)
  }

  async function exportCards() {
    const text = cards
      .map((c, i) => `Q${i + 1}: ${c.front}\nA${i + 1}: ${c.back}`)
      .join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      setMsg(`Copied ${cards.length} flashcards to clipboard.`);
    } catch {
      setMsg("Copy failed — select and copy manually.");
    }
  }

  async function saveEdit(id: number) {
    const token = getToken();
    const r = await fetch(`/api/flashcards/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ front: editFront, back: editBack }),
    });
    if (r.ok) {
      setCards((prev) =>
        prev.map((c) => (c.id === id ? { ...c, front: editFront, back: editBack } : c))
      );
      setEditing(null);
    } else {
      setMsg("Update failed.");
    }
  }

  async function loadCards() {
    const token = getToken();
    if (!token) {
      setNoAuth(true);
      setLoading(false);
      return;
    }
    setDueMode(false);
    const r = await fetch(`/api/flashcards?paper=${paper}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (r.status === 401) {
      setNoAuth(true);
      return;
    }
    setCards(await r.json());
    const dr = await fetch(`/api/flashcards/due?paper=${paper}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (dr.ok) setDueCount((await dr.json()).count);
    setLoading(false);
  }

  async function loadDue() {
    const token = getToken();
    if (!token) return;
    setBusy(true);
    const r = await fetch(`/api/flashcards/due?paper=${paper}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (r.ok) {
      const d = await r.json();
      setCards(d.due);
      setDueCount(d.count);
      setDueMode(true);
    }
    setBusy(false);
  }

  async function grade(id: number, g: number) {
    const token = getToken();
    const r = await fetch(`/api/flashcards/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ grade: g }),
    });
    if (r.ok) {
      const d = await r.json();
      setCards((prev) =>
        prev.map((c) =>
          c.id === id
            ? { ...c, ease: d.ease, interval: d.interval, reps: d.reps, lapses: d.lapses, due_at: d.due_at }
            : c
        )
      );
      if (dueMode) setCards((prev) => prev.filter((c) => c.id !== id));
    }
  }

  useEffect(() => {
    loadCards();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paper]);

  async function importNotes() {
    const token = getToken();
    if (!token) {
      setNoAuth(true);
      return;
    }
    setBusy(true);
    setMsg("");
    const fd = new FormData();
    fd.append("paper", paper);
    fd.append("text", text);
    files.forEach((f) => fd.append("files", f));
    const res = await fetch("/api/notes/import", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
    setBusy(false);
    if (res.ok) {
      const r = await res.json();
      setMsg(`Created ${r.created} flashcards.`);
      setText("");
      setFiles([]);
      await loadCards();
    } else {
      const r = await res.json().catch(() => ({}));
      setMsg(r.detail || "Import failed.");
    }
  }

  if (noAuth)
    return (
      <div>
        <h2 className="section-title">Notes → Flashcards</h2>
        <p className="muted">
          Please <Link className="btn" href="/auth">Login</Link> to import notes
          and generate flashcards.
        </p>
      </div>
    );

  return (
    <div>
      <h2 className="section-title">Notes → Flashcards</h2>
      <p className="muted">
        Paste study notes or upload a <code>.txt</code>/<code>.pdf</code> file.
        The AI tutor turns them into revision flashcards.
      </p>

      <div className="card" style={{ marginBottom: 22 }}>
        <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
          <select value={paper} onChange={(e) => setPaper(e.target.value)}>
            <option value="DA">DA</option>
            <option value="CS">CS</option>
          </select>
          <input
            type="file"
            multiple
            accept=".txt,.pdf,.png,.jpg,.jpeg,.bmp,.tiff,.gif"
            onChange={(e) => setFiles(Array.from(e.target.files || []))}
          />
        </div>
        <p className="muted" style={{ fontSize: 12, margin: "0 0 10px" }}>
          Paste notes, upload a <code>.txt</code>/<code>.pdf</code>, or attach an image /
          screenshot (OCR extracts the text) or code snippet.
          {files.length > 0 && ` · ${files.length} file(s) attached`}
        </p>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste your notes or a code snippet here…"
          style={{
            width: "100%",
            minHeight: 140,
            background: "var(--panel)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            padding: 12,
            fontSize: 14,
          }}
        />
        <div style={{ marginTop: 12 }}>
          <button className="btn" onClick={importNotes} disabled={busy || (files.length === 0 && !text.trim())}>
            {busy ? "Generating…" : "Generate Flashcards"}
          </button>
          {msg && <span className="muted" style={{ marginLeft: 12 }}>{msg}</span>}
        </div>
      </div>

      <div
        style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 14 }}
      >
        <h3 className="section-title" style={{ margin: 0 }}>
          Your Flashcards ({cards.length})
        </h3>
        <button className="btn secondary" onClick={loadDue} disabled={busy || dueCount === 0}>
          Study due ({dueCount})
        </button>
        {dueMode && (
          <button className="btn secondary" onClick={loadCards}>Show all</button>
        )}
        <select
          value={order}
          onChange={(e) => setOrder(e.target.value as any)}
          style={{ background: "var(--panel)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, padding: "4px 8px" }}
        >
          <option value="oldest">Study order: oldest first</option>
          <option value="newest">Newest first</option>
          <option value="random">Random</option>
        </select>
        <button className="btn secondary" onClick={exportCards} disabled={cards.length === 0}>
          Export / Copy
        </button>
      </div>
      {dueMode && (
        <p className="muted" style={{ marginBottom: 12 }}>
          Spaced-repetition mode: {cards.length} card(s) due now. Grade each after
          revealing the answer to reschedule it.
        </p>
      )}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : cards.length === 0 ? (
        <p className="muted">No flashcards yet.</p>
      ) : (
        <div className="card-grid">
          {visibleCards().map((c) => (
            <div
              key={c.id}
              className="card flashcard"
              onClick={() => editing !== c.id && setFlipped((p) => ({ ...p, [c.id]: !p[c.id] }))}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="chip">{c.paper}</span>
                <div style={{ display: "flex", gap: 6 }}>
                  {editing !== c.id && (
                    <button
                      className="delbtn"
                      title="Edit flashcard"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditing(c.id);
                        setEditFront(c.front);
                        setEditBack(c.back);
                      }}
                    >
                      ✎
                    </button>
                  )}
                  <button
                    className="delbtn"
                    title="Delete flashcard"
                    onClick={async (e) => {
                      e.stopPropagation();
                      if (!confirm("Delete this flashcard?")) return;
                      const token = getToken();
                      const r = await fetch(`/api/flashcards/${c.id}`, {
                        method: "DELETE",
                        headers: { Authorization: `Bearer ${token}` },
                      });
                      if (r.ok) setCards((prev) => prev.filter((x) => x.id !== c.id));
                    }}
                  >
                    ✕
                  </button>
                </div>
              </div>

              {editing === c.id ? (
                <div onClick={(e) => e.stopPropagation()}>
                  <textarea
                    value={editFront}
                    onChange={(e) => setEditFront(e.target.value)}
                    style={{ width: "100%", minHeight: 50, background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, padding: 8, fontSize: 14, marginBottom: 8 }}
                  />
                  <textarea
                    value={editBack}
                    onChange={(e) => setEditBack(e.target.value)}
                    style={{ width: "100%", minHeight: 50, background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, padding: 8, fontSize: 14, marginBottom: 8 }}
                  />
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn" onClick={() => saveEdit(c.id)}>Save</button>
                    <button className="btn secondary" onClick={() => setEditing(null)}>Cancel</button>
                  </div>
                </div>
              ) : (
                <>
                  <p style={{ marginTop: 10, fontWeight: 600 }}>
                    {flipped[c.id] ? c.back : c.front}
                  </p>
                  {flipped[c.id] ? (
                    <div onClick={(e) => e.stopPropagation()}>
                      <p className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
                        next in {c.interval ?? 0}d · ease {c.ease?.toFixed(2) ?? "2.5"}
                        {c.lapses ? ` · lapses ${c.lapses}` : ""}
                      </p>
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        <button className="grade g-again" onClick={() => grade(c.id, 1)}>Again</button>
                        <button className="grade g-hard" onClick={() => grade(c.id, 3)}>Hard</button>
                        <button className="grade g-good" onClick={() => grade(c.id, 4)}>Good</button>
                        <button className="grade g-easy" onClick={() => grade(c.id, 5)}>Easy</button>
                      </div>
                    </div>
                  ) : (
                    <p className="muted" style={{ fontSize: 12 }}>tap to reveal answer</p>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}
      <style jsx>{`
        .grade {
          border: 1px solid var(--border, #ccc);
          background: #f5f5f5;
          color: #222;
          border-radius: 8px;
          padding: 6px 12px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
        }
        .g-again { background: #f8d7da; border-color: #f5c2c7; }
        .g-hard { background: #ffe0b2; border-color: #ffcc80; }
        .g-good { background: #d1e7dd; border-color: #badbcc; }
        .g-easy { background: #cfe2ff; border-color: #9ec5fe; }
      `}</style>
    </div>
  );
}
