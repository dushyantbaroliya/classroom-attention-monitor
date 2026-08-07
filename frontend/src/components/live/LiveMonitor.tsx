import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Eye,
  Gauge,
  Hand,
  Minus,
  MonitorOff,
  Smartphone,
} from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import type { LiveFrame, LiveStudent } from "../../types";
import { attentionBand, BAND_TEXT, cn } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";
import { EmptyState } from "../ui/states";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";

const HEAD_ICON: Record<string, typeof ArrowUp> = {
  forward: ArrowUp,
  left: ArrowLeft,
  right: ArrowRight,
  up: ArrowUp,
  down: ArrowDown,
  unknown: Minus,
};

const BAND_BORDER: Record<string, string> = {
  excellent: "border-status-excellent",
  good: "border-status-good",
  warning: "border-status-warning",
  critical: "border-status-critical",
};

interface LiveMonitorProps {
  frame: LiveFrame | null;
  connected: boolean;
  running: boolean;
}

/** Large live video panel with HTML overlays positioned over each student. */
export function LiveMonitor({ frame, connected, running }: LiveMonitorProps) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [scale, setScale] = useState<{
    x: number;
    y: number;
    offX: number;
    offY: number;
  } | null>(null);

  // Map bbox pixel coords (source frame) -> rendered <img> coords.
  const recompute = () => {
    const img = imgRef.current;
    if (!img || !img.naturalWidth) return;
    const rect = img.getBoundingClientRect();
    const srcRatio = img.naturalWidth / img.naturalHeight;
    const dstRatio = rect.width / rect.height;
    let drawW = rect.width;
    let drawH = rect.height;
    if (srcRatio > dstRatio) drawH = rect.width / srcRatio;
    else drawW = rect.height * srcRatio;
    setScale({
      x: drawW / img.naturalWidth,
      y: drawH / img.naturalHeight,
      offX: (rect.width - drawW) / 2,
      offY: (rect.height - drawH) / 2,
    });
  };

  useLayoutEffect(() => {
    recompute();
    window.addEventListener("resize", recompute);
    return () => window.removeEventListener("resize", recompute);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frame?.jpeg_b64]);

  const students = frame?.students ?? [];
  const fps =
    frame?.processing_ms && frame.processing_ms > 0
      ? Math.min(99, 1000 / frame.processing_ms)
      : null;

  return (
    <Card className="overflow-hidden">
      {/* header strip */}
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              running && connected
                ? "animate-pulse bg-status-excellent"
                : "bg-muted-foreground/40",
            )}
            aria-hidden
          />
          <span className="text-sm font-medium">
            {running ? (connected ? "Live" : "Connecting…") : "Idle"}
          </span>
          {frame?.session_id != null && (
            <Badge variant="outline">Session #{frame.session_id}</Badge>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {fps != null && (
            <Badge variant="primary">
              <Gauge className="h-3 w-3" aria-hidden />
              {fps.toFixed(0)} FPS
            </Badge>
          )}
          {frame?.class_average != null && (
            <Badge
              variant={attentionBand(frame.class_average)}
              aria-label={`Class average ${Math.round(frame.class_average)}`}
            >
              class {Math.round(frame.class_average)}
            </Badge>
          )}
        </div>
      </div>

      {/* video area */}
      <div className="relative aspect-video w-full bg-zinc-950">
        {frame?.jpeg_b64 ? (
          <>
            <img
              ref={imgRef}
              src={`data:image/jpeg;base64,${frame.jpeg_b64}`}
              alt="Live annotated classroom feed"
              onLoad={recompute}
              className="h-full w-full object-contain"
            />
            {/* overlays */}
            {scale &&
              students.map((s) => (
                <StudentOverlay key={s.track_id} student={s} scale={scale} />
              ))}
          </>
        ) : (
          <div className="flex h-full items-center justify-center">
            <EmptyState
              icon={MonitorOff}
              title={running ? "Waiting for frames" : "No live session"}
              message={
                running
                  ? "The pipeline is warming up. The first annotated frame lands here."
                  : "Start a webcam stream or upload a video from the controls."
              }
              className="py-0"
            />
          </div>
        )}
      </div>

      {/* live chips */}
      <AnimatePresence>
        {students.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-wrap gap-2 border-t border-border px-4 py-3"
          >
            {students.map((s) => (
              <LiveChip key={s.track_id} student={s} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}

function StudentOverlay({
  student,
  scale,
}: {
  student: LiveStudent;
  scale: { x: number; y: number; offX: number; offY: number };
}) {
  const [x1, y1, x2] = student.bbox;
  const band = attentionBand(student.attention);
  const HeadIcon = HEAD_ICON[student.head_pose] ?? Minus;

  return (
    <motion.div
      layout
      layoutId={`overlay-${student.track_id}`}
      transition={{ type: "spring", stiffness: 260, damping: 28 }}
      className="pointer-events-none absolute"
      style={{
        left: scale.offX + x1 * scale.x,
        top: Math.max(2, scale.offY + y1 * scale.y - 26),
        width: Math.max(90, (x2 - x1) * scale.x),
      }}
    >
      <span
        className={cn(
          "inline-flex max-w-full items-center gap-1.5 rounded-md border bg-zinc-950/80 px-1.5 py-0.5 text-[10px] font-medium text-white backdrop-blur-sm",
          BAND_BORDER[band],
        )}
      >
        <span className="truncate">{student.label}</span>
        <span className={cn("tabular-nums", BAND_TEXT[band])}>
          {Math.round(student.attention)}
        </span>
        <HeadIcon className="h-3 w-3 opacity-80" aria-hidden />
        {student.phone_visible && (
          <Smartphone className="h-3 w-3 text-status-critical" aria-hidden />
        )}
        {student.hand_raised && (
          <Hand className="h-3 w-3 text-status-good" aria-hidden />
        )}
      </span>
    </motion.div>
  );
}

function LiveChip({ student }: { student: LiveStudent }) {
  const band = attentionBand(student.attention);
  const breakdown = Object.entries(student.score_components);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className="flex cursor-default items-center gap-2 rounded-lg border border-border bg-muted/40 px-2.5 py-1.5 text-xs transition-colors hover:bg-accent"
          tabIndex={0}
        >
          <span className="font-medium">{student.label}</span>
          <span className={cn("font-semibold tabular-nums", BAND_TEXT[band])}>
            {Math.round(student.attention)}
          </span>
          <span className="text-muted-foreground">
            {student.head_pose}/{student.gaze}
          </span>
          {student.hand_raised && (
            <Hand className="h-3 w-3 text-status-good" aria-hidden />
          )}
          {student.phone_visible && (
            <Smartphone className="h-3 w-3 text-status-critical" aria-hidden />
          )}
          {student.eyes_closed && (
            <Eye className="h-3 w-3 text-status-warning" aria-hidden />
          )}
        </span>
      </TooltipTrigger>
      <TooltipContent>
        <p className="mb-1 font-medium">Score breakdown</p>
        {breakdown.length === 0 ? (
          <p className="text-muted-foreground">No active components</p>
        ) : (
          <ul className="space-y-0.5">
            {breakdown.map(([k, v]) => (
              <li key={k} className="flex justify-between gap-4 tabular-nums">
                <span className="text-muted-foreground">{k.replaceAll("_", " ")}</span>
                <span className={v > 0 ? "text-status-excellent" : "text-status-critical"}>
                  {v > 0 ? "+" : ""}
                  {v}
                </span>
              </li>
            ))}
          </ul>
        )}
      </TooltipContent>
    </Tooltip>
  );
}
