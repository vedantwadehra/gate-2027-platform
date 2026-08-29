'use client';

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function Navbar() {
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [theme, setTheme] = useState<string>("dark");

  useEffect(() => {
    setToken(localStorage.getItem("gate_token"));
    setEmail(localStorage.getItem("gate_email"));
    setTheme(document.documentElement.dataset.theme || "dark");
  }, []);

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
