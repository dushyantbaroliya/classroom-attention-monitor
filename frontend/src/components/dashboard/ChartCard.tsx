import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Skeleton } from "../ui/skeleton";

interface ChartCardProps {
  title: string;
  description?: string;
  height?: number;
  loading?: boolean;
  empty?: boolean;
  emptyHint?: string;
  actions?: ReactNode;
  children: ReactNode;
}

/** Shared wrapper: consistent chrome, skeleton loading and empty handling. */
export function ChartCard({
  title,
  description,
  height = 260,
  loading,
  empty,
  emptyHint = "No data for this session yet.",
  actions,
  children,
}: ChartCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <Card className="hover:shadow-card-hover">
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <div>
            <CardTitle>{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </div>
          {actions}
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton style={{ height }} className="w-full" />
          ) : empty ? (
            <div
              style={{ height }}
              className="flex items-center justify-center text-xs text-muted-foreground"
            >
              {emptyHint}
            </div>
          ) : (
            <div style={{ height }}>{children}</div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}

/** Shared Recharts tooltip look. */
export function chartTooltipStyle() {
  return {
    contentStyle: {
      background: "hsl(var(--card))",
      border: "1px solid hsl(var(--border))",
      borderRadius: 10,
      fontSize: 12,
      color: "hsl(var(--card-foreground))",
      boxShadow: "0 8px 24px -6px rgb(0 0 0 / 0.15)",
    },
    labelStyle: { color: "hsl(var(--muted-foreground))", fontSize: 11 },
    cursor: { stroke: "hsl(var(--border))", strokeWidth: 1 },
  } as const;
}
