'use client';

import { useEffect, useRef, useState } from "react";
import Markdown from "../components/Markdown";
import { getToken } from "../lib/auth";

type Msg = { id: number; role: "user" | "bot"; text: string };
type SessionItem = {
  session_id: string;
  paper: string;
  preview: string;
  messages?: number;
  updated_at?: string | null;
  local?: boolean;
};
type LocalSession = {
  session_id: string;
  paper: string;
  preview: string;
  updated_at: string;
};
type GenQ = {
  question: string;
  options: string[];
  answer_index: number;
  explanation: string;
};

let msgId = 0;

export default function ChatPage() {
  const [paper, setPaper] = useState<"DA" | "CS">("DA");
  const [model, setModel] = useState<string>("");
  const [messages, setMessages] = useState<Msg[]>([
    {
      id: msgId++,
      role: "bot",
      text: "Hi! I'm GATEMentor, your AI tutor for GATE 2027. Ask me about any DA or CS topic, request a practice question, or paste a doubt.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [imgFile, setImgFile] = useState<File | null>(null);

  const [topic, setTopic] = useState("");
  const [genQ, setGenQ] = useState<GenQ | null>(null);
  const [genBusy, setGenBusy] = useState(false);
  const [showAnswer, setShowAnswer] = useState(false);
  const [saved, setSaved] = useState(false);

  const logRef = useRef<HTMLDivElement>(null);
  const sessionRef = useRef<string>("");
  const mountedRef = useRef(false);
  const [sessions, setSessions] = useState<SessionItem[]>([]);

  function newSessionId(): string {
    return Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  function greeting(): Msg {
    return {
      id: msgId++,
      role: "bot",
      text: "Hi! I'm GATEMentor, your AI tutor for GATE 2027. Ask me about any DA or CS topic, request a practice question, or paste a doubt.",
    };
  }

  function trackLocalSession(id: string, paperP: string, preview: string) {
    try {
      const raw = localStorage.getItem("gate_sessions");
      const list: LocalSession[] = raw ? JSON.parse(raw) : [];
      if (!list.some((s) => s.session_id === id)) {
        list.unshift({
          session_id: id,
          paper: paperP,
          preview: preview.slice(0, 120),
          updated_at: new Date().toISOString(),
        });
        localStorage.setItem("gate_sessions", JSON.stringify(list.slice(0, 50)));
      }
    } catch {
      /* storage unavailable */
    }
  }

  async function loadSessions() {
    let server: SessionItem[] = [];
    try {
      const token = getToken();
      if (token) {
        const r = await fetch(`/api/chat/sessions?paper=${paper}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (r.ok) server = await r.json();
      }
    } catch {
      /* offline */
    }
    let local: SessionItem[] = [];
    try {
      const raw = localStorage.getItem("gate_sessions");
      const list: LocalSession[] = raw ? JSON.parse(raw) : [];
      local = list
        .filter((s) => s.paper === paper)
        .map((s) => ({ ...s, messages: undefined, local: true }));
    } catch {
      /* ignore */
    }
    const seen = new Set(server.map((s) => s.session_id));
    setSessions([...server, ...local.filter((s) => !seen.has(s.session_id))]);
  }

  function startNewChat() {
    sessionRef.current = newSessionId();
    setMessages([greeting()]);
    setImgFile(null);
  }

  async function openSession(id: string) {
    sessionRef.current = id;
    try {
      const r = await fetch(`/api/chat/history?paper=${paper}&session_id=${id}`);
      const hist: { role: string; content: string }[] = r.ok ? await r.json() : [];
      if (hist && hist.length) {
        setMessages(
          hist.map((h) => ({
            id: msgId++,
            role: (h.role === "assistant" ? "bot" : h.role) as "user" | "bot",
            text: h.content,
          }))
        );
      } else {
        setMessages([greeting()]);
      }
    } catch {
      setMessages([greeting()]);
    }
  }

  async function deleteSession(id: string) {
    try {
      const token = getToken();
      await fetch(`/api/chat/sessions/${id}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const raw = localStorage.getItem("gate_sessions");
      const list: LocalSession[] = raw ? JSON.parse(raw) : [];
      localStorage.setItem(
        "gate_sessions",
        JSON.stringify(list.filter((s) => s.session_id !== id))
      );
    } catch {
      /* ignore */
    }
    if (sessionRef.current === id) startNewChat();
    else loadSessions();
  }

  useEffect(() => {
    if (!mountedRef.current) {
      // Fresh chat on every open; history lives in the panel below.
      mountedRef.current = true;
      sessionRef.current = newSessionId();
      setMessages([greeting()]);
      loadSessions();
      return;
    }
    fetch(`/api/chat/history?paper=${paper}&session_id=${sessionRef.current}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((hist: { role: string; content: string }[]) => {
        if (hist && hist.length) {
          setMessages([
            { id: msgId++, role: "bot", text: "(continued from earlier)" },
            ...hist.map((h) => ({
              id: msgId++,
              role: (h.role === "assistant" ? "bot" : h.role) as "user" | "bot",
              text: h.content,
            })),
          ]);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paper]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages]);

  function appendTo(id: number, token: string) {
    setMessages((m) =>
      m.map((msg) => (msg.id === id ? { ...msg, text: msg.text + token } : msg))
    );
  }

  async function send() {
    const text = input.trim();
    if ((!text && !imgFile) || busy) return;
    trackLocalSession(sessionRef.current, paper, text || "(image attached)");
    const userId = msgId++;
    const botId = msgId++;
    setMessages((m) => [
      ...m,
      { id: userId, role: "user", text: text || "(image attached)" },
      { id: botId, role: "bot", text: "" },
    ]);
    setInput("");
    setBusy(true);
    const fd = new FormData();
    fd.append("paper", paper);
    fd.append("message", text);
    if (sessionRef.current) fd.append("session_id", sessionRef.current);
    if (model) fd.append("model", model);
    if (imgFile) fd.append("image", imgFile);
    try {
      const res = await fetch("/api/chat/stream", { method: "POST", body: fd });
      if (!res.ok) {
        let errMsg = "Sorry, the tutor could not process that.";
        try {
          const j = await res.json();
          if (j.detail) errMsg = j.detail;
        } catch {
          /* keep default */
        }
        appendTo(botId, `\n[${errMsg}]`);
        return;
      }
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n\n")) >= 0) {
          const chunk = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          const line = chunk.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          const data = line.slice(5).trim();
          if (data === "[DONE]") continue;
          try {
            const obj = JSON.parse(data);
            if (obj.token) appendTo(botId, obj.token);
          } catch {
            /* ignore */
          }
        }
      }
    } catch {
      appendTo(botId, "\n[Sorry, the tutor service was unreachable.]");
    } finally {
      setBusy(false);
      setImgFile(null);
      loadSessions();
    }
  }

  async function generate() {
    const t = topic.trim();
    if (!t || genBusy) return;
    setGenBusy(true);
    setGenQ(null);
    setShowAnswer(false);
    setSaved(false);
    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper, topic: t }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data || typeof data.question !== "string") {
        throw new Error(
          (data && data.detail) || `Generation failed (${res.status}). Please retry.`
        );
      }
      setGenQ(data);
    } catch (e: unknown) {
      setGenQ({
        question: e instanceof Error ? e.message : "Generation failed. Please retry.",
        options: [],
        answer_index: -1,
        explanation: "",
      });
    } finally {
      setGenBusy(false);
    }
  }

  async function saveQuestion() {
    if (!genQ) return;
    const token = getToken();
    const res = await fetch("/api/generate/save", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        paper,
        topic: topic.trim(),
        question: genQ.question,
        options: genQ.options,
        answer_index: genQ.answer_index,
        explanation: genQ.explanation,
        session_id: sessionRef.current,
      }),
    });
    if (res.ok) setSaved(true);
    else alert("Could not save this question. Please retry.");
  }

  return (
    <div>
      <h2 className="section-title">
        AI Tutor{" "}
          <select
          value={paper}
          onChange={(e) => setPaper(e.target.value as "DA" | "CS")}
          style={{
            background: "var(--panel)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "4px 8px",
          }}
        >
          <option value="DA">DA</option>
          <option value="CS">CS</option>
        </select>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          title="Model"
          style={{
            background: "var(--panel)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "4px 8px",
          }}
        >
          <option value="">Default (Groq)</option>
          <option value="openai/gpt-oss-120b">Groq · gpt-oss-120b</option>
          <option value="qwen/qwen3.6-27b">Groq · Qwen 3.6 27B</option>
          <option value="groq/compound">Groq · Compound</option>
          <option value="mock">Mock (offline)</option>
        </select>
      </h2>

      <div
        style={{
          background: "var(--panel)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          padding: 16,
          marginBottom: 18,
        }}
      >
        <strong>Generate a practice question</strong>
        <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
          <input
            placeholder="Topic e.g. 'gradient descent' or 'IPC'"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            style={{
              flex: 1,
              background: "var(--bg)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 9,
              padding: "9px 12px",
              fontSize: 14,
            }}
          />
          <button className="btn" onClick={generate} disabled={genBusy || !topic.trim()}>
            {genBusy ? "Generating…" : "Generate"}
          </button>
        </div>

          {genQ && (
          <div style={{ marginTop: 14 }}>
            <div style={{ fontWeight: 600, marginBottom: 10 }}>
              <Markdown text={genQ.question} />
            </div>
            <div className="options">
              {genQ.options.map((opt, i) => {
                let cls = "option";
                if (showAnswer && i === genQ.answer_index) cls += " correct";
                return (
                  <div key={i} className={cls}>
                    <span>{String.fromCharCode(65 + i)}.</span>
                    <Markdown text={opt} />
                  </div>
                );
              })}
            </div>
            {genQ.options.length > 0 && (
              <button
                className="btn secondary"
                style={{ marginTop: 12 }}
                onClick={() => setShowAnswer(true)}
                disabled={showAnswer}
              >
                {showAnswer ? "Answer revealed" : "Show answer & explanation"}
              </button>
            )}
            {showAnswer && genQ.explanation && (
              <div className="muted" style={{ marginTop: 10, fontSize: 13 }}>
                <strong>Explanation:</strong>{" "}
                <Markdown text={genQ.explanation} />
              </div>
            )}
            <div style={{ marginTop: 12, display: "flex", gap: 10 }}>
              {!saved ? (
                <button className="btn" onClick={saveQuestion} disabled={genBusy}>
                  Save to my bank
                </button>
              ) : (
                <span className="chip" style={{ alignSelf: "center" }}>
                  ✓ Saved to My Questions
                </span>
              )}
              <a className="btn secondary" href="/my-questions">
                View my bank
              </a>
            </div>
          </div>
        )}
      </div>

      <div
        style={{
          background: "var(--panel)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          padding: 16,
          marginBottom: 18,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <strong>Chat history</strong>
          <button className="btn secondary" onClick={startNewChat}>
            + New chat
          </button>
        </div>
        {sessions.length === 0 ? (
          <p className="muted" style={{ fontSize: 13, marginBottom: 0 }}>
            No past chats yet. Each visit starts fresh; previous chats appear here.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
            {sessions.map((s) => (
              <div
                key={s.session_id}
                style={{ display: "flex", gap: 8, alignItems: "center" }}
              >
                <button
                  className="btn secondary"
                  style={{
                    flex: 1,
                    textAlign: "left",
                    fontWeight: s.session_id === sessionRef.current ? 700 : 400,
                  }}
                  onClick={() => openSession(s.session_id)}
                  title={s.preview}
                >
                  {(s.preview || "(image chat)").slice(0, 60)}
                  <span className="muted" style={{ fontSize: 12 }}>
                    {" "}
                    · {s.messages !== undefined ? `${s.messages} msgs · ` : ""}
                    {s.updated_at
                      ? new Date(s.updated_at).toLocaleString()
                      : "this device"}
                  </span>
                </button>
                <button
                  className="btn secondary"
                  title="Delete this chat"
                  onClick={() => deleteSession(s.session_id)}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="chat-box">
        <div className="chat-log" ref={logRef}>
          {messages.map((m) => (
            <div key={m.id} className={`msg ${m.role}`}>
              {m.role === "bot" ? (
                m.text ? (
                  <Markdown text={m.text} />
                ) : (
                  busy ? "…" : ""
                )
              ) : (
                m.text
              )}
            </div>
          ))}
        </div>
        <div className="chat-input">
          {imgFile && (
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
              <span className="chip">
                {imgFile.name}
                <button
                  onClick={() => setImgFile(null)}
                  style={{
                    marginLeft: 6,
                    background: "transparent",
                    border: "none",
                    color: "inherit",
                    cursor: "pointer",
                  }}
                >
                  ×
                </button>
              </span>
              <span className="muted" style={{ fontSize: 12 }}>
                Attached — tutor will read it (OCR or vision).
              </span>
            </div>
          )}
          <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
            <label
              className="btn secondary"
              style={{ flex: "none", cursor: "pointer" }}
              title="Attach an image (diagram, notes, question)"
            >
              Attach image
              <input
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={(e) => setImgFile(e.target.files?.[0] || null)}
              />
            </label>
            <textarea
              rows={2}
              placeholder="Ask a doubt or request a practice question…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <button className="btn" onClick={send} disabled={busy}>
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
