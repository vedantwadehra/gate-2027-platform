'use client';

"use client";

import { useEffect, useState } from "react";
import { getToken } from "../lib/auth";

type QItem = {
  id: string;
  db_id?: number;
  paper: string;
  section: string;
  text: string;
  options: string[];
  answer: number;
  explanation: string;
  year?: number | null;
  source?: string | null;
  verified: boolean;
};

const EMPTY = {
  paper: "DA",
  qid: "",
  section: "",
  text: "",
  optionsText: "",
  answer: 0,
  explanation: "",
  year: "",
  source: "",
  verified: false,
};

export default function AdminPage() {
  const [adminKey, setAdminKey] = useState("");
  const [items, setItems] = useState<QItem[]>([]);
  const [total, setTotal] = useState(0);
  const [paper, setPaper] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState<QItem | null>(null);
  const [form, setForm] = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setAdminKey(localStorage.getItem("gate_admin_key") || "");
  }, []);

  function authHeaders() {
    const h: Record<string, string> = { "X-Admin-Key": adminKey };
    const t = getToken();
    if (t) h["Authorization"] = `Bearer ${t}`;
    return h;
  }

  async function load() {
    if (!adminKey) {
      setErr("Enter the admin key (X-Admin-Key) to manage the question bank.");
      return;
    }
    setErr("");
    setLoading(true);
    const params = new URLSearchParams();
    if (paper) params.set("paper", paper);
    if (search) params.set("q", search);
    params.set("limit", "50");
    params.set("offset", String(offset));
    const r = await fetch(`/api/admin/questions?${params.toString()}`, {
      headers: authHeaders(),
    });
    if (r.status === 403) {
      setErr("Admin key rejected.");
      setLoading(false);
      return;
    }
    const d = await r.json();
    setItems(d.items);
    setTotal(d.total);
    setLoading(false);
  }

  useEffect(() => {
    if (adminKey) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adminKey, paper, offset]);

  function saveKey() {
    localStorage.setItem("gate_admin_key", adminKey);
    load();
  }

  function startNew() {
    setEditing(null);
    setForm({ ...EMPTY });
  }

  function startEdit(q: QItem) {
    setEditing(q);
    setForm({
      paper: q.paper,
      qid: q.id,
      section: q.section,
      text: q.text,
      optionsText: (q.options || []).join("\n"),
      answer: q.answer,
      explanation: q.explanation || "",
      year: q.year != null ? String(q.year) : "",
      source: q.source ?? "",
      verified: q.verified,
    });
  }

  async function save() {
    setSaving(true);
    setMsg("");
    const payload = {
      paper: form.paper,
      qid: form.qid,
      section: form.section,
      text: form.text,
      options: form.optionsText.split("\n").map((s) => s.trim()).filter(Boolean),
      answer: Number(form.answer),
      explanation: form.explanation,
      year: form.year ? Number(form.year) : null,
      source: form.source || null,
      verified: form.verified,
    };
    if (!payload.qid || !payload.text || payload.options.length < 2) {
      setMsg("qid, text and at least 2 options are required.");
      setSaving(false);
      return;
    }
    const url = editing
      ? `/api/admin/questions/${editing.id}?paper=${editing.paper}`
      : "/api/admin/questions";
    const method = editing ? "PUT" : "POST";
    const r = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(payload),
    });
    if (r.ok) {
      setMsg(editing ? "Updated." : "Created.");
      setEditing(null);
      await load();
    } else {
      const e = await r.json().catch(() => ({}));
      setMsg(e.detail || "Save failed.");
    }
    setSaving(false);
  }

  async function remove(q: QItem) {
    if (!confirm(`Delete ${q.id}?`)) return;
    const r = await fetch(`/api/admin/questions/${q.id}?paper=${q.paper}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (r.ok) {
      setMsg("Deleted.");
      await load();
    } else {
      setMsg("Delete failed.");
    }
  }

  async function seed() {
    if (!confirm("Seed from questions.py if bank empty?")) return;
    const r = await fetch("/api/admin/seed", { method: "POST", headers: authHeaders() });
    const d = await r.json().catch(() => ({}));
    setMsg(d.message || "Seeded.");
    await load();
  }

  async function reset() {
    if (!confirm("Reset the entire question bank to the seed file? This deletes all edits.")) return;
    const r = await fetch("/api/admin/reset", { method: "POST", headers: authHeaders() });
    const d = await r.json().catch(() => ({}));
    setMsg(d.message || "Reset.");
    await load();
  }

  if (!adminKey) {
    return (
      <div>
        <h2 className="section-title">Question Bank Admin</h2>
        <p className="muted">Enter the admin key to manage questions (stored in localStorage).</p>
        <div style={{ display: "flex", gap: 10 }}>
          <input
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            placeholder="X-Admin-Key"
            style={inp}
          />
          <button className="btn" onClick={saveKey}>Unlock</button>
        </div>
        {err && <p className="muted" style={{ color: "var(--danger)" }}>{err}</p>}
      </div>
    );
  }

  return (
    <div>
      <h2 className="section-title">Question Bank Admin</h2>
      <p className="muted">
        Questions are stored in the database. Edits here are reflected in tests, review
        and the AI tutor immediately.
      </p>

      <div className="card" style={{ marginBottom: 18, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <input value={adminKey} onChange={(e) => setAdminKey(e.target.value)} placeholder="admin key" style={{ ...inp, maxWidth: 200 }} />
        <button className="btn secondary" onClick={saveKey}>Save key</button>
        <select value={paper} onChange={(e) => { setPaper(e.target.value); setOffset(0); }} style={inp}>
          <option value="">All papers</option>
          <option value="DA">DA</option>
          <option value="CS">CS</option>
        </select>
        <input value={search} onChange={(e) => { setSearch(e.target.value); setOffset(0); }} placeholder="search text…" style={inp} />
        <button className="btn secondary" onClick={() => { setOffset(0); load(); }}>Search</button>
        <button className="btn secondary" onClick={startNew}>＋ New question</button>
        <button className="btn secondary" onClick={seed}>Seed</button>
        <button className="btn secondary" onClick={reset}>Reset to seed</button>
      </div>

      {msg && <p className="muted">{msg}</p>}
      {err && <p style={{ color: "var(--danger)" }}>{err}</p>}
      {loading && <p className="muted">Loading…</p>}
      <p className="muted">Showing {items.length} of {total}</p>

      {(editing || form.qid || form.text) && (
        <div className="card" style={{ marginBottom: 18 }}>
          <h3>{editing ? `Edit ${editing.id}` : "New question"}</h3>
          <div style={{ display: "grid", gap: 8 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <select value={form.paper} onChange={(e) => setForm({ ...form, paper: e.target.value })} style={inp}>
                <option value="DA">DA</option>
                <option value="CS">CS</option>
              </select>
              <input placeholder="qid (unique)" value={form.qid} onChange={(e) => setForm({ ...form, qid: e.target.value })} style={inp} />
              <input placeholder="section id" value={form.section} onChange={(e) => setForm({ ...form, section: e.target.value })} style={inp} />
              <label className="filtertoggle">
                <input type="checkbox" checked={form.verified} onChange={(e) => setForm({ ...form, verified: e.target.checked })} /> Verified
              </label>
            </div>
            <textarea placeholder="Question text" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} style={{ ...inp, minHeight: 60 }} />
            <textarea placeholder="Options (one per line)" value={form.optionsText} onChange={(e) => setForm({ ...form, optionsText: e.target.value })} style={{ ...inp, minHeight: 80 }} />
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <label className="filtertoggle">
                Correct option index:
                <input type="number" min={0} value={form.answer} onChange={(e) => setForm({ ...form, answer: Number(e.target.value) })} style={{ ...inp, width: 70 }} />
              </label>
              <input placeholder="year" value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} style={{ ...inp, width: 90 }} />
              <input placeholder="source" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} style={inp} />
            </div>
            <textarea placeholder="Explanation" value={form.explanation} onChange={(e) => setForm({ ...form, explanation: e.target.value })} style={{ ...inp, minHeight: 50 }} />
          </div>
          <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
            <button className="btn" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save"}</button>
            <button className="btn secondary" onClick={startNew}>Cancel</button>
          </div>
        </div>
      )}

      {items.map((q) => (
        <div className="question" key={q.id}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
            <div>
              <span className="chip">{q.paper}</span>
              <span className="chip">{q.section}</span>
              {q.verified && <span className="badge">✓ verified</span>}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="delbtn" onClick={() => startEdit(q)}>✎</button>
              <button className="delbtn" onClick={() => remove(q)}>✕</button>
            </div>
          </div>
          <div className="qtext" style={{ fontSize: 14, marginTop: 8 }}>{q.text}</div>
          <ul style={{ fontSize: 13, margin: "6px 0", paddingLeft: 18 }}>
            {q.options.map((o, i) => (
              <li key={i} style={i === q.answer ? { color: "var(--ok)", fontWeight: 600 } : undefined}>{o}</li>
            ))}
          </ul>
        </div>
      ))}

      {total > items.length && (
        <button className="btn secondary" onClick={() => setOffset(offset + items.length)}>Load more</button>
      )}
    </div>
  );
}

const inp: React.CSSProperties = {
  background: "var(--bg)",
  color: "var(--text)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: "8px 10px",
  fontSize: 14,
};
