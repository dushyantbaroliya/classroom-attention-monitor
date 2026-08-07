import { Download, Lightbulb, Sparkles, TrendingUp } from "lucide-react";
import { useMemo } from "react";
import { api } from "../api";
import { ChartCard } from "../components/dashboard/ChartCard";
import {
  AttentionAreaChart,
  BlinkTrendChart,
  DistributionChart,
  PhoneDonutChart,
  RankingChart,
} from "../components/dashboard/charts";
import { EngagementHeatmap } from "../components/dashboard/Heatmap";
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
import { ErrorState } from "../components/ui/states";
import { useSelectedSession } from "../hooks/useSelectedSession";
import {
  useAnalytics,
  useStatistics,
  useStudentTimelines,
} from "../hooks/useSessionData";
import { deriveInsights } from "../lib/events";
import { cn } from "../lib/utils";

export function AnalyticsPage() {
  const { sessionId } = useSelectedSession();
  const analytics = useAnalytics(sessionId);
  const statistics = useStatistics(sessionId);

  const timeline = analytics.data?.timeline ?? [];
  const students = analytics.data?.students ?? [];
  const { byStudentId } = useStudentTimelines(students, sessionId);
  const loading = analytics.isLoading;

  const insights = useMemo(
    () => deriveInsights(timeline, students.length),
    [timeline, students.length],
  );

  const ranked = useMemo(
    () => [...students].sort((a, b) => b.avg_attention - a.avg_attention),
    [students],
  );

  if (analytics.isError) {
    return (
      <>
        <PageHeader title="Analytics" />
        <ErrorState
          message="No analytics available yet. Record a session first."
          onRetry={() => analytics.refetch()}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Analytics"
        description="Session insights, rankings and engagement patterns"
        actions={
          <div className="flex items-center gap-2">
            <SessionPicker />
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(api.csvUrl(sessionId), "_blank")}
            >
              <Download aria-hidden /> CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => window.print()}>
              <Download aria-hidden /> PDF
            </Button>
          </div>
        }
      />

      <div className="flex flex-col gap-4">
        {/* Overview strip */}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <OverviewTile
            label="Class average"
            value={statistics.data?.class_average_attention.toFixed(1) ?? "-"}
            hint="across all samples"
          />
          <OverviewTile
            label="Most attentive"
            value={statistics.data?.most_engaged ?? "-"}
            hint={
              ranked[0] ? `${ranked[0].avg_attention.toFixed(0)} avg score` : ""
            }
            tone="excellent"
          />
          <OverviewTile
            label="Needs support"
            value={statistics.data?.least_engaged ?? "-"}
            hint={
              ranked.length
                ? `${ranked[ranked.length - 1].avg_attention.toFixed(0)} avg score`
                : ""
            }
            tone="warning"
          />
          <OverviewTile
            label="Alerts triggered"
            value={String(statistics.data?.low_attention_alerts ?? 0)}
            hint="snapshots below threshold"
            tone="critical"
          />
        </div>

        {/* Insights + recommendations */}
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" aria-hidden />
                Insights
              </CardTitle>
              <CardDescription>
                Derived from the class attention timeline
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {insights.length === 0 ? (
                <p className="py-6 text-center text-xs text-muted-foreground">
                  Not enough data yet. Insights appear once a session has a few
                  minutes of samples.
                </p>
              ) : (
                insights.map((ins) => (
                  <div
                    key={ins.title}
                    className="rounded-xl border border-border p-3 transition-colors hover:bg-accent/40"
                  >
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          ins.tone === "positive"
                            ? "excellent"
                            : ins.tone === "warning"
                              ? "warning"
                              : "default"
                        }
                      >
                        {ins.title}
                      </Badge>
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                      {ins.detail}
                    </p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-status-warning" aria-hidden />
                Recommendations
              </CardTitle>
              <CardDescription>
                Suggestions for the teacher, best interpreted with classroom context
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2.5">
                {buildRecommendations(students, timeline).map((r, i) => (
                  <li
                    key={i}
                    className="flex gap-2.5 rounded-xl border border-border p-3 text-xs leading-relaxed"
                  >
                    <TrendingUp
                      className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary"
                      aria-hidden
                    />
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        <ChartCard
          title="Attention over time"
          description="Class average with alert markers"
          height={280}
          loading={loading}
          empty={timeline.length === 0}
        >
          <AttentionAreaChart timeline={timeline} />
        </ChartCard>

        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard
            title="Student ranking"
            description="Average attention, highest to lowest"
            height={Math.max(220, students.length * 30)}
            loading={loading}
            empty={students.length === 0}
          >
            <RankingChart students={students} />
          </ChartCard>
          <div className="flex flex-col gap-4">
            <ChartCard
              title="Attention distribution"
              height={180}
              loading={loading}
              empty={students.length === 0}
            >
              <DistributionChart students={students} />
            </ChartCard>
            <ChartCard
              title="Phone usage"
              height={180}
              loading={loading}
              empty={students.length === 0}
            >
              <PhoneDonutChart students={students} />
            </ChartCard>
          </div>
        </div>

        <ChartCard
          title="Blink trends"
          description="Blink rate and eyes-closed share per student (a fatigue proxy)"
          loading={loading}
          empty={students.length === 0}
        >
          <BlinkTrendChart students={students} />
        </ChartCard>

        <Card>
          <CardHeader>
            <CardTitle>Engagement heatmap</CardTitle>
            <CardDescription>
              Every student across the session. Darker means more attentive.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {students.length === 0 ? (
              <p className="py-10 text-center text-xs text-muted-foreground">
                No student data for this session.
              </p>
            ) : (
              <EngagementHeatmap students={students} timelines={byStudentId} />
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function OverviewTile({
  label,
  value,
  hint,
  tone = "primary",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "primary" | "excellent" | "warning" | "critical";
}) {
  return (
    <Card className="p-4">
      <p className="text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p
        className={cn("mt-1 truncate text-xl font-semibold tracking-tight", {
          "text-primary": tone === "primary",
          "text-status-excellent": tone === "excellent",
          "text-status-warning": tone === "warning",
          "text-status-critical": tone === "critical",
        })}
      >
        {value}
      </p>
      {hint && <p className="mt-0.5 text-[11px] text-muted-foreground">{hint}</p>}
    </Card>
  );
}

function buildRecommendations(
  students: { avg_attention: number; phone_usage_ratio: number; label: string }[],
  timeline: { avg_attention: number; timestamp: number }[],
): string[] {
  const recs: string[] = [];
  if (students.length === 0 || timeline.length < 3) {
    return [
      "Record a full session to unlock tailored recommendations based on real engagement patterns.",
    ];
  }
  const struggling = students.filter((s) => s.avg_attention < 45);
  const phoneUsers = students.filter((s) => s.phone_usage_ratio > 0.1);
  const trough = timeline.reduce((a, b) =>
    b.avg_attention < a.avg_attention ? b : a,
  );

  if (struggling.length > 0) {
    recs.push(
      `${struggling.length} student${struggling.length > 1 ? "s" : ""} averaged below 45 (${struggling
        .slice(0, 3)
        .map((s) => s.label)
        .join(", ")}). A short check-in may help. These are behavioral signals, not proof of disengagement.`,
    );
  }
  if (phoneUsers.length > 0) {
    recs.push(
      `Phones were visible for over 10% of frames for ${phoneUsers.length} student${phoneUsers.length > 1 ? "s" : ""}. Consider a phones-away norm during instruction blocks.`,
    );
  }
  recs.push(
    `Attention was lowest around ${Math.floor(trough.timestamp / 60)} minutes in. An activity switch or short break near that point may lift the second half.`,
  );
  if (recs.length < 3) {
    recs.push(
      "Engagement stayed stable, so the current lesson pacing appears to be working well.",
    );
  }
  return recs;
}
