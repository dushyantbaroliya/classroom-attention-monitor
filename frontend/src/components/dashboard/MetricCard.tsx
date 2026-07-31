import { motion } from "framer-motion";
import { TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { cn } from "../../lib/utils";
import { Card } from "../ui/card";
import { Skeleton } from "../ui/skeleton";

/** Animated count-up for metric values. */
function CountUp({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const [display, setDisplay] = useState(value);
  const raf = useRef<number>();
  const from = useRef(value);

  useEffect(() => {
    const start = performance.now();
    const initial = from.current;
    const animate = (t: number) => {
      const p = Math.min(1, (t - start) / 600);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(initial + (value - initial) * eased);
      if (p < 1) raf.current = requestAnimationFrame(animate);
      else from.current = value;
    };
    raf.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf.current!);
  }, [value]);

  return <>{display.toFixed(decimals)}</>;
}

export interface MetricCardProps {
  label: string;
  value: number | null | undefined;
  decimals?: number;
  suffix?: string;
  icon: LucideIcon;
  trend?: number | null; // signed delta vs earlier period
  trendSuffix?: string;
  spark?: number[]; // tiny sparkline series
  tone?: "primary" | "excellent" | "good" | "warning" | "critical";
  loading?: boolean;
  index?: number; // stagger order
}

const TONE_TEXT: Record<NonNullable<MetricCardProps["tone"]>, string> = {
  primary: "text-primary",
  excellent: "text-status-excellent",
  good: "text-status-good",
  warning: "text-status-warning",
  critical: "text-status-critical",
};

export function MetricCard({
  label,
  value,
  decimals = 0,
  suffix,
  icon: Icon,
  trend,
  trendSuffix = "",
  spark,
  tone = "primary",
  loading,
  index = 0,
}: MetricCardProps) {
  if (loading || value == null) {
    return (
      <Card className="p-5">
        <Skeleton className="h-3.5 w-20" />
        <Skeleton className="mt-3 h-8 w-16" />
        <Skeleton className="mt-3 h-8 w-full" />
      </Card>
    );
  }

  const sparkData = (spark ?? []).map((v, i) => ({ i, v }));
  const trendUp = (trend ?? 0) >= 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.35, ease: "easeOut" }}
      whileHover={{ y: -2 }}
    >
      <Card className="group relative overflow-hidden p-5 hover:shadow-card-hover">
        <div className="flex items-start justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {label}
          </span>
          <span
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-lg bg-muted transition-transform duration-300 group-hover:scale-110",
              TONE_TEXT[tone],
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
          </span>
        </div>

        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-3xl font-semibold tabular-nums tracking-tight">
            <CountUp value={value} decimals={decimals} />
            {suffix && (
              <span className="ml-0.5 text-base font-normal text-muted-foreground">
                {suffix}
              </span>
            )}
          </span>
          {trend != null && Math.abs(trend) > 0.05 && (
            <span
              className={cn(
                "flex items-center gap-0.5 text-xs font-medium tabular-nums",
                trendUp ? "text-status-excellent" : "text-status-critical",
              )}
            >
              {trendUp ? (
                <TrendingUp className="h-3 w-3" aria-hidden />
              ) : (
                <TrendingDown className="h-3 w-3" aria-hidden />
              )}
              {trendUp ? "+" : ""}
              {trend.toFixed(1)}
              {trendSuffix}
            </span>
          )}
        </div>

        {sparkData.length > 1 && (
          <div className="mt-3 h-9" aria-hidden>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkData} margin={{ top: 2, bottom: 0, left: 0, right: 0 }}>
                <defs>
                  <linearGradient id={`spark-${label}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="currentColor" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="currentColor" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  dataKey="v"
                  type="monotone"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  fill={`url(#spark-${label})`}
                  className={TONE_TEXT[tone]}
                  isAnimationActive
                  animationDuration={700}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </motion.div>
  );
}
