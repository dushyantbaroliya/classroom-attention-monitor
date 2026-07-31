import {
  Activity,
  Clock,
  Eye,
  Gauge,
  Hand,
  Smartphone,
  Users,
} from "lucide-react";
import { useMemo } from "react";
import { ActivityTimeline } from "../components/dashboard/ActivityTimeline";
import { ChartCard } from "../components/dashboard/ChartCard";
import {
  AttentionAreaChart,
  DistributionChart,
  PhoneDonutChart,
} from "../components/dashboard/charts";
import { MetricCard } from "../components/dashboard/MetricCard";
import { PageHeader } from "../components/layout/AppShell";
import { SessionPicker } from "../components/layout/SessionPicker";
import { LiveMonitor } from "../components/live/LiveMonitor";
import { SessionControls } from "../components/live/SessionControls";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { ErrorState } from "../components/ui/states";
import { useLiveFeed } from "../hooks/useLiveFeed";
import { useSelectedSession } from "../hooks/useSelectedSession";
import {
  useAnalytics,
  useAttendance,
  useIsRunning,
  useStatistics,
} from "../hooks/useSessionData";
import { deriveEvents } from "../lib/events";
import { fmtClock } from "../lib/utils";

export function DashboardPage() {
  const { sessionId } = useSelectedSession();
  const running = useIsRunning();
  const analytics = useAnalytics(sessionId);
  const statistics = useStatistics(sessionId);
  const attendance = useAttendance(sessionId);
  const { frame, connected } = useLiveFeed(running);

  const timeline = analytics.data?.timeline ?? [];
  const students = analytics.data?.students ?? [];
  const stats = statistics.data;
  const loading = analytics.isLoading || statistics.isLoading;

  const events = useMemo(
    () => deriveEvents(timeline, analytics.data?.session),
    [timeline, analytics.data?.session],
  );

  // Derived metrics for the hero cards.
  const sparkAttention = timeline.map((p) => p.avg_attention);
  const trend = useMemo(() => {
    if (timeline.length < 6) return null;
    const third = Math.floor(timeline.length / 3);
    const avg = (arr: typeof timeline) =>
      arr.reduce((s, p) => s + p.avg_attention, 0) / Math.max(1, arr.length);
    return avg(timeline.slice(-third)) - avg(timeline.slice(0, third));
  }, [timeline]);

  const avgBlink =
    students.length > 0
      ? students.reduce((s, x) => s + x.avg_blink_rate, 0) / students.length
      : 0;
  const handRaisers = students.filter((s) => s.hand_raised_ratio > 0).length;
  const duration = timeline.length > 0 ? timeline[timeline.length - 1].timestamp : 0;
  const present = attendance.data?.attendance.length ?? stats?.students_detected ?? 0;

  if (analytics.isError && statistics.isError) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <ErrorState
          message="No sessions have been recorded yet. Start a live stream or upload a video to begin monitoring."
          onRetry={() => {
            analytics.refetch();
            statistics.refetch();
          }}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Live classroom engagement overview"
        actions={<SessionPicker />}
      />

      <div className="flex flex-col gap-4">
        <SessionControls running={running} />

        {/* Hero metrics */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard
            index={0}
            label="Avg attention"
            value={stats?.class_average_attention}
            icon={Gauge}
            tone="primary"
            trend={trend}
            spark={sparkAttention}
            loading={loading}
          />
          <MetricCard
            index={1}
            label="Present"
            value={present}
            icon={Users}
            tone="good"
            spark={timeline.map((p) => p.students_present)}
            loading={loading}
          />
          <MetricCard
            index={2}
            label="Phone usage"
            value={stats?.phone_incidents}
            icon={Smartphone}
            tone="critical"
            spark={timeline.map((p) => p.phones_visible)}
            loading={loading}
          />
          <MetricCard
            index={3}
            label="Hand raises"
            value={handRaisers}
            icon={Hand}
            tone="excellent"
            spark={timeline.map((p) => p.hands_raised)}
            loading={loading}
          />
          <MetricCard
            index={4}
            label="Blink rate"
            value={avgBlink}
            decimals={1}
            suffix="/min"
            icon={Eye}
            tone="good"
            loading={loading}
          />
          <MetricCard
            index={5}
            label="Duration"
            value={duration / 60}
            decimals={1}
            suffix="min"
            icon={Clock}
            tone="warning"
            loading={loading}
          />
        </div>

        {/* Live + activity */}
        <div className="grid gap-4 xl:grid-cols-3">
          <div className="xl:col-span-2">
            <LiveMonitor frame={frame} connected={connected} running={running} />
          </div>
          <Card className="flex flex-col">
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted-foreground" aria-hidden />
                Activity
              </CardTitle>
              {duration > 0 && (
                <span className="text-[11px] tabular-nums text-muted-foreground">
                  {fmtClock(duration)} elapsed
                </span>
              )}
            </CardHeader>
            <CardContent className="max-h-[420px] flex-1 overflow-y-auto">
              <ActivityTimeline events={events} />
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        <ChartCard
          title="Attention over time"
          description="Class average across the session, alert dips highlighted"
          height={280}
          loading={loading}
          empty={timeline.length === 0}
        >
          <AttentionAreaChart timeline={timeline} />
        </ChartCard>

        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard
            title="Attention distribution"
            description="How many students fall in each engagement band"
            loading={loading}
            empty={students.length === 0}
          >
            <DistributionChart students={students} />
          </ChartCard>
          <ChartCard
            title="Phone usage"
            description="Share of students with a phone detected"
            loading={loading}
            empty={students.length === 0}
          >
            <PhoneDonutChart students={students} />
          </ChartCard>
        </div>
      </div>
    </>
  );
}
