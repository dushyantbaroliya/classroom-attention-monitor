import { motion } from "framer-motion";
import { useMemo } from "react";
import { fmtClock } from "../../lib/utils";
import type { StudentStats, StudentTimelinePoint } from "../../types";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "../ui/tooltip";

const BUCKETS = 24;

interface HeatmapProps {
  students: StudentStats[];
  timelines: Map<number, StudentTimelinePoint[]>;
}

/** Engagement heatmap: students × time buckets, colored by avg attention. */
export function EngagementHeatmap({ students, timelines }: HeatmapProps) {
  const { rows, bucketSeconds } = useMemo(() => {
    let maxT = 0;
    for (const pts of timelines.values()) {
      const last = pts[pts.length - 1];
      if (last) maxT = Math.max(maxT, last.timestamp);
    }
    const bucketSec = Math.max(1, maxT / BUCKETS);

    const rows = students.map((s) => {
      const pts = timelines.get(s.student_id) ?? [];
      const sums = new Array(BUCKETS).fill(0);
      const counts = new Array(BUCKETS).fill(0);
      for (const p of pts) {
        const b = Math.min(BUCKETS - 1, Math.floor(p.timestamp / bucketSec));
        sums[b] += p.attention;
        counts[b] += 1;
      }
      return {
        student: s,
        cells: sums.map((sum, i) =>
          counts[i] > 0 ? sum / counts[i] : null,
        ) as (number | null)[],
      };
    });
    return { rows, bucketSeconds: bucketSec };
  }, [students, timelines]);

  if (rows.length === 0) return null;

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[560px]">
        {rows.map(({ student, cells }, rowIdx) => (
          <div key={student.student_id} className="mb-1 flex items-center gap-2">
            <span className="w-20 shrink-0 truncate text-right text-[11px] text-muted-foreground">
              {student.label}
            </span>
            <div className="flex flex-1 gap-[3px]">
              {cells.map((v, i) => (
                <Tooltip key={i}>
                  <TooltipTrigger asChild>
                    <motion.span
                      initial={{ opacity: 0, scale: 0.6 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: rowIdx * 0.03 + i * 0.008 }}
                      tabIndex={-1}
                      className="h-5 flex-1 rounded-[4px]"
                      style={{
                        backgroundColor:
                          v == null
                            ? "hsl(var(--muted))"
                            : `hsl(var(--primary) / ${0.08 + (v / 100) * 0.85})`,
                      }}
                      aria-label={
                        v == null
                          ? `${student.label}: absent`
                          : `${student.label} at ${fmtClock(i * bucketSeconds)}: ${Math.round(v)}`
                      }
                    />
                  </TooltipTrigger>
                  <TooltipContent>
                    {student.label} · {fmtClock(i * bucketSeconds)} ·{" "}
                    {v == null ? "not present" : `attention ${Math.round(v)}`}
                  </TooltipContent>
                </Tooltip>
              ))}
            </div>
          </div>
        ))}
        <div className="ml-[88px] mt-1.5 flex justify-between text-[10px] tabular-nums text-muted-foreground">
          <span>0:00</span>
          <span>{fmtClock((BUCKETS / 2) * bucketSeconds)}</span>
          <span>{fmtClock(BUCKETS * bucketSeconds)}</span>
        </div>
      </div>
    </div>
  );
}
