'use client';

import { useEffect, useState } from "react";
import Link from "next/link";
import Markdown from "../components/Markdown";
import { getToken } from "../lib/auth";

type GQ = {
  id: number;
  paper: string;
  topic: string;
  section: string | null;
  section_name: string;
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

      {(["DA", "CS"] as const).map((paper) => {
        const list = items.filter((q) => q.paper === paper);
        if (!list.length) return null;
        const groups = new Map<string, { name: string; qs: GQ[] }>();
        for (const q of list) {
          const key = q.section || "__general__";
          if (!groups.has(key)) groups.set(key, { name: q.section_name || "General", qs: [] });
          groups.get(key)!.qs.push(q);
        }
        return (
          <div key={paper} style={{ marginTop: 18 }}>
            <h3 className="section-title">
              {paper} · {list.length} question{list.length === 1 ? "" : "s"}
            </h3>
            {[...groups.entries()].map(([key, g]) => (
              <div key={key} style={{ marginTop: 12 }}>
                <h4 style={{ margin: "10px 0 6px" }}>
                  {g.name} · {g.qs.length}
                </h4>
                {g.qs.map((q) => (
                  <QuestionCard
                    key={q.id}
                    q={q}
                    revealed={!!revealed[q.id]}
                    onReveal={() => setRevealed((r) => ({ ...r, [q.id]: true }))}
                  />
                ))}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function QuestionCard({ q, revealed, onReveal }: {
  q: GQ;
  revealed: boolean;
  onReveal: () => void;
}) {
  return (
    <div className="question">
          <div style={{ marginBottom: 6 }}>
            <span className="paper-pill">{q.paper}</span>{" "}
            <span className="chip">{q.topic}</span>
          </div>
          <div className="qtext"><Markdown text={q.question} /></div>
          <div className="options">
            {q.options.map((opt, i) => {
              let cls = "option";
              if (revealed && i === q.answer_index) cls += " correct";
              return (
                <div
                  key={i}
                  className={cls}
                  onClick={onReveal}
                >
                  <span>{String.fromCharCode(65 + i)}.</span>
                  <Markdown text={opt} />
                </div>
              );
            })}
          </div>
          {revealed && q.explanation && (
            <div className="muted" style={{ marginTop: 10, fontSize: 13 }}>
              <strong>Explanation:</strong> <Markdown text={q.explanation} />
            </div>
          )}
    </div>
  );
}
