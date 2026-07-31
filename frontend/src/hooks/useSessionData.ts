/**
 * React Query hooks for all backend data.
 *
 * Polling intervals replace the old manual setInterval refresh; queries are
 * deduplicated and cached, so every page can freely mount the same hooks.
 */
import { useQueries, useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { StudentStats } from "../types";

const LIVE_POLL_MS = 4000;
const IDLE_POLL_MS = 15000;

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 5000,
  });
}

/** True while a pipeline session is actively running. */
export function useIsRunning(): boolean {
  const { data } = useHealth();
  return data?.active_session_id != null;
}

function pollMs(running: boolean) {
  return running ? LIVE_POLL_MS : IDLE_POLL_MS;
}

export function useSessions() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: api.sessions,
    refetchInterval: IDLE_POLL_MS,
  });
}

export function useAnalytics(sessionId?: number) {
  const running = useIsRunning();
  return useQuery({
    queryKey: ["analytics", sessionId ?? "latest"],
    queryFn: () => api.analytics(sessionId),
    refetchInterval: pollMs(running),
    retry: 1,
  });
}

export function useStatistics(sessionId?: number) {
  const running = useIsRunning();
  return useQuery({
    queryKey: ["statistics", sessionId ?? "latest"],
    queryFn: () => api.statistics(sessionId),
    refetchInterval: pollMs(running),
    retry: 1,
  });
}

export function useAttendance(sessionId?: number) {
  const running = useIsRunning();
  return useQuery({
    queryKey: ["attendance", sessionId ?? "latest"],
    queryFn: () => api.attendance(sessionId),
    refetchInterval: pollMs(running),
    retry: 1,
  });
}

/** Per-student attention timelines (for the heatmap + student cards). */
export function useStudentTimelines(
  students: StudentStats[],
  sessionId?: number,
) {
  return useQueries({
    queries: students.map((s) => ({
      queryKey: ["student-timeline", sessionId ?? "latest", s.student_id],
      queryFn: () => api.studentTimeline(s.student_id, sessionId),
      staleTime: 10000,
    })),
    combine: (results) => ({
      byStudentId: new Map(
        results.map((r, i) => [students[i]?.student_id, r.data ?? []]),
      ),
      loading: results.some((r) => r.isLoading),
    }),
  });
}
