import type {
  AnalyticsResponse,
  AttendanceEntry,
  HealthResponse,
  SessionInfo,
  StatisticsResponse,
  StudentStats,
  StudentTimelinePoint,
} from "./types";

// In dev, Vite proxies /api -> FastAPI; in Docker, nginx does the same.
const BASE = "/api";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => getJson<HealthResponse>("/health"),
  sessions: () => getJson<SessionInfo[]>("/sessions"),
  analytics: (sessionId?: number) =>
    getJson<AnalyticsResponse>(
      `/analytics${sessionId ? `?session_id=${sessionId}` : ""}`,
    ),
  students: (sessionId?: number) =>
    getJson<StudentStats[]>(
      `/students${sessionId ? `?session_id=${sessionId}` : ""}`,
    ),
  attendance: (sessionId?: number) =>
    getJson<{ session_id: number; attendance: AttendanceEntry[] }>(
      `/attendance${sessionId ? `?session_id=${sessionId}` : ""}`,
    ),
  statistics: (sessionId?: number) =>
    getJson<StatisticsResponse>(
      `/statistics${sessionId ? `?session_id=${sessionId}` : ""}`,
    ),

  studentTimeline: (studentId: number, sessionId?: number) =>
    getJson<StudentTimelinePoint[]>(
      `/students/${studentId}/timeline${sessionId ? `?session_id=${sessionId}` : ""}`,
    ),

  csvUrl: (sessionId?: number) =>
    `${BASE}/analytics/export.csv${sessionId ? `?session_id=${sessionId}` : ""}`,

  streamStart: async (source: string | null, sessionName: string) => {
    const parsed =
      source === null || source === ""
        ? null
        : /^\d+$/.test(source)
          ? Number(source)
          : source;
    const res = await fetch(`${BASE}/stream/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: parsed, session_name: sessionName }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail ?? "Failed to start stream");
    return body as { ok: boolean; message: string; session_id: number };
  },

  streamStop: async () => {
    const res = await fetch(`${BASE}/stream/stop`, { method: "POST" });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail ?? "Failed to stop stream");
    return body as { ok: boolean; message: string };
  },

  uploadVideo: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/video/upload`, {
      method: "POST",
      body: form,
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail ?? "Upload failed");
    return body as { ok: boolean; session_id: number; filename: string };
  },
};

export function liveSocketUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/live`;
}
