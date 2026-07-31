import { motion } from "framer-motion";
import { attentionBand, BAND_TEXT, cn } from "../../lib/utils";

interface ProgressRingProps {
  value: number; // 0..100
  size?: number;
  strokeWidth?: number;
  className?: string;
  showLabel?: boolean;
}

/** Animated circular attention indicator, colored by status band. */
export function ProgressRing({
  value,
  size = 64,
  strokeWidth = 5,
  className,
  showLabel = true,
}: ProgressRingProps) {
  const clamped = Math.min(100, Math.max(0, value));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const band = attentionBand(clamped);

  return (
    <div
      className={cn("relative inline-flex", className)}
      role="meter"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Attention ${Math.round(clamped)} out of 100`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-muted"
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{
            strokeDashoffset: circumference * (1 - clamped / 100),
          }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className={cn("stroke-current", BAND_TEXT[band])}
        />
      </svg>
      {showLabel && (
        <span
          className={cn(
            "absolute inset-0 flex items-center justify-center text-sm font-semibold tabular-nums",
            BAND_TEXT[band],
          )}
        >
          {Math.round(clamped)}
        </span>
      )}
    </div>
  );
}
