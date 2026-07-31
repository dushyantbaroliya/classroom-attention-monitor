import { motion } from "framer-motion";
import {
  Activity,
  Flag,
  FlagOff,
  Hand,
  Smartphone,
  SmartphoneNfc,
  TrendingDown,
  TrendingUp,
  UserPlus,
  type LucideIcon,
} from "lucide-react";
import type { SessionEvent, SessionEventKind } from "../../lib/events";
import { cn, fmtClock } from "../../lib/utils";
import { EmptyState } from "../ui/states";

const EVENT_META: Record<
  SessionEventKind,
  { icon: LucideIcon; tone: string }
> = {
  session_started: { icon: Flag, tone: "text-primary bg-primary/10" },
  session_ended: { icon: FlagOff, tone: "text-muted-foreground bg-muted" },
  phone_detected: {
    icon: Smartphone,
    tone: "text-status-critical bg-status-critical/10",
  },
  phone_cleared: {
    icon: SmartphoneNfc,
    tone: "text-status-excellent bg-status-excellent/10",
  },
  hand_raised: { icon: Hand, tone: "text-status-good bg-status-good/10" },
  attention_dropped: {
    icon: TrendingDown,
    tone: "text-status-warning bg-status-warning/10",
  },
  attention_recovered: {
    icon: TrendingUp,
    tone: "text-status-excellent bg-status-excellent/10",
  },
  student_joined: { icon: UserPlus, tone: "text-status-good bg-status-good/10" },
};

export function ActivityTimeline({
  events,
  limit = 12,
}: {
  events: SessionEvent[];
  limit?: number;
}) {
  if (events.length === 0) {
    return (
      <EmptyState
        icon={Activity}
        title="No activity yet"
        message="Session events — phones, hand raises, attention swings — will appear here as they happen."
      />
    );
  }

  return (
    <ol className="relative space-y-1" aria-label="Session activity timeline">
      {events.slice(0, limit).map((e, i) => {
        const meta = EVENT_META[e.kind];
        const Icon = meta.icon;
        return (
          <motion.li
            key={`${e.kind}-${e.timestamp}-${i}`}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            className="group relative flex gap-3 rounded-xl px-2 py-2 transition-colors hover:bg-accent/60"
          >
            {/* connector line */}
            {i < Math.min(events.length, limit) - 1 && (
              <span
                className="absolute left-[22px] top-10 h-[calc(100%-24px)] w-px bg-border"
                aria-hidden
              />
            )}
            <span
              className={cn(
                "z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                meta.tone,
              )}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="truncate text-sm font-medium">{e.title}</p>
                <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
                  {fmtClock(e.timestamp)}
                </span>
              </div>
              <p className="truncate text-xs text-muted-foreground">{e.detail}</p>
            </div>
          </motion.li>
        );
      })}
    </ol>
  );
}
