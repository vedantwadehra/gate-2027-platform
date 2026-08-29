'use client';

"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

type Section = {
  id: string;
  name: string;
  topics: string[];
  guide: string;
  notes?: string;
};

export default function GuidePage() {
  const params = useParams();
  const paper = params.paper as string;
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/syllabus/${paper}`)
      .then((r) => r.json())
      .then((data) => {
        setSections(data.sections || []);
        setLoading(false);
      });
  }, [paper]);

  return (
    <div>
      <h2 className="section-title">Syllabus Guide — {paper}</h2>
      {loading && <p className="muted">Loading syllabus…</p>}
      {sections.map((s) => (
        <div className="syllabus-section" key={s.id}>
          <h3>{s.name}</h3>
          <div className="guide">{s.guide}</div>
          {s.notes && (
            <div
              style={{
                marginTop: 8,
                padding: "10px 12px",
                background: "var(--panel-2)",
                border: "1px solid var(--border)",
                borderRadius: 9,
                fontSize: 13,
                color: "var(--muted)",
              }}
            >
              <strong style={{ color: "var(--accent-2)" }}>Study notes: </strong>
              {s.notes}
            </div>
          )}
          <div>
            {s.topics.map((t, i) => (
              <span className="chip" key={i}>{t}</span>
            ))}
          </div>
          <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap" }}>
            <a className="btn secondary" href={`/test/${paper}`}>Practice Full {paper} Test</a>
            <a className="btn" href={`/test/${paper}?section=${s.id}`}>Practice this section</a>
          </div>
        </div>
      ))}
    </div>
  );
}
