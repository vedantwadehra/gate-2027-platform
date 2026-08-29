'use client';

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getToken } from "../lib/auth";

type QItem = {
  id: string;
  paper: string;
  section?: string | null;
  text: string;
  options: string[];
  answer: number;
  explanation?: string;
  folder?: string | null;
  tags?: string[];
};

export default function ReviewPage() {
  const [bookmarks, setBookmarks] = useState<QItem[]>([]);
  const [wrong, setWrong] = useState<QItem[]>([]);
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [noAuth, setNoAuth] = useState(false);
  const [practicePaper, setPracticePaper] = useState("CS");
  const [folderFilter, setFolderFilter] = useState("");
  const [editFolder, setEditFolder] = useState<Record<number, string>>({});
  const [editTags, setEditTags] = useState<Record<number, string>>({});
  const [editingId, setEditingId] = useState<number | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setNoAuth(true);
      setLoading(false);
      return;
    }
    Promise.all([
      fetch("/api/bookmarks", { headers: { Authorization: `Bearer ${token}` } }),
      fetch("/api/review/wrong", { headers: { Authorization: `Bearer ${token}` } }),
    ])
      .then(async ([b, w]) => {
        if (b.status === 401) {
          setNoAuth(true);
          return;
        }
        setBookmarks((await b.json()) as QItem[]);
        setWrong((await w.json()) as QItem[]);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="muted">Loading…</p>;
  if (noAuth)
    return (
      <div>
        <h2 className="section-title">Review</h2>
        <p className="muted">
          Please <Link className="btn" href="/auth">Login</Link> to see your
          bookmarked questions and wrong-answer review.
        </p>
      </div>
    );

  function toggle(id: string) {
    setRevealed((p) => ({ ...p, [id]: !p[id] }));
  }

  async function saveMeta(bmId: number) {
    const token = getToken();
    const r = await fetch(`/api/bookmarks/${bmId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        folder: editFolder[bmId] ?? null,
        tags: (editTags[bmId] ?? "")
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      }),
    });
    if (r.ok) {
      const d = await r.json();
      setBookmarks((prev) =>
        prev.map((x, i) =>
          x.id === String(bmId) ? { ...x, folder: d.folder, tags: d.tags } : x
        )
      );
      setEditingId(null);
    }
  }

  const folders = Array.from(
    new Set(bookmarks.map((b) => b.folder || "Unfiled"))
  ).sort();
  const visibleBookmarks = folderFilter
    ? bookmarks.filter((b) => (b.folder || "Unfiled") === folderFilter)
    : bookmarks;

  function renderList(items: QItem[], emptyMsg: string, withMeta = false) {
    if (items.length === 0) return <p className="muted">{emptyMsg}</p>;
    return items.map((q) => {
      const bmId = Number(q.id);
      return (
        <div className="question" key={q.id}>
          <div className="qtext">{q.text}</div>
          <div style={{ marginBottom: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
            <span className="chip">{q.section || q.paper}</span>
            {(q.tags || []).map((t) => (
              <span key={t} className="chip" style={{ background: "#e7e7ff", color: "#333" }}>
                #{t}
              </span>
            ))}
            {q.folder && <span className="badge">📁 {q.folder}</span>}
          </div>
          <ul style={{ margin: "6px 0 10px", paddingLeft: 18, fontSize: 14 }}>
            {q.options.map((o, i) => (
              <li key={i} style={revealed[q.id] && i === q.answer ? { color: "var(--ok)", fontWeight: 600 } : undefined}>
                {o}
              </li>
            ))}
          </ul>
          <button className="btn secondary" onClick={() => toggle(q.id)}>
            {revealed[q.id] ? "Hide answer" : "Show answer"}
          </button>
          {revealed[q.id] && (
            <div className="muted" style={{ marginTop: 10, fontSize: 13 }}>
              <strong>Explanation:</strong> {q.explanation || "—"}
            </div>
          )}
          {withMeta && (
            <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              {editingId === bmId ? (
                <>
                  <input
                    placeholder="Folder"
                    value={editFolder[bmId] ?? q.folder ?? ""}
                    onChange={(e) => setEditFolder((p) => ({ ...p, [bmId]: e.target.value }))}
                    style={{ background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, padding: "4px 8px", fontSize: 13 }}
                  />
                  <input
                    placeholder="tags, comma sep"
                    value={editTags[bmId] ?? (q.tags || []).join(", ")}
                    onChange={(e) => setEditTags((p) => ({ ...p, [bmId]: e.target.value }))}
                    style={{ background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, padding: "4px 8px", fontSize: 13, minWidth: 160 }}
                  />
                  <button className="btn" onClick={() => saveMeta(bmId)}>Save</button>
                  <button className="btn secondary" onClick={() => setEditingId(null)}>Cancel</button>
                </>
              ) : (
                <button className="btn secondary" onClick={() => setEditingId(bmId)}>
                  Organize (folder/tags)
                </button>
              )}
            </div>
          )}
        </div>
      );
    });
  }

  return (
    <div>
      <h2 className="section-title">Review</h2>

      <div className="card" style={{ marginBottom: 22, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <strong>Practice your bookmarks as a test</strong>
        <select value={practicePaper} onChange={(e) => setPracticePaper(e.target.value)}>
          <option value="CS">CS</option>
          <option value="DA">DA</option>
        </select>
        <Link className="btn" href={`/test/bookmarks?practice=bookmarks&paper=${practicePaper}`}>
          Start practice test
        </Link>
        <span className="muted" style={{ fontSize: 12 }}>
          {bookmarks.filter((b) => b.paper === practicePaper).length} bookmarked {practicePaper} questions
        </span>
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 12 }}>
        <h3 className="section-title" style={{ margin: 0 }}>
          Bookmarked / Flagged ({bookmarks.length})
        </h3>
        {folders.length > 0 && (
          <select value={folderFilter} onChange={(e) => setFolderFilter(e.target.value)}>
            <option value="">All folders</option>
            {folders.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        )}
      </div>
      {renderList(visibleBookmarks, "No bookmarks yet. Use the ☆ button on any test question.", true)}

      <h3 className="section-title" style={{ marginTop: 26 }}>
        Wrong Answers to Review ({wrong.length})
      </h3>
      {renderList(wrong, "No wrong answers recorded. Take a mock test first.")}
    </div>
  );
}
