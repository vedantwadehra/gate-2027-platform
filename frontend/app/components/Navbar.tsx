'use client';

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navbar() {
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [theme, setTheme] = useState<string>("dark");
  const [imgOk, setImgOk] = useState(true);
  const pathname = usePathname();

  function readSession() {
    setToken(localStorage.getItem("gate_token"));
    setEmail(localStorage.getItem("gate_email"));
    setImgOk(true);
  }

  useEffect(() => {
    readSession();
    setTheme(document.documentElement.dataset.theme || "dark");
    const onStorage = () => readSession();
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [pathname]);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("gate_theme", next);
    setTheme(next);
  }

  function logout() {
    localStorage.removeItem("gate_token");
    localStorage.removeItem("gate_email");
    setToken(null);
    setEmail(null);
    window.location.href = "/";
  }

  return (
    <nav className="navbar">
      <span className="brand">GATEmentor 2027</span>
      <span className="links">
        <Link href="/">Home</Link>
        <Link href="/guide/DA">DA Guide</Link>
        <Link href="/guide/CS">CS Guide</Link>
        <Link href="/test/DA">DA Tests</Link>
        <Link href="/test/CS">CS Tests</Link>
        <Link href="/chat">AI Tutor</Link>
        <Link href="/my-questions">My Questions</Link>
        <Link href="/review">Review</Link>
        <Link href="/notes">Flashcards</Link>
        <Link href="/progress">Progress</Link>
        <Link href="/admin">Admin</Link>
      </span>
      <span style={{ marginLeft: "auto" }} className="links">
        <button className="btn secondary" onClick={toggleTheme} title="Toggle dark mode">
          {theme === "dark" ? "☀ Light" : "🌙 Dark"}
        </button>
        {token ? (
          <>
            <span
              title={email || "Logged in"}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: "50%",
                overflow: "hidden",
                background: "var(--accent-2, #2f6df6)",
                color: "#fff",
                fontWeight: 700,
              }}
            >
              {email && imgOk ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={`https://api.dicebear.com/9.x/adventurer/svg?seed=${encodeURIComponent(email)}`}
                  alt="profile"
                  width={32}
                  height={32}
                  onError={() => setImgOk(false)}
                />
              ) : (
                (email || "?").slice(0, 1).toUpperCase()
              )}
            </span>
            <span className="muted">{email}</span>
            <button className="btn secondary" onClick={logout}>
              Logout
            </button>
          </>
        ) : (
          <Link className="btn" href="/auth">
            Login
          </Link>
        )}
      </span>
    </nav>
  );
}
