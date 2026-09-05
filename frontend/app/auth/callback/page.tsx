'use client';

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { setSession } from "../../lib/auth";

/** OAuth landing: backend redirects here as /auth/callback#token=....
 *  The fragment never reaches any server; we read it client-side. */
export default function OAuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState("");

  useEffect(() => {
    const hash = window.location.hash || "";
    const m = hash.match(/(?:^|[&#])token=([^&]+)/);
    if (!m) {
      setError("Login did not complete. Please try again.");
      return;
    }
    try {
      const token = decodeURIComponent(m[1]);
      const payload = JSON.parse(atob(token.split(".")[1]));
      setSession(token, payload.email || "");
    } catch {
      setError("Login did not complete. Please try again.");
      return;
    }
    router.push("/");
  }, [router]);

  return (
    <div style={{ maxWidth: 420, margin: "0 auto" }}>
      <h2 className="section-title">Logging you in…</h2>
      {error && <p className="muted">{error}</p>}
    </div>
  );
}
