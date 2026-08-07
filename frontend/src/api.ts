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

/**
 * Static demo mode (GitHub Pages): there is no backend, so reads are served
 * from pre-baked JSON exported by `scripts/export_demo_data.py` and the
 * session-control mutations are disabled with an explanatory message.
 * Payload shapes are identical to the live API, so nothing else changes.
 */
export const IS_STATIC_DEMO = import.meta.env.VITE_DEMO_STATIC === "true";

const DEMO_BASE = `${import.meta.env.BASE_URL}demo-data`;

export const DEMO_NOTICE =
  "This is a static demo. Live capture needs the Python backend running " +
  "locally, so clone the repo to process your own video.";

class DemoUnavailableError extends Error {
  constructor() {
    super(DEMO_NOTICE);
    this.name = "DemoUnavailableError";
  }
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

/** Read helper: hits the API normally, or a static JSON file in demo mode. */
async function getJson<T>(path: string, demoFile?: string): Promise<T> {
  if (IS_STATIC_DEMO) {
    if (!demoFile) throw new DemoUnavailableError();
    return fetchJson<T>(`${DEMO_BASE}/${demoFile}`);
  }
  return fetchJson<T>(`${BASE}${path}`);
}

export const api = {
  health: () => getJson<HealthResponse>("/health", "health.json"),
  sessions: () => getJson<SessionInfo[]>("/sessions", "sessions.json"),
  analytics: (sessionId?: number) =>
    getJson<AnalyticsResponse>(
      `/analytics${sessionId ? `?session_id=${sessionId}` : ""}`,
      "analytics.json",
    ),
  students: (sessionId?: number) =>
    getJson<StudentStats[]>(
      `/students${sessionId ? `?session_id=${sessionId}` : ""}`,
      "students.json",
    ),
  attendance: (sessionId?: number) =>
    getJson<{ session_id: number; attendance: AttendanceEntry[] }>(
      `/attendance${sessionId ? `?session_id=${sessionId}` : ""}`,
      "attendance.json",
    ),
  statistics: (sessionId?: number) =>
    getJson<StatisticsResponse>(
      `/statistics${sessionId ? `?session_id=${sessionId}` : ""}`,
      "statistics.json",
    ),

  studentTimeline: (studentId: number, sessionId?: number) =>
    getJson<StudentTimelinePoint[]>(
      `/students/${studentId}/timeline${sessionId ? `?session_id=${sessionId}` : ""}`,
      `student-${studentId}-timeline.json`,
    ),

  csvUrl: (sessionId?: number) =>
    IS_STATIC_DEMO
      ? `${DEMO_BASE}/students.csv`
      : `${BASE}/analytics/export.csv${sessionId ? `?session_id=${sessionId}` : ""}`,

  streamStart: async (source: string | null, sessionName: string) => {
    if (IS_STATIC_DEMO) throw new DemoUnavailableError();
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
    if (IS_STATIC_DEMO) throw new DemoUnavailableError();
    const res = await fetch(`${BASE}/stream/stop`, { method: "POST" });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail ?? "Failed to stop stream");
    return body as { ok: boolean; message: string };
  },

  uploadVideo: async (file: File) => {
    if (IS_STATIC_DEMO) throw new DemoUnavailableError();
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
