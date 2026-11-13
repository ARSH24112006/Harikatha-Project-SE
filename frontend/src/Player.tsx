import { useState } from "react";
import { audioUrl, type Timeline } from "./api";

export default function Player({
  id,
  files,
  timeline,
  onActive,
  onDownloadJson,
}: {
  id: string;
  files: string[];
  timeline: Timeline;
  onActive: (segId: string | null) => void;
  onDownloadJson: (name: "script" | "timeline") => void;
}) {
  const fmt = files.includes("performance.mp3") ? "mp3" : "wav";
  const [t, setT] = useState(0);

  return (
    <div className="card">
      <h3>Performance</h3>
      <audio
        controls
        src={audioUrl(id, fmt)}
        onTimeUpdate={(e) => {
          const now = e.currentTarget.currentTime;
          setT(now);
          onActive(timeline.segments.find((s) => now >= s.start && now < s.end + 0.35)?.id ?? null);
        }}
        onEnded={() => onActive(null)}
      />
      <div className="timeline" title={`${t.toFixed(1)}s / ${timeline.total_sec}s`}>
        {timeline.segments.map((s) => (
          <div
            key={s.id}
            className={`tick${t >= s.start && t < s.end + 0.35 ? " on" : ""}`}
            style={{ width: `${((s.end - s.start) / timeline.total_sec) * 100}%` }}
          />
        ))}
      </div>
      <div className="row">
        {files.map((f) => (
          <a key={f} href={audioUrl(id, f.endsWith("mp3") ? "mp3" : "wav")} download>
            {f}
          </a>
        ))}
        <button onClick={() => onDownloadJson("script")}>script.json</button>
        <button onClick={() => onDownloadJson("timeline")}>timeline.json</button>
      </div>
    </div>
  );
}
