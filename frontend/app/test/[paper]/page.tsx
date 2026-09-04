'use client';

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { getToken } from "../../lib/auth";

type Question = {
  id: string;
  section: string;
  text: string;
  options: string[];
  marks: number;
  qtype: "MCQ" | "MSQ" | "NAT";
  year?: number | null;
  source?: string | null;
  verified?: boolean;
  difficulty?: string;
};

type ResultItem = {
  id: string;
  qtype?: "MCQ" | "MSQ" | "NAT";
  chosen: number | number[] | string | null;
  correct_option: string | null;
  correct_options?: string[] | null;
  correct_value?: number | null;
  correct_tol?: number | null;
  is_correct: boolean;
  marks: number;
  max_marks: number;
  explanation: string;
};

type TestData = {
  paper: string;
  section: string | null;
  is_full?: boolean;
  paper_set?: number | null;
  sets_total?: number;
  topic_set?: number | null;
  topic_sets_total?: number;
  total_matched?: number;
  total_marks?: number;
  duration_minutes: number;
  title: string;
  section_names: Record<string, string>;
  questions: Question[];
};

type PaperSetInfo = { set: number; title: string; total_questions: number; total_marks: number };
type SectionInfo = { id: string; name: string };
type TopicInfo = { id: string; name: string; questions: number; sets: number };

type SubmitResponse = {
  score: number;
  correct: number;
  total: number;
  marks_obtained: number;
  max_marks: number;
  results: ResultItem[];
};

function evalCalc(expr: string): string {
  if (!/^[0-9+\-*/().\s]+$/.test(expr)) return "err";
  try {
    // eslint-disable-next-line no-new-func
    const v = Function(`"use strict";return (${expr})`)();
    if (!isFinite(v)) return "err";
    return String(Math.round(v * 1e6) / 1e6);
  } catch {
    return "err";
  }
}

