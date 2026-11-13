import { useState } from "react";
import type { Segment } from "./api";

const SECTION_LABEL = (s: string) =>
  s.startsWith("nirupana") ? `Nirupana ${s.split("_")[1]}` : s.charAt(0).toUpperCase() + s.slice(1);

function SegmentRow({
  seg,
  active,
  editable,
  onSave,
}: {
  seg: Segment;
  active: boolean;
  editable: boolean;
  onSave: (id: string, text: string) => Promise<void>;
}) {
  const [text, setText] = useState(seg.text);
  const dirty = text !== seg.text;

  return (
    <div className={`segment${active ? " active" : ""}`}>
      <div className="meta">
        <span className="tag">{seg.type}</span>
        <span className="tag">{seg.origin}</span>
        <span>{seg.target_sec.toFixed(0)}s</span>
        {seg.source_ids.length > 0 && <span>source: {seg.source_ids.join(", ")}</span>}
      </div>
      <textarea value={text} rows={2} disabled={!editable} onChange={(e) => setText(e.target.value)} />
      {dirty && editable && (
        <button onClick={() => onSave(seg.id, text)}>Save edit</button>
      )}
    </div>
  );
}

export default function ScriptView({
  segments,
  activeId,
  editable,
  onSave,
}: {
  segments: Segment[];
  activeId: string | null;
  editable: boolean;
  onSave: (id: string, text: string) => Promise<void>;
}) {
  const sections = [...new Set(segments.map((s) => s.section))];
  return (
    <div>
      {sections.map((sec) => (
        <section key={sec} className="card">
          <h3>{SECTION_LABEL(sec)}</h3>
          {segments
            .filter((s) => s.section === sec)
            // key includes text so a saved or regenerated segment resets its draft
            .map((s) => (
              <SegmentRow key={`${s.id}:${s.text}`} seg={s} active={s.id === activeId} editable={editable} onSave={onSave} />
            ))}
        </section>
      ))}
    </div>
  );
}
