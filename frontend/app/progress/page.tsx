'use client';

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getToken } from "../lib/auth";

type Attempt = {
  id: number;
  paper: string;
  score: number;
  correct: number;
  total: number;
  created_at: string;
  sections: Record<string, { correct: number; total: number }>;
};

type TrendPoint = { date: string; accuracy: number };
type QH = {
  attempt_id: number;
  date: string;
  paper: string;
  section: string;
  qid: string;
  correct: boolean;
  chosen: number | null;
};
type RankEst = {
  score: number;
  is_full: boolean;
  estimated_percentile: number;
  estimated_rank: number;
  cohort_size: number;
  note: string;
};

type Analytics = {
  total_attempts: number;
  avg_score: number;
  by_paper: Record<string, { avg: number; attempts: number }>;
  sections: Record<string, number>;
  strongest: string | null;
  weakest: string | null;
  sections_trend: Record<string, TrendPoint[]>;
  section_improvement: Record<string, number>;
  question_history: QH[];
  rank_estimate: RankEst | null;
};

export default function ProgressPage() {
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [secNames, setSecNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [noAuth, setNoAuth] = useState(false);
  const [qFilter, setQFilter] = useState<"all" | "wrong">("all");

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setNoAuth(true);
      setLoading(false);
      return;
    }
    Promise.all([
      fetch("/api/attempts", { headers: { Authorization: `Bearer ${token}` } }),
      fetch("/api/analytics", { headers: { Authorization: `Bearer ${token}` } }),
      fetch("/api/syllabus/DA"),
      fetch("/api/syllabus/CS"),
    ])
      .then(async ([a, an, da, cs]) => {
        if (a.status === 401) {
          setNoAuth(true);
          return;
        }
        setAttempts(await a.json());
        setAnalytics(await an.json());
        const names: Record<string, string> = {};
        const daJ = await da.json().catch(() => null);
        const csJ = await cs.json().catch(() => null);
        for (const p of [daJ, csJ]) {
          if (p?.sections) p.sections.forEach((s: any) => (names[s.id] = s.name));
        }
        setSecNames(names);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="muted">Loading…</p>;

  if (noAuth)
    return (
      <div>
        <h2 className="section-title">Your Progress</h2>
        <p className="muted">
          Please <Link className="btn" href="/auth">Login</Link> to see your
          attempt history and section-wise analytics.
        </p>
      </div>
    );

  const an = analytics;
  const secEntries = an
    ? Object.entries(an.sections).sort((a, b) => a[1] - b[1])
    : [];

  const qHist = (an?.question_history || []).filter((q) =>
    qFilter === "wrong" ? !q.correct : true
  );

  function Sparkline({ points }: { points: TrendPoint[] }) {
    if (points.length === 0) return null;
    return (
      <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 34, marginTop: 6 }}>
        {points.map((p, i) => (
          <div
            key={i}
            title={`${new Date(p.date).toLocaleDateString()} · ${p.accuracy}%`}
            style={{
              width: 8,
              height: `${Math.max(4, p.accuracy)}%`,
              background: p.accuracy >= 70 ? "var(--ok)" : p.accuracy >= 40 ? "var(--accent)" : "var(--danger)",
              borderRadius: 2,
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <div>
      <h2 className="section-title">Your Progress</h2>

      <div className="card-grid" style={{ marginBottom: 22 }}>
        <div className="card">
          <h3>Attempts</h3>
          <p style={{ fontSize: 28, fontWeight: 700 }}>{an?.total_attempts ?? 0}</p>
        </div>
        <div className="card">
          <h3>Avg Score</h3>
          <p style={{ fontSize: 28, fontWeight: 700, color: "var(--accent-2)" }}>
            {an?.avg_score ?? 0}%
          </p>
        </div>
        <div className="card">
          <h3>Strongest</h3>
          <p className="muted">{an?.strongest ? (secNames[an.strongest] || an.strongest) : "—"}</p>
        </div>
        <div className="card">
          <h3>Weakest</h3>
          <p className="muted">{an?.weakest ? (secNames[an.weakest] || an.weakest) : "—"}</p>
        </div>
      </div>

      {an?.rank_estimate && (
        <div className="card" style={{ marginBottom: 22, borderColor: "var(--accent-2)" }}>
          <h3>Estimated GATE Rank</h3>
          <p style={{ fontSize: 28, fontWeight: 700, color: "var(--accent-2)" }}>
            AIR ~{an.rank_estimate.estimated_rank.toLocaleString()}
          </p>
          <p className="muted">
            From latest {an.rank_estimate.is_full ? "full-length" : "sectional"} mock ·
            score {an.rank_estimate.score}% · estimated percentile{" "}
            <strong>{an.rank_estimate.estimated_percentile}%</strong> (cohort ~
            {an.rank_estimate.cohort_size.toLocaleString()})
          </p>
          <p className="muted" style={{ fontSize: 12 }}>{an.rank_estimate.note}</p>
        </div>
      )}

      <h3 className="section-title">Score Trend</h3>
      {attempts.length === 0 ? (
        <p className="muted">No attempts yet — take a mock test to see your trend.</p>
      ) : (
        <div className="trend">
          {[...attempts].reverse().map((a, i) => (
            <div className="trend-col" key={a.id} title={`${a.paper} · ${a.score}%`}>
              <div className="trend-bar" style={{ height: `${a.score}%` }}>
                <span className="trend-val">{a.score}%</span>
              </div>
              <div className="trend-label">{a.paper}</div>
              <div className="trend-sub">#{attempts.length - i}</div>
            </div>
          ))}
        </div>
      )}

      <h3 className="section-title" style={{ marginTop: 26 }}>
        Topic Weakness &amp; Improvement
      </h3>
      {secEntries.length === 0 && (
        <p className="muted">No data yet — take a mock test to populate analytics.</p>
      )}
      {secEntries.map(([sec, acc]) => {
        const imp = an?.section_improvement?.[sec] ?? 0;
        const trend = an?.sections_trend?.[sec] || [];
        return (
          <div key={sec} className="syllabus-section" style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div className="muted" style={{ fontSize: 13 }}>
                {secNames[sec] || sec} — {acc}%
                {imp !== 0 && (
                  <span style={{ marginLeft: 8, color: imp > 0 ? "var(--ok)" : "var(--danger)", fontWeight: 600 }}>
                    {imp > 0 ? "▲" : "▼"} {Math.abs(imp)} pts
                  </span>
                )}
              </div>
            </div>
            <div
              style={{
                background: "var(--panel-2)",
                borderRadius: 999,
                height: 10,
                overflow: "hidden",
                border: "1px solid var(--border)",
                margin: "4px 0",
              }}
            >
              <div
                style={{
                  width: `${acc}%`,
                  height: "100%",
                  background:
                    acc >= 70 ? "var(--ok)" : acc >= 40 ? "var(--accent)" : "var(--danger)",
                }}
              />
            </div>
            {trend.length > 1 && <Sparkline points={trend} />}
          </div>
        );
      })}

      <h3 className="section-title" style={{ marginTop: 26 }}>
        Question-Level History
      </h3>
      {qHist.length === 0 && (
        <p className="muted">No attempts recorded yet.</p>
      )}
      {qHist.length > 0 && (
        <>
          <div style={{ marginBottom: 10 }}>
            <button
              className="btn secondary"
              onClick={() => setQFilter(qFilter === "all" ? "wrong" : "all")}
            >
              {qFilter === "all" ? "Show wrong only" : "Show all"}
            </button>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                  <th style={{ padding: "6px 8px" }}>Date</th>
                  <th style={{ padding: "6px 8px" }}>Paper</th>
                  <th style={{ padding: "6px 8px" }}>Topic</th>
                  <th style={{ padding: "6px 8px" }}>Result</th>
                </tr>
              </thead>
              <tbody>
                {qHist.slice(0, 200).map((q, i) => (
                  <tr key={i} style={{ borderTop: "1px solid var(--border)" }}>
                    <td style={{ padding: "6px 8px" }}>{new Date(q.date).toLocaleDateString()}</td>
                    <td style={{ padding: "6px 8px" }}>{q.paper}</td>
                    <td style={{ padding: "6px 8px" }}>{secNames[q.section] || q.section}</td>
                    <td style={{ padding: "6px 8px" }}>
                      <span
                        className="chip"
                        style={{
                          background: q.correct ? "#c8e6c9" : "#f8d7da",
                          color: q.correct ? "#256029" : "#842029",
                        }}
                      >
                        {q.correct ? "✓ correct" : "✗ wrong"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h3 className="section-title" style={{ marginTop: 26 }}>
        Attempt History
      </h3>
      {attempts.length === 0 && (
        <p className="muted">
          No attempts yet. <Link href="/test/DA">Take a DA test</Link> or{" "}
          <Link href="/test/CS">CS test</Link>.
        </p>
      )}
      {attempts.map((a) => (
        <div
          key={a.id}
          className="syllabus-section"
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
        >
          <div>
            <strong>{a.paper}</strong> mock — {a.correct}/{a.total} correct
            <div className="muted" style={{ fontSize: 12 }}>
              {new Date(a.created_at).toLocaleString()}
            </div>
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--accent-2)" }}>
            {a.score}%
          </div>
        </div>
      ))}
    </div>
  );
}