export default function TestPage() {
  const params = useParams();
  const paramsPaper = params.paper as string;
  const [paper, setPaper] = useState(paramsPaper);
  const [practiceBookmarks, setPracticeBookmarks] = useState(false);

  const [data, setData] = useState<TestData | null>(null);
  const [answers, setAnswers] = useState<Record<string, number | number[] | string>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitResponse | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [bookmarked, setBookmarked] = useState<Record<string, boolean>>({});
  const [marked, setMarked] = useState<Record<string, boolean>>({});
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [weakOnly, setWeakOnly] = useState(false);
  const [fullMock, setFullMock] = useState(false);
  const [paperSets, setPaperSets] = useState<PaperSetInfo[]>([]);
  const [paperSet, setPaperSet] = useState<number | null>(null);
  const [topicSections, setTopicSections] = useState<SectionInfo[]>([]);
  const [topic, setTopic] = useState("all");
  const [topicSet, setTopicSet] = useState<number | null>(null);
  const [topicsList, setTopicsList] = useState<TopicInfo[]>([]);
  const [expandedTopic, setExpandedTopic] = useState<string | null>(null);
  const [view, setView] = useState<"choose" | "test">("choose");
  const [difficulty, setDifficulty] = useState("any");
  const [adaptive, setAdaptive] = useState(false);
  const [attemptId, setAttemptId] = useState<number | null>(null);
  const [paused, setPaused] = useState(false);
  const [showCalc, setShowCalc] = useState(false);
  const [activeQ, setActiveQ] = useState(0);
  const [explanations, setExplanations] = useState<Record<string, string>>({});
  const [loadingExp, setLoadingExp] = useState<Record<string, boolean>>({});
  const submittedRef = useRef(false);
  const qRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const isPractice = sp.get("practice") === "bookmarks";
    setPracticeBookmarks(isPractice);
    if (isPractice) setPaper(sp.get("paper") || "CS");
    else setPaper(paramsPaper);
    const ls = JSON.parse(localStorage.getItem("gate_test_settings") || "{}");
    setFullMock(sp.get("mock") === "full" ? true : (ls.fullMock ?? false));
    setPaperSet(sp.get("set") ? parseInt(sp.get("set") as string, 10) : (ls.paperSet ?? null));
    setTopic(sp.get("section") || ls.topic || "all");
    setTopicSet(sp.get("topic_set") ? parseInt(sp.get("topic_set") as string, 10) : (ls.topicSet ?? null));
    if (sp.get("mock") === "full" || sp.get("set") || (sp.get("section") && sp.get("topic_set"))) {
      setView("test");
    } else if (sp.get("section")) {
      setView("test");
    } else {
      setView("choose");
    }
    setDifficulty(sp.get("difficulty") || ls.difficulty || "any");
    setAdaptive(sp.get("adaptive") === "1" ? true : (ls.adaptive ?? false));
    setVerifiedOnly(sp.get("verified_only") === "1" ? true : (ls.verifiedOnly ?? false));
    setWeakOnly(sp.get("weak") === "1" ? true : (ls.weakOnly ?? false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsPaper]);

  useEffect(() => {
    fetch(`/api/test/${paper}/papers`)
      .then((r) => (r.ok ? r.json() : { sets: [], sections: [] }))
      .then((d) => {
        setPaperSets(d.sets || []);
        setTopicSections(d.sections || []);
        setPaperSet((prev) => {
          const total = (d.sets || []).length;
          if (!total) return null;
          if (prev && prev >= 1 && prev <= total) return prev;
          return 1;
        });
      })
      .catch(() => {});
    fetch(`/api/test/${paper}/topics`)
      .then((r) => (r.ok ? r.json() : { topics: [] }))
      .then((d) => setTopicsList(d.topics || []))
      .catch(() => {});
  }, [paper]);

  useEffect(() => {
    if (practiceBookmarks) return;
    localStorage.setItem(
      "gate_test_settings",
      JSON.stringify({ fullMock, paperSet, topic, topicSet, difficulty, adaptive, verifiedOnly, weakOnly })
    );
  }, [fullMock, paperSet, topic, topicSet, difficulty, adaptive, verifiedOnly, weakOnly, practiceBookmarks]);

  useEffect(() => {
    if (!view || (view !== "test" && !practiceBookmarks)) return;
    const paramsQ = new URLSearchParams();
    let loadUrl: string;
    if (practiceBookmarks) {
      loadUrl = `/api/bookmarks/test?paper=${paper}`;
    } else {
      if (fullMock) {
        paramsQ.set("mock", "full");
        if (paperSet) paramsQ.set("set", String(paperSet));
      } else if (topic !== "all") {
        paramsQ.set("section", topic);
        if (topicSet) paramsQ.set("topic_set", String(topicSet));
      }
      if (adaptive) paramsQ.set("adaptive", "1");
      if (difficulty !== "any") paramsQ.set("difficulty", difficulty);
      if (verifiedOnly) paramsQ.set("verified_only", "1");
      if (weakOnly) paramsQ.set("weak", "1");
      const qs = paramsQ.toString();
      loadUrl = `/api/test/${paper}${qs ? `?${qs}` : ""}`;
    }
    fetch(loadUrl)
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setAnswers({});
        setMarked({});
        setResult(null);
        submittedRef.current = false;
        setSecondsLeft(d.duration_minutes * 60);
        setPaused(false);
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paper, fullMock, paperSet, topic, topicSet, view, difficulty, verifiedOnly, weakOnly, practiceBookmarks]);

  function startFullPaper(n: number) {
    setPaperSet(n);
    setFullMock(true);
    setTopic("all");
    setTopicSet(null);
    setView("test");
  }

  function startTopicTest(sec: string, n: number) {
    setTopic(sec);
    setTopicSet(n);
    setFullMock(false);
    setPaperSet(null);
    setView("test");
  }

  function startMixedPractice() {
    setFullMock(false);
    setPaperSet(null);
    setTopicSet(null);
    setTopic("all");
    setView("test");
  }

  function backToChooser() {
    setResult(null);
    setAnswers({});
    setMarked({});
    setView("choose");
  }

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    fetch("/api/bookmarks", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: any[]) => {
        const map: Record<string, boolean> = {};
        rows.forEach((b) => (map[b.qid] = true));
        setBookmarked(map);
      })
      .catch(() => {});
  }, [paper]);

  useEffect(() => {
    if (paused || secondsLeft <= 0 || result) return;
    const t = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          clearInterval(t);
          if (!submittedRef.current) doSubmit();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paused, secondsLeft, result]);

  function choose(qid: string, optIdx: number) {
    if (result) return;
    setAnswers((prev) => ({ ...prev, [qid]: optIdx }));
  }

  function toggleMSQ(qid: string, optIdx: number) {
    if (result) return;
    setAnswers((prev) => {
      const cur = prev[qid];
      const set = new Set(Array.isArray(cur) ? cur : []);
      if (set.has(optIdx)) set.delete(optIdx);
      else set.add(optIdx);
      return { ...prev, [qid]: [...set].sort((a, b) => a - b) };
    });
  }

  function answerNAT(qid: string, value: string) {
    if (result) return;
    setAnswers((prev) => ({ ...prev, [qid]: value }));
  }

  function isAnswered(q: Question): boolean {
    const a = answers[q.id];
    if (a === undefined || a === null) return false;
    if (Array.isArray(a)) return a.length > 0;
    if (typeof a === "string") return a.trim() !== "";
    return true;
  }

  function toggleMark(qid: string) {
    setMarked((prev) => ({ ...prev, [qid]: !prev[qid] }));
  }

  function gotoQ(i: number) {
    setActiveQ(i);
    qRefs.current[i]?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function toggleBookmark(qid: string) {
    const token = getToken();
    if (!token) {
      alert("Login to bookmark questions.");
      return;
    }
    const currently = !!bookmarked[qid];
    const res = await fetch("/api/bookmark", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ paper, qid }),
    });
    if (res.ok) {
      const r = await res.json();
      setBookmarked((prev) => ({ ...prev, [qid]: r.bookmarked }));
    } else if (res.status === 401) {
      alert("Login to bookmark questions.");
    }
  }

  async function doSubmit() {
    if (submittedRef.current || !data) return;
    submittedRef.current = true;
    setSubmitting(true);
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch("/api/test/submit", {
      method: "POST",
      headers,
      body: JSON.stringify({ paper, answers, qids: data.questions.map((q) => q.id) }),
    });
    const r = await res.json();
    setResult(r);
    setAttemptId(r.attempt_id ?? null);
    setSubmitting(false);
  }

  async function downloadPdf() {
    if (!attemptId) return;
    const token = getToken();
    const res = await fetch(`/api/test/export/${attemptId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      alert("Could not generate PDF.");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gate_${paper}_attempt_${attemptId}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function genExplanation(qid: string) {
    setLoadingExp((p) => ({ ...p, [qid]: true }));
    try {
      const r = await fetch(`/api/explain/${paper}/${qid}`);
      const j = await r.json();
      setExplanations((p) => ({ ...p, [qid]: j.explanation }));
    } finally {
      setLoadingExp((p) => ({ ...p, [qid]: false }));
    }
  }

  if (loading || !data) {
    if (view === "choose" && !practiceBookmarks) {
      return (
        <div>
          <h2 className="section-title">
            GATE {paper} — Choose Your Test
          </h2>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>Full-Length Mock Exams</h3>
            <p className="muted" style={{ fontSize: 13 }}>
              65 questions · 100 marks · 180 minutes · real GATE pattern (MCQ/MSQ/NAT)
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
              {paperSets.length === 0 && <span className="muted">Loading papers…</span>}
              {paperSets.map((p) => (
                <button key={p.set} className="btn secondary" onClick={() => startFullPaper(p.set)}>
                  Exam No. {p.set}
                </button>
              ))}
            </div>
          </div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>Topic-Wise Mock Tests</h3>
            <p className="muted" style={{ fontSize: 13 }}>
              Pick a topic, then a test number. Each test has 15–20 questions.
            </p>
            {topicsList.length === 0 && <span className="muted">Loading topics…</span>}
            {topicsList.map((t) => (
              <div key={t.id} style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border, #eee)" }}>
                <button className="btn secondary" onClick={() => setExpandedTopic((p) => (p === t.id ? null : t.id))}>
                  {t.name} · {t.questions} Qs · {t.sets} test{t.sets === 1 ? "" : "s"}
                </button>
                {expandedTopic === t.id && (
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                    {Array.from({ length: t.sets }, (_, i) => i + 1).map((n) => (
                      <button key={n} className="btn secondary" onClick={() => startTopicTest(t.id, n)}>
                        Test No. {n}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="card">
            <h3>Quick Mixed Practice</h3>
            <p className="muted" style={{ fontSize: 13 }}>
              A mixed set with filters (verified, weak sections, difficulty, adaptive).
            </p>
            <button className="btn" style={{ marginTop: 8 }} onClick={startMixedPractice}>
              Start Mixed Practice
            </button>
          </div>
        </div>
      );
    }
    return <p className="muted">Loading test…</p>;
  }

  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
  const ss = String(secondsLeft % 60).padStart(2, "0");
  const unanswered = data.questions.filter((q) => !isAnswered(q)).length;

  const numberedSet = (fullMock && paperSet) || (!fullMock && topic !== "all" && topicSet);

  return (
    <div>
      <button className="btn secondary" onClick={backToChooser} style={{ marginBottom: 12 }}>
        ← All {paper} tests
      </button>
      <h2 className="section-title">
        {data.title}{" "}
        <span className="paper-pill">
          {data.questions.length} Qs · {data.duration_minutes}m
          {data.is_full ? " · Full Mock" : ""}
          {typeof data.total_marks === "number" && data.total_marks > 0 ? ` · ${data.total_marks} marks` : ""}
        </span>
      </h2>

      {!result && !practiceBookmarks && !numberedSet && (
        <div className="filterbar">
          <label className="filtertoggle">
            Topic:
            <select value={topic} onChange={(e) => setTopic(e.target.value)}>
              <option value="all">All topics (mixed)</option>
              {topicSections.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </label>
          <label className="filtertoggle">
            <input type="checkbox" checked={verifiedOnly} onChange={(e) => setVerifiedOnly(e.target.checked)} />
            Verified PYQs only
          </label>
          <label className="filtertoggle">
            <input type="checkbox" checked={weakOnly} onChange={(e) => setWeakOnly(e.target.checked)} />
            Focus my weak sections
          </label>
          <label className="filtertoggle">
            Difficulty:
            <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
              <option value="any">Any</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </label>
          <label className="filtertoggle" title="Prioritize your weak sections and harder questions">
            <input type="checkbox" checked={adaptive} onChange={(e) => setAdaptive(e.target.checked)} />
            Adaptive (focus weak areas)
          </label>
          {(verifiedOnly || weakOnly || difficulty !== "any") && (
            <span className="muted" style={{ fontSize: 12 }}>
              Showing {data.questions.length}
              {typeof data.total_matched === "number" && data.total_matched > data.questions.length
                ? ` of ${data.total_matched} matched — pick a numbered topic test for the rest`
                : " questions matched"}
            </span>
          )}
        </div>
      )}

      {/* Sticky control bar */}
      {!result && (
        <div className="testbar">
          <span className="timer" style={{ color: secondsLeft < 60 ? "var(--danger)" : "var(--accent-2)" }}>
            {mm}:{ss}
          </span>
          <button className="btn secondary" onClick={() => setPaused((p) => !p)}>
            {paused ? "Resume" : "Pause"}
          </button>
          <button className="btn secondary" onClick={() => setShowCalc(true)}>Calculator</button>
          <span className="muted">Answered {data.questions.length - unanswered}/{data.questions.length}</span>
          <button className="btn" onClick={doSubmit} disabled={submitting || Object.keys(answers).length === 0}>
            {submitting ? "Scoring…" : "Submit Test"}
          </button>
        </div>
      )}

      {/* Question palette */}
      {!result && (
        <div className="palette">
          {data.questions.map((q, qi) => {
            const st = marked[q.id] ? "mark" : isAnswered(q) ? "ans" : "unans";
            return (
              <button
                key={q.id}
                className={`pal ${st} ${activeQ === qi ? "active" : ""}`}
                onClick={() => gotoQ(qi)}
                title={`Q${qi + 1}`}
              >
                {qi + 1}
              </button>
            );
          })}
        </div>
      )}

      {result && (
        <div className="result-banner">
          <div className="score">
            {typeof result.max_marks === "number" && result.max_marks > 0
              ? `${result.marks_obtained} / ${result.max_marks}`
              : `${result.score}%`}
          </div>
          <div className="muted">
            You got {result.correct} / {result.total} correct
            {typeof result.max_marks === "number" && result.max_marks > 0
              ? ` · ${result.score}% (MCQ −1/3; MSQ/NAT no negative marking)` : ""}
          </div>
        </div>
      )}

      {data.questions.map((q, qi) => {
        const resItem = result?.results.find((r) => r.id === q.id);
        const secName = data.section_names[q.section] || q.section;
        return (
          <div className="question" key={q.id} ref={(el) => { qRefs.current[qi] = el; }}>
            <div className="qhead">
              <div className="qtext">
                {qi + 1}. {q.text}
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                {!result && (
                  <button
                    className={`star ${marked[q.id] ? "on" : ""}`}
                    title="Mark for review"
                    onClick={() => toggleMark(q.id)}
                  >
                    {marked[q.id] ? "✦" : "✧"}
                  </button>
                )}
                <button
                  className={`star ${bookmarked[q.id] ? "on" : ""}`}
                  title={practiceBookmarks ? "Already bookmarked" : (bookmarked[q.id] ? "Remove bookmark" : "Bookmark / flag")}
                  onClick={() => toggleBookmark(q.id)}
                  disabled={!!result || practiceBookmarks}
                >
                  {bookmarked[q.id] ? "★" : "☆"}
                </button>
              </div>
            </div>
            <div style={{ marginBottom: 8 }}>
              <span className="chip">{secName}</span>
              <span className="chip">{q.qtype}</span>
              <span className="chip">{q.marks} mark{q.marks === 1 ? "" : "s"}</span>
              {result && resItem && (
                <span className="chip" style={resItem.marks < 0 ? { background: "#f8d7da", color: "#842029" } : undefined}>
                  {resItem.marks > 0 ? `+${resItem.marks}` : `${resItem.marks}`} / {resItem.max_marks}
                </span>
              )}
              {q.verified && (
                <span className="badge">
                  ✓ Verified{typeof q.year === "number" ? ` · GATE ${q.year}` : ""}
                  {q.source ? ` · ${q.source}` : ""}
                </span>
              )}
              {q.difficulty && <span className={`chip diff-${q.difficulty}`}>{q.difficulty}</span>}
              {marked[q.id] && !result && <span className="chip" style={{ background: "#b8860b", color: "#fff" }}>review</span>}
            </div>
            {q.qtype === "NAT" ? (
              <div className="options">
                <label className="muted" style={{ fontSize: 13 }}>
                  Numerical answer:
                  <input
                    type="text"
                    inputMode="decimal"
                    disabled={!!result}
                    value={typeof answers[q.id] === "string" ? (answers[q.id] as string) : ""}
                    onChange={(e) => answerNAT(q.id, e.target.value)}
                    placeholder="Enter a number"
                    style={{ marginLeft: 8, padding: "6px 10px", borderRadius: 8, border: "1px solid var(--border, #ccc)" }}
                  />
                </label>
                {result && resItem && (
                  <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>
                    Correct: {resItem.correct_value}
                    {(resItem.correct_tol ?? 0) > 0 ? ` ± ${resItem.correct_tol}` : ""}
                    {typeof answers[q.id] === "string" && answers[q.id] !== "" ? ` · You answered: ${answers[q.id]}` : " · Skipped"}
                  </div>
                )}
              </div>
            ) : (
            <div className="options">
              {q.options.map((opt, oi) => {
                let cls = "option";
                const correctIdx = resItem?.correct_option
                  ? resItem.correct_option.charCodeAt(0) - 65
                  : -1;
                const correctSet = new Set(
                  (resItem?.correct_options || []).map((t) => q.options.indexOf(t)).filter((i) => i >= 0)
                );
                const pickedSet = new Set(Array.isArray(answers[q.id]) ? (answers[q.id] as number[]) : []);
                if (result && resItem) {
                  if (q.qtype === "MSQ") {
                    if (correctSet.has(oi)) cls += " correct";
                    else if (pickedSet.has(oi) && !resItem.is_correct) cls += " wrong";
                  } else {
                    if (oi === correctIdx) cls += " correct";
                    else if (answers[q.id] === oi && !resItem.is_correct) cls += " wrong";
                  }
                } else if (q.qtype === "MSQ") {
                  if (pickedSet.has(oi)) cls += " selected";
                } else if (answers[q.id] === oi) cls += " selected";
                return (
                  <div
                    key={oi}
                    className={cls}
                    onClick={() => (q.qtype === "MSQ" ? toggleMSQ(q.id, oi) : choose(q.id, oi))}
                  >
                    <span>{q.qtype === "MSQ" ? (pickedSet.has(oi) ? "☑" : "☐") : `${String.fromCharCode(65 + oi)}.`}</span>
                    <span>{opt}</span>
                  </div>
                );
              })}
            </div>
            )}
            {result && resItem && (
              <div className="expbox">
                <strong>Explanation:</strong>{" "}
                {resItem.explanation ? (
                  resItem.explanation
                ) : explanations[q.id] ? (
                  explanations[q.id]
                ) : (
                  <button className="btn secondary" disabled={loadingExp[q.id]} onClick={() => genExplanation(q.id)}>
                    {loadingExp[q.id] ? "Generating…" : "Generate with AI Tutor"}
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}

      {!result && (
        <button className="btn" onClick={doSubmit} disabled={submitting || Object.keys(answers).length === 0}>
          {submitting ? "Scoring…" : "Submit Test"}
        </button>
      )}
      {result && (
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <button className="btn secondary" onClick={downloadPdf} disabled={!attemptId}>
            Download PDF
          </button>
          <button className="btn secondary" onClick={() => window.print()}>Print / Save
          </button>
          <a className="btn secondary" href={`/chat`}>Discuss with AI Tutor</a>
          <a className="btn secondary" href={`/review`}>Review wrong answers</a>
        </div>
      )}

      {showCalc && (
        <Calculator onClose={() => setShowCalc(false)} />
      )}

      <style jsx>{`
        .testbar {
          position: sticky;
          top: 0;
          z-index: 20;
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;
          padding: 10px 12px;
          background: var(--card, #fff);
          border: 1px solid var(--border, #ddd);
          border-radius: 10px;
          margin-bottom: 14px;
        }
        .timer { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
        .palette {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(34px, 1fr));
          gap: 6px;
          margin-bottom: 16px;
        }
        .pal {
          width: 34px; height: 34px;
          border-radius: 8px; border: 1px solid var(--border, #ccc);
          background: #eee; cursor: pointer; font-weight: 600;
        }
        .pal.ans { background: #c8e6c9; border-color: #66bb6a; }
        .pal.mark { background: #ffe0b2; border-color: #ffa726; }
        .pal.unans { background: #f3f3f3; }
        .pal.active { outline: 3px solid var(--accent-2, #2f6df6); }
        .chip.diff-easy { background: #c8e6c9; color: #256029; }
        .chip.diff-medium { background: #fff3cd; color: #8a6d00; }
        .chip.diff-hard { background: #f8d7da; color: #842029; }
        .expbox {
          margin-top: 10px; font-size: 13px;
          background: var(--card, #fafafa);
          border: 1px solid var(--border, #eee);
          border-radius: 8px; padding: 8px 10px;
        }
      `}</style>
    </div>
  );
}

function Calculator({ onClose }: { onClose: () => void }) {
  const [disp, setDisp] = useState("");
  const keys = ["7", "8", "9", "/", "4", "5", "6", "*", "1", "2", "3", "-", "0", ".", "(", ")", "C", "=", "+"];
  function press(k: string) {
    if (k === "C") return setDisp("");
    if (k === "=") return setDisp(evalCalc(disp));
    setDisp((d) => d + k);
  }
  return (
    <div className="calc-overlay">
      <div className="calc">
        <div className="calc-disp">{disp || "0"}</div>
        <div className="calc-grid">
          {keys.map((k) => (
            <button key={k} className={`calc-key ${k === "=" ? "eq" : ""}`} onClick={() => press(k)}>
              {k}
            </button>
          ))}
        </div>
        <button className="btn" onClick={onClose} style={{ marginTop: 8 }}>Close</button>
      </div>
      <style jsx>{`
        .calc-overlay {
          position: fixed; inset: 0; background: rgba(0,0,0,0.4);
          display: flex; align-items: center; justify-content: center; z-index: 50;
        }
        .calc { background: var(--card, #fff); padding: 16px; border-radius: 12px; width: 260px; }
        .calc-disp {
          background: #111; color: #0f0; font-family: monospace; font-size: 20px;
          padding: 10px; border-radius: 8px; min-height: 44px; word-break: break-all; text-align: right;
        }
        .calc-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 10px; }
        .calc-key {
          padding: 12px; font-size: 16px; border: 1px solid var(--border, #ccc);
          border-radius: 8px; background: #f5f5f5; cursor: pointer;
        }
        .calc-key.eq { background: var(--accent-2, #2f6df6); color: #fff; }
      `}</style>
    </div>
  );
}
