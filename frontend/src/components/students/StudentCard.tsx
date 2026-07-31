import { motion } from "framer-motion";
import { Eye, Hand, Smartphone, User } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import {
  attentionBand,
  BAND_LABEL,
  cn,
  fmtClock,
  pct,
} from "../../lib/utils";
import type { StudentStats, StudentTimelinePoint } from "../../types";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";
import { ProgressRing } from "../ui/progress-ring";

const HEAD_ARROW: Record<string, string> = {
  forward: "↑",
  left: "←",
  right: "→",
  up: "↥",
  down: "↓",
  unknown: "·",
};

interface StudentCardProps {
  student: StudentStats;
  timeline?: StudentTimelinePoint[];
  index?: number;
}

export function StudentCard({ student, timeline, index = 0 }: StudentCardProps) {
  const band = attentionBand(student.avg_attention);
  const dominantPose = student.forward_ratio >= 0.5 ? "forward" : "away";
  const sparkData = (timeline ?? []).map((p) => ({ v: p.attention }));

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.35, ease: "easeOut" }}
      whileHover={{ y: -3 }}
    >
      <Card className="group relative overflow-hidden p-4 hover:shadow-card-hover">
        {/* status accent */}
        <span
          className={cn("absolute inset-x-0 top-0 h-0.5 opacity-70", {
            "bg-status-excellent": band === "excellent",
            "bg-status-good": band === "good",
            "bg-status-warning": band === "warning",
            "bg-status-critical": band === "critical",
          })}
          aria-hidden
        />

        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted transition-transform duration-300 group-hover:scale-105">
              <User className="h-5 w-5 text-muted-foreground" aria-hidden />
            </div>
            <div>
              <p className="text-sm font-semibold">{student.label}</p>
              <p className="text-[11px] text-muted-foreground">
                Track #{student.track_id} · last seen {fmtClock(student.last_seen)}
              </p>
            </div>
          </div>
          <ProgressRing value={student.avg_attention} size={52} strokeWidth={4} />
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <Badge variant={band}>{BAND_LABEL[band]}</Badge>
          <Badge variant="outline">
            <span aria-hidden>{HEAD_ARROW[dominantPose === "forward" ? "forward" : "down"]}</span>
            {pct(student.forward_ratio)} forward
          </Badge>
          {student.phone_usage_ratio > 0.02 && (
            <Badge variant="critical">
              <Smartphone className="h-3 w-3" aria-hidden />
              {pct(student.phone_usage_ratio)}
            </Badge>
          )}
          {student.hand_raised_ratio > 0 && (
            <Badge variant="good">
              <Hand className="h-3 w-3" aria-hidden /> raised
            </Badge>
          )}
          <Badge variant="outline">
            <Eye className="h-3 w-3" aria-hidden />
            {student.blink_total} blinks
          </Badge>
        </div>

        {sparkData.length > 1 && (
          <div className="mt-3 h-10" aria-hidden>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkData} margin={{ top: 2, bottom: 0, left: 0, right: 0 }}>
                <defs>
                  <linearGradient
                    id={`stud-spark-${student.student_id}`}
                    x1="0" y1="0" x2="0" y2="1"
                  >
                    <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  dataKey="v"
                  type="monotone"
                  stroke="hsl(var(--primary))"
                  strokeWidth={1.5}
                  fill={`url(#stud-spark-${student.student_id})`}
                  isAnimationActive
                  animationDuration={600}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </motion.div>
  );
}
