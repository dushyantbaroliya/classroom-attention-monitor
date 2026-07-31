// API payload types mirroring backend/app/schemas.py

export interface SessionInfo {
  session_id: number;
  name: string;
  source: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  fps: number;
  frames_processed: number;
}

export interface StudentStats {
  student_id: number;
  track_id: number;
  label: string;
  first_seen: number;
  last_seen: number;
  frames_seen: number;
  avg_attention: number;
  min_attention: number;
  max_attention: number;
  blink_total: number;
  avg_blink_rate: number;
  phone_usage_ratio: number;
  hand_raised_ratio: number;
  eyes_closed_ratio: number;
  forward_ratio: number;
}

export interface TimelinePoint {
  timestamp: number;
  avg_attention: number;
  students_present: number;
  phones_visible: number;
  hands_raised: number;
  alert: boolean;
}

export interface StudentTimelinePoint {
  timestamp: number;
  attention: number;
  head_pose: string;
  gaze: string;
}

export interface AnalyticsResponse {
  session: SessionInfo | null;
  timeline: TimelinePoint[];
  students: StudentStats[];
}

export interface AttendanceEntry {
  label: string;
  present: boolean;
  first_seen: number;
  last_seen: number;
  presence_ratio: number | null;
}

export interface StatisticsResponse {
  session: SessionInfo | null;
  class_average_attention: number;
  students_detected: number;
  total_samples: number;
  low_attention_alerts: number;
  most_engaged: string | null;
  least_engaged: string | null;
  total_hand_raises: number;
  phone_incidents: number;
}

export interface LiveStudent {
  track_id: number;
  label: string;
  bbox: number[];
  attention: number;
  head_pose: string;
  gaze: string;
  eyes_closed: boolean;
  phone_visible: boolean;
  hand_raised: boolean;
  score_components: Record<string, number>;
}

export interface LiveFrame {
  type: "frame" | "idle";
  session_id?: number;
  frame_index?: number;
  timestamp?: number;
  class_average?: number;
  processing_ms?: number;
  students?: LiveStudent[];
  jpeg_b64?: string | null;
}

export interface HealthResponse {
  status: string;
  version: string;
  pipeline_available: boolean;
  active_session_id: number | null;
}
