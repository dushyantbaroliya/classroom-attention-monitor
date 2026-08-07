import { Download, FileText, Printer } from "lucide-react";
import { useMemo } from "react";
import { api } from "../api";
import { ChartCard } from "../components/dashboard/ChartCard";
import {
  AttentionAreaChart,
  RankingChart,
} from "../components/dashboard/charts";
import { PageHeader } from "../components/layout/AppShell";
import { SessionPicker } from "../components/layout/SessionPicker";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { EmptyState } from "../components/ui/states";
import { useSelectedSession } from "../hooks/useSelectedSession";
import {
  useAnalytics,
  useAttendance,
  useStatistics,
} from "../hooks/useSessionData";
import { deriveInsights } from "../lib/events";
import { attentionBand, BAND_LABEL, fmtClock, pct } from "../lib/utils";

export function ReportsPage() {
  const { sessionId } = useSelectedSession();
  const analytics = useAnalytics(sessionId);
  const statistics = useStatistics(sessionId);
  const attendance = useAttendance(sessionId);

  const session = analytics.data?.session;
  const timeline = analytics.data?.timeline ?? [];
  const students = analytics.data?.students ?? [];
  const insights = useMemo(
    () => deriveInsights(timeline, students.length),
    [timeline, students.length],
  );

  if (!analytics.isLoading && !session) {
    return (
      <>
        <PageHeader title="Reports" />
        <Card>
          <EmptyState
            icon={FileText}
            title="No report available"
            message="Reports are generated from recorded sessions. Run a monitoring session first, then return here for a printable summary."
          />
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Reports"
        description="Printable session summary for staff and records"
        actions={
          <div className="flex items-center gap-2">
            <SessionPicker />
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(api.csvUrl(sessionId), "_blank")}
            >
              <Download aria-hidden /> Export CSV
            </Button>
            <Button size="sm" onClick={() => window.print()}>
              <Printer aria-hidden /> Print / PDF
            </Button>
          </div>
        }
      />

      <div className="flex flex-col gap-4">
        {/* Report header card */}
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="text-lg">
                  {session?.name ?? "Session report"}
                </CardTitle>
                <CardDescription>
                  Source {session?.source} · {session?.frames_processed ?? 0}{" "}
                  frames processed at {session?.fps.toFixed(1) ?? "0"} FPS
                </CardDescription>
              </div>
              <Badge variant={session?.status === "completed" ? "excellent" : "default"}>
                {session?.status ?? "-"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Stat
                label="Class average"
                value={statistics.data?.class_average_attention.toFixed(1) ?? "-"}
              />
              <Stat
                label="Students"
                value={String(statistics.data?.students_detected ?? 0)}
              />
              <Stat
                label="Duration"
                value={
                  timeline.length
                    ? fmtClock(timeline[timeline.length - 1].timestamp)
                    : "-"
                }
              />
              <Stat
                label="Alerts"
                value={String(statistics.data?.low_attention_alerts ?? 0)}
              />
            </dl>
          </CardContent>
        </Card>

        {/* Summary narrative */}
        <Card>
          <CardHeader>
            <CardTitle>Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {insights.map((ins) => (
              <p key={ins.title} className="text-sm leading-relaxed">
                <span className="font-medium">{ins.title}.</span>{" "}
                <span className="text-muted-foreground">{ins.detail}</span>
              </p>
            ))}
            <p className="pt-2 text-xs leading-relaxed text-muted-foreground">
              This report reflects observable behavioral proxies (head
              orientation, eyelid aperture, gaze direction, phone visibility,
              hand raises), not measured cognitive attention. Use it as
              teaching feedback, never for grading or discipline.
            </p>
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard
            title="Attention over time"
            loading={analytics.isLoading}
            empty={timeline.length === 0}
          >
            <AttentionAreaChart timeline={timeline} />
          </ChartCard>
          <ChartCard
            title="Student ranking"
            height={Math.max(220, students.length * 28)}
            loading={analytics.isLoading}
            empty={students.length === 0}
          >
            <RankingChart students={students} />
          </ChartCard>
        </div>

        {/* Printable roster */}
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Attendance & engagement roster</CardTitle>
            <CardDescription>
              Anonymous tracker identities, no face recognition performed
            </CardDescription>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-y border-border bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-5 py-2.5">Student</th>
                  <th className="px-5 py-2.5">Present</th>
                  <th className="px-5 py-2.5">Window</th>
                  <th className="px-5 py-2.5">Avg attention</th>
                  <th className="px-5 py-2.5">Band</th>
                  <th className="px-5 py-2.5">Phone</th>
                </tr>
              </thead>
              <tbody>
                {students.map((s) => {
                  const att = attendance.data?.attendance.find(
                    (a) => a.label === s.label,
                  );
                  const band = attentionBand(s.avg_attention);
                  return (
                    <tr
                      key={s.student_id}
                      className="border-b border-border/60 last:border-0"
                    >
                      <td className="px-5 py-2.5 font-medium">{s.label}</td>
                      <td className="px-5 py-2.5 text-muted-foreground">
                        {att?.presence_ratio != null
                          ? pct(att.presence_ratio)
                          : "live"}
                      </td>
                      <td className="px-5 py-2.5 tabular-nums text-muted-foreground">
                        {fmtClock(s.first_seen)} – {fmtClock(s.last_seen)}
                      </td>
                      <td className="px-5 py-2.5 tabular-nums">
                        {s.avg_attention.toFixed(1)}
                      </td>
                      <td className="px-5 py-2.5">
                        <Badge variant={band}>{BAND_LABEL[band]}</Badge>
                      </td>
                      <td className="px-5 py-2.5 text-muted-foreground">
                        {pct(s.phone_usage_ratio)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 text-xl font-semibold tabular-nums tracking-tight">
        {value}
      </dd>
    </div>
  );
}
