export default function HomePage() {
  return (
    <div>
      <section className="hero">
        <h1>GATE 2027 — DA &amp; CS Prep, Supercharged by AI</h1>
        <p>
          Structured syllabus guides, full-length mock tests, and a personal AI
          tutor that explains, quizzes, and clears your doubts.
        </p>
      </section>

      <div className="card-grid">
        <div className="card">
          <h3>DA Guide</h3>
          <p>Data Analytics / Data Science syllabus, topic guides &amp; weightage.</p>
          <a className="btn" href="/guide/DA">Open Guide</a>
        </div>
        <div className="card">
          <h3>CS Guide</h3>
          <p>Computer Science syllabus with section-wise study pointers.</p>
          <a className="btn" href="/guide/CS">Open Guide</a>
        </div>
        <div className="card">
          <h3>Mock Test — DA</h3>
          <p>Full-length papers (65Q/100m) and topic-wise tests with GATE scoring.</p>
          <a className="btn secondary" href="/test/DA">Choose DA Test</a>
        </div>
        <div className="card">
          <h3>Mock Test — CS</h3>
          <p>Full-length papers and topic-wise tests with detailed solutions.</p>
          <a className="btn secondary" href="/test/CS">Choose CS Test</a>
        </div>
        <div className="card">
          <h3>AI Tutor</h3>
          <p>Ask doubts, generate questions, get exam-focused explanations.</p>
          <a className="btn" href="/chat">Chat Now</a>
        </div>
      </div>
    </div>
  );
}
