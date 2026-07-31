import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Seconds -> "m:ss" (or "h:mm:ss" for long sessions). */
export function fmtClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = (s % 60).toString().padStart(2, "0");
  return h > 0 ? `${h}:${m.toString().padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

export function pct(ratio: number, digits = 0): string {
  return `${(ratio * 100).toFixed(digits)}%`;
}

export type AttentionBand = "excellent" | "good" | "warning" | "critical";

export function attentionBand(score: number): AttentionBand {
  if (score >= 75) return "excellent";
  if (score >= 55) return "good";
  if (score >= 35) return "warning";
  return "critical";
}

export const BAND_TEXT: Record<AttentionBand, string> = {
  excellent: "text-status-excellent",
  good: "text-status-good",
  warning: "text-status-warning",
  critical: "text-status-critical",
};

export const BAND_BG: Record<AttentionBand, string> = {
  excellent: "bg-status-excellent",
  good: "bg-status-good",
  warning: "bg-status-warning",
  critical: "bg-status-critical",
};

export const BAND_LABEL: Record<AttentionBand, string> = {
  excellent: "Excellent",
  good: "Good",
  warning: "Warning",
  critical: "Critical",
};

/** CSS color strings for chart libraries (resolved from the design tokens). */
export const chartColor = {
  primary: "hsl(var(--primary))",
  excellent: "hsl(var(--status-excellent))",
  good: "hsl(var(--status-good))",
  warning: "hsl(var(--status-warning))",
  critical: "hsl(var(--status-critical))",
  grid: "hsl(var(--chart-grid))",
  muted: "hsl(var(--muted-foreground))",
};
