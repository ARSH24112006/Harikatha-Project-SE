import { useEffect, useState } from "react";
import { createPerformance, getStatus, render, type Status } from "./api";

export default function App() {
  const [title, setTitle] = useState("");
  const [story, setStory] = useState("");
  const [language, setLanguage] = useState("en-IN");
  const [minutes, setMinutes] = useState(8);
  const [id, setId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Poll status until the performance is done or errored.
  useEffect(() => {
    if (!id || status?.stage === "done" || status?.stage === "error") return;
    const t = setInterval(() => getStatus(id).then(setStatus).catch((e) => setError(String(e))), 2000);
    return () => clearInterval(t);
  }, [id, status?.stage]);

  async function onGenerate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const r = await createPerformance({ title, story, language, duration_minutes: minutes });
      setId(r.id);
      setStatus(r.status);
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <main style={{ maxWidth: 640, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>Harikatha</h1>
      <form onSubmit={onGenerate} style={{ display: "grid", gap: 8 }}>
        <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} required />
        <textarea placeholder="Story" rows={6} value={story} onChange={(e) => setStory(e.target.value)} required />
        <select value={language} onChange={(e) => setLanguage(e.target.value)}>
          <option value="en-IN">English</option>
          <option value="hi-IN">Hindi</option>
          <option value="te-IN">Telugu</option>
          <option value="ta-IN">Tamil</option>
          <option value="kn-IN">Kannada</option>
        </select>
        <label>
          Duration (minutes){" "}
          <input type="number" min={1} max={60} value={minutes} onChange={(e) => setMinutes(+e.target.value)} />
        </label>
        <button type="submit">Generate script</button>
      </form>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {id && status && (
        <section>
          <h2>Performance {id}</h2>
          <p>Stage: <b>{status.stage}</b> {status.detail}</p>
          <button onClick={() => render(id).then(setStatus).catch((e) => setError(String(e)))}>
            Render performance
          </button>
          {status.stage === "done" && <audio controls src={`/api/v1/performances/${id}/audio?fmt=mp3`} />}
        </section>
      )}
    </main>
  );
}
