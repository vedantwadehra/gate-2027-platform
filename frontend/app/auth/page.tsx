'use client';

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { setSession } from "../lib/auth";

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [providers, setProviders] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetch("/api/auth/providers")
      .then((r) => (r.ok ? r.json() : {}))
      .then((d) => setProviders(d))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetch("/api/auth/providers")
      .then((r) => (r.ok ? r.json() : {}))
      .then((d) => setProviders(d))
      .catch(() => {});
  }, []);

  async function submit() {
    setError("");
    setBusy(true);
    const body =
      mode === "register"
        ? { email, name, password }
        : { email, password };
    try {
      const res = await fetch(`/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const d = data && (data as { detail?: unknown }).detail;
        setError(
          typeof d === "string"
            ? d
            : Array.isArray(d)
              ? d.map((e) => (typeof e === "string" ? e : e?.msg || "Invalid input")).join("; ")
              : "Something went wrong"
        );
        return;
      }
      setSession(data.access_token, data.user.email);
      router.push("/");
    } catch {
      setError("Network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 420, margin: "0 auto" }}>
      <h2 className="section-title">
        {mode === "login" ? "Login" : "Create account"}
      </h2>
      <div
        style={{
          background: "var(--panel)",
          border: "1px solid var(--border)",
          borderRadius: 14,
          padding: 22,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <input
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={inp}
        />
        {mode === "register" && (
          <input
            placeholder="Name (optional)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={inp}
          />
        )}
        <input
          placeholder="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={inp}
        />
        {mode === "register" && (
          <div className="muted" style={{ fontSize: 12 }}>
            Passwords need at least 6 characters. After registering you stay
            logged in on this device.
          </div>
        )}
        {error && <div style={{ color: "var(--danger)", fontSize: 13 }}>{error}</div>}
        <button className="btn" onClick={submit} disabled={busy || !email || !password}>
          {busy ? "Please wait…" : mode === "login" ? "Login" : "Register"}
        </button>
        <button
          className="btn secondary"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login"
            ? "Need an account? Register"
            : "Have an account? Login"}
        </button>
        {(providers.google || providers.github || providers.facebook) && (
          <>
            <div
              className="muted"
              style={{ textAlign: "center", fontSize: 12 }}
            >
              — or continue with —
            </div>
            {(
              [
                ["google", "Google"],
                ["github", "GitHub"],
                ["facebook", "Facebook"],
              ] as [string, string][]
            )
              .filter(([p]) => providers[p])
              .map(([p, label]) => (
                <button
                  key={p}
                  className="btn secondary"
                  onClick={() => {
                    window.location.href = `/api/auth/oauth/${p}`;
                  }}
                >
                  Continue with {label}
                </button>
              ))}
          </>
        )}
      </div>
    </div>
  );
}

const inp: React.CSSProperties = {
  background: "var(--bg)",
  color: "var(--text)",
  border: "1px solid var(--border)",
  borderRadius: 9,
  padding: "10px 12px",
  fontSize: 14,
};
