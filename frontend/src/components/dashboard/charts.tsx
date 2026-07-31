/** Recharts-based chart set. All colors come from the design tokens. */
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { attentionBand, chartColor, fmtClock } from "../../lib/utils";
import type { StudentStats, TimelinePoint } from "../../types";
import { chartTooltipStyle } from "./ChartCard";

const AXIS = {
  stroke: chartColor.muted,
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const;

/* ------------------------------------------------ attention over time */
export function AttentionAreaChart({ timeline }: { timeline: TimelinePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={timeline} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
        <defs>
          <linearGradient id="attn-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={chartColor.primary} stopOpacity={0.28} />
            <stop offset="100%" stopColor={chartColor.primary} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={chartColor.grid} strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="timestamp" tickFormatter={fmtClock} {...AXIS} minTickGap={40} />
        <YAxis domain={[0, 100]} width={38} {...AXIS} />
        <RTooltip
          {...chartTooltipStyle()}
          labelFormatter={(v) => `t = ${fmtClock(Number(v))}`}
          formatter={(value: number | string, name: string) => [
            typeof value === "number" ? value.toFixed(0) : value,
            name === "avg_attention" ? "Class attention" : "Students",
          ]}
        />
        <Area
          dataKey="avg_attention"
          type="monotone"
          stroke={chartColor.primary}
          strokeWidth={2}
          fill="url(#attn-fill)"
          animationDuration={800}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* --------------------------------------------- attention distribution */
export function DistributionChart({ students }: { students: StudentStats[] }) {
  const buckets = [
    { range: "0–25", min: 0, max: 25, color: chartColor.critical },
    { range: "25–50", min: 25, max: 50, color: chartColor.warning },
    { range: "50–75", min: 50, max: 75, color: chartColor.good },
    { range: "75–100", min: 75, max: 101, color: chartColor.excellent },
  ].map((b) => ({
    ...b,
    count: students.filter(
      (s) => s.avg_attention >= b.min && s.avg_attention < b.max,
    ).length,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={buckets} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
        <CartesianGrid stroke={chartColor.grid} strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="range" {...AXIS} />
        <YAxis allowDecimals={false} width={32} {...AXIS} />
        <RTooltip
          {...chartTooltipStyle()}
          cursor={{ fill: "hsl(var(--muted))", opacity: 0.4 }}
          formatter={(v: number | string) => [`${v} students`, "Count"]}
        />
        <Bar dataKey="count" radius={[6, 6, 0, 0]} animationDuration={700}>
          {buckets.map((b) => (
            <Cell key={b.range} fill={b.color} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ------------------------------------------------------- phone donut */
export function PhoneDonutChart({ students }: { students: StudentStats[] }) {
  const withPhone = students.filter((s) => s.phone_usage_ratio > 0.02).length;
  const clean = students.length - withPhone;
  const data = [
    { name: "Phone seen", value: withPhone, color: chartColor.critical },
    { name: "No phone", value: clean, color: chartColor.excellent },
  ];

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <RTooltip
          {...chartTooltipStyle()}
          formatter={(v: number | string, name: string) => [`${v} students`, name]}
        />
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius="62%"
          outerRadius="85%"
          paddingAngle={4}
          cornerRadius={6}
          animationDuration={800}
          stroke="none"
        >
          {data.map((d) => (
            <Cell key={d.name} fill={d.color} fillOpacity={0.85} />
          ))}
        </Pie>
        <text
          x="50%"
          y="47%"
          textAnchor="middle"
          className="fill-current text-2xl font-semibold"
          fill="hsl(var(--foreground))"
        >
          {students.length ? Math.round((clean / students.length) * 100) : 0}%
        </text>
        <text
          x="50%"
          y="58%"
          textAnchor="middle"
          fontSize={11}
          fill="hsl(var(--muted-foreground))"
        >
          phone-free
        </text>
      </PieChart>
    </ResponsiveContainer>
  );
}

/* ------------------------------------------------------- blink trends */
export function BlinkTrendChart({ students }: { students: StudentStats[] }) {
  const data = students.map((s) => ({
    label: s.label.replace("Student ", "S"),
    rate: s.avg_blink_rate,
    closed: s.eyes_closed_ratio * 100,
  }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
        <CartesianGrid stroke={chartColor.grid} strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="label" {...AXIS} />
        <YAxis width={32} {...AXIS} />
        <RTooltip
          {...chartTooltipStyle()}
          formatter={(v: number | string, name: string) => [
            typeof v === "number" ? v.toFixed(1) : v,
            name === "rate" ? "Blinks/min" : "Eyes closed %",
          ]}
        />
        <Line
          dataKey="rate"
          type="monotone"
          stroke={chartColor.good}
          strokeWidth={2}
          dot={{ r: 3, fill: chartColor.good, strokeWidth: 0 }}
          animationDuration={700}
        />
        <Line
          dataKey="closed"
          type="monotone"
          stroke={chartColor.warning}
          strokeWidth={2}
          strokeDasharray="5 4"
          dot={false}
          animationDuration={700}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

/* --------------------------------------------------- student ranking */
export function RankingChart({ students }: { students: StudentStats[] }) {
  const sorted = [...students].sort((a, b) => b.avg_attention - a.avg_attention);
  const bandColor = {
    excellent: chartColor.excellent,
    good: chartColor.good,
    warning: chartColor.warning,
    critical: chartColor.critical,
  } as const;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart
        data={sorted}
        layout="vertical"
        margin={{ top: 0, right: 28, left: -6, bottom: 0 }}
      >
        <CartesianGrid stroke={chartColor.grid} strokeDasharray="3 6" horizontal={false} />
        <XAxis type="number" domain={[0, 100]} {...AXIS} />
        <YAxis
          type="category"
          dataKey="label"
          width={78}
          {...AXIS}
          tickFormatter={(v: string) => v}
        />
        <RTooltip
          {...chartTooltipStyle()}
          cursor={{ fill: "hsl(var(--muted))", opacity: 0.4 }}
          formatter={(v: number | string) => [
            typeof v === "number" ? v.toFixed(1) : v,
            "Avg attention",
          ]}
        />
        <Bar
          dataKey="avg_attention"
          radius={[0, 6, 6, 0]}
          barSize={14}
          animationDuration={800}
          label={{
            position: "right",
            fontSize: 11,
            fill: "hsl(var(--muted-foreground))",
            formatter: (v: unknown) => Math.round(Number(v)),
          }}
        >
          {sorted.map((s) => (
            <Cell
              key={s.student_id}
              fill={bandColor[attentionBand(s.avg_attention)]}
              fillOpacity={0.85}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
