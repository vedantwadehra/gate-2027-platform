'use client';

import { useEffect, useState } from "react";
import Link from "next/link";
import Markdown from "../components/Markdown";
import { getToken } from "../lib/auth";

type GQ = {
  id: number;
  paper: string;
  topic: string;
  question: string;
  options: string[];
  answer_index: number;
  explanation: string;
};

export default function MyQuestionsPage() {
  const [items, setItems] = useState<GQ[]>([]);
  const [loading, setLoading] = useState(true);
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});

  useEffect(() => {
    // Logged-in rows link by user; anonymous rows link by the device's
    // known chat session ids (the tutor tracks these on every send).
    let ids: string[] = [];
    try {
      const raw = localStorage.getItem("gate_sessions");
      const list = raw ? JSON.parse(raw) : [];
      ids = list.map((s: { session_id: string }) => s.session_id).slice(0, 50);
    } catch {
      /* ignore */
    }
    const token = getToken();
    const qs = ids.length ? `?session_ids=${encodeURIComponent(ids.join(","))}` : "";
    fetch(`/api/questions/saved${qs}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((d: GQ[]) => setItems(d))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="muted">Loading…</p>;

  return (
    <div>
      <h2 className="section-title">My Question Bank</h2>
      <p className="muted">
        AI-generated questions you saved.{" "}
        <Link href="/chat">Generate more in the AI Tutor</Link>.
      </p>

      {items.length === 0 && (
        <p className="muted">No saved questions yet.</p>
      )}

      {items.map((q) => (
        <div className="question" key={q.id}>
          <div style={{ marginBottom: 6 }}>
            <span className="paper-pill">{q.paper}</span>{" "}
            <span className="chip">{q.topic}</span>
          </div>
          <div className="qtext"><Markdown text={q.question} /></div>
          <div className="options">
            {q.options.map((opt, i) => {
              let cls = "option";
              if (revealed[q.id] && i === q.answer_index) cls += " correct";
              return (
                <div
                  key={i}
                  className={cls}
                  onClick={() => setRevealed((r) => ({ ...r, [q.id]: true }))}
                >
                  <span>{String.fromCharCode(65 + i)}.</span>
                  <Markdown text={opt} />
                </div>
              );
            })}
          </div>
          {revealed[q.id] && q.explanation && (
            <div className="muted" style={{ marginTop: 10, fontSize: 13 }}>
              <strong>Explanation:</strong> <Markdown text={q.explanation} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
