import { useState } from "react";
import { rate } from "./api";

const FIELDS = ["clarity", "musicality", "harikatha_feel", "fidelity"] as const;

export default function RatingForm({ id }: { id: string }) {
  const [scores, setScores] = useState<Record<(typeof FIELDS)[number], number>>({
    clarity: 3,
    musicality: 3,
    harikatha_feel: 3,
    fidelity: 3,
  });
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState(false);

  if (sent) return <p className="card">Thanks for rating.</p>;
  return (
    <form
      className="card form"
      onSubmit={async (e) => {
        e.preventDefault();
        // Pseudonymous rater id: never a name or email.
        await rate(id, { rater_id: crypto.randomUUID().slice(0, 8), ...scores, comment });
        setSent(true);
      }}
    >
      <h3>Rate this performance</h3>
      {FIELDS.map((f) => (
        <label key={f}>
          {f.replace("_", " ")}: {scores[f]}
          <input
            type="range"
            min={1}
            max={5}
            value={scores[f]}
            onChange={(e) => setScores({ ...scores, [f]: +e.target.value })}
          />
        </label>
      ))}
      <textarea placeholder="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
      <button type="submit">Submit rating</button>
    </form>
  );
}
