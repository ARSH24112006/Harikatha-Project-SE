export type Status = { stage: string; detail: string; updated_at: string };

export type GenerateRequest = {
  title: string;
  story: string;
  language: string;
  duration_minutes: number;
};

const BASE = "/api/v1";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const createPerformance = (req: GenerateRequest) =>
  fetch(`${BASE}/performances`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  }).then((r) => json<{ id: string; status: Status }>(r));

export const getStatus = (id: string) =>
  fetch(`${BASE}/performances/${id}/status`).then((r) => json<Status>(r));

export const render = (id: string) =>
  fetch(`${BASE}/performances/${id}/render`, { method: "POST" }).then((r) => json<Status>(r));
