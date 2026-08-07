/**
 * Session event derivation.
 *
 * The backend stores a class snapshot every few seconds; this module turns
 * those snapshots into a human-readable activity timeline (phone appeared,
 * hand raised, attention dropped/recovered, session start/end) without any
 * backend changes.
 */
import type { SessionInfo, TimelinePoint } from "../types";

export type SessionEventKind =
  | "session_started"
  | "session_ended"
  | "phone_detected"
  | "phone_cleared"
  | "hand_raised"
  | "attention_dropped"
  | "attention_recovered"
  | "student_joined";

export interface SessionEvent {
  kind: SessionEventKind;
  timestamp: number;
  title: string;
  detail: string;
}

const DROP_THRESHOLD = 45;
const RECOVER_THRESHOLD = 60;

export function deriveEvents(
  timeline: TimelinePoint[],
  session: SessionInfo | null | undefined,
): SessionEvent[] {
  const events: SessionEvent[] = [];
  if (timeline.length === 0) return events;

  events.push({
    kind: "session_started",
    timestamp: timeline[0].timestamp,
    title: "Session started",
    detail: session
      ? `${session.name} · source ${session.source}`
      : "Monitoring began",
  });

  let low = false;
  for (let i = 1; i < timeline.length; i++) {
    const prev = timeline[i - 1];
    const cur = timeline[i];

    if (cur.students_present > prev.students_present) {
      events.push({
        kind: "student_joined",
        timestamp: cur.timestamp,
        title: `Student joined`,
        detail: `${cur.students_present} students now present`,
      });
    }
    if (cur.phones_visible > prev.phones_visible) {
      events.push({
        kind: "phone_detected",
        timestamp: cur.timestamp,
        title: "Phone detected",
        detail: `${cur.phones_visible} phone${cur.phones_visible > 1 ? "s" : ""} visible in class`,
      });
    } else if (cur.phones_visible === 0 && prev.phones_visible > 0) {
      events.push({
        kind: "phone_cleared",
        timestamp: cur.timestamp,
        title: "Phones away",
        detail: "No phones visible anymore",
      });
    }
    if (cur.hands_raised > prev.hands_raised) {
      events.push({
        kind: "hand_raised",
        timestamp: cur.timestamp,
        title: "Hand raised",
        detail: `${cur.hands_raised} hand${cur.hands_raised > 1 ? "s" : ""} up`,
      });
    }
    if (!low && cur.avg_attention < DROP_THRESHOLD) {
      low = true;
      events.push({
        kind: "attention_dropped",
        timestamp: cur.timestamp,
        title: "Attention dropped",
        detail: `Class average fell to ${Math.round(cur.avg_attention)}`,
      });
    } else if (low && cur.avg_attention >= RECOVER_THRESHOLD) {
      low = false;
      events.push({
        kind: "attention_recovered",
        timestamp: cur.timestamp,
        title: "Attention recovered",
        detail: `Class average back to ${Math.round(cur.avg_attention)}`,
      });
    }
  }

  if (session?.ended_at) {
    events.push({
      kind: "session_ended",
      timestamp: timeline[timeline.length - 1].timestamp,
      title: "Session ended",
      detail: `${session.frames_processed} frames analyzed at ${session.fps.toFixed(1)} FPS`,
    });
  }

  return events.reverse(); // newest first
}

/** Insight sentences for the Analytics/Reports pages. */
export interface Insight {
  title: string;
  detail: string;
  tone: "positive" | "neutral" | "warning";
}

export function deriveInsights(
  timeline: TimelinePoint[],
  studentCount: number,
): Insight[] {
  if (timeline.length < 3) return [];
  const insights: Insight[] = [];

  const peak = timeline.reduce((a, b) =>
    b.avg_attention > a.avg_attention ? b : a,
  );
  const trough = timeline.reduce((a, b) =>
    b.avg_attention < a.avg_attention ? b : a,
  );
  const third = Math.floor(timeline.length / 3);
  const avgOf = (pts: TimelinePoint[]) =>
    pts.reduce((s, p) => s + p.avg_attention, 0) / Math.max(1, pts.length);
  const early = avgOf(timeline.slice(0, third));
  const late = avgOf(timeline.slice(-third));

  insights.push({
    title: "Peak engagement",
    detail: `Highest class attention (${Math.round(peak.avg_attention)}) at ${fmt(peak.timestamp)}.`,
    tone: "positive",
  });
  insights.push({
    title: "Lowest engagement period",
    detail: `Attention bottomed out at ${Math.round(trough.avg_attention)} around ${fmt(trough.timestamp)}.`,
    tone: "warning",
  });
  if (late < early - 8) {
    insights.push({
      title: "Fatigue trend",
      detail: `Average attention fell ${Math.round(early - late)} points from the first to the last third of the session, so a mid-session break may help.`,
      tone: "warning",
    });
  } else if (late > early + 8) {
    insights.push({
      title: "Warm-up trend",
      detail: `The class became ${Math.round(late - early)} points more attentive as the session progressed.`,
      tone: "positive",
    });
  }
  const alerts = timeline.filter((p) => p.alert).length;
  if (alerts > 0) {
    insights.push({
      title: "Low-attention alerts",
      detail: `${alerts} snapshot${alerts > 1 ? "s" : ""} fell below the alert threshold across ${studentCount} students.`,
      tone: "warning",
    });
  } else {
    insights.push({
      title: "Steady session",
      detail: "No low-attention alerts were triggered during this session.",
      tone: "positive",
    });
  }
  return insights;
}

function fmt(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
