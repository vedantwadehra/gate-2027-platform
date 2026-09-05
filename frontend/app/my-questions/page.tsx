'use client';

import { useEffect, useState } from "react";
import Link from "next/link";
import Markdown from "../components/Markdown";

type GQ = {
  id: number;
  paper: string;
  topic: string;
  question: string;
  options: string[];
  answer_index: number;
  explanation: string;
};

function getSession(): string {
  let s = localStorage.getItem("gate_session");
  if (!s) {
    s = Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem("gate_session", s);
  }
  return s;
}

export default function MyQuestionsPage() {
  const [items, setItems] = useState<GQ[]>([]);
  const [loading, setLoading] = useState(true);
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});

  useEffect(() => {
    fetch(`/api/questions/saved?session_id=${getSession()}`)
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
