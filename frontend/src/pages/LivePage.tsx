import { CircleDot, Users } from "lucide-react";
import { PageHeader } from "../components/layout/AppShell";
import { LiveMonitor } from "../components/live/LiveMonitor";
import { SessionControls } from "../components/live/SessionControls";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { ProgressRing } from "../components/ui/progress-ring";
import { EmptyState } from "../components/ui/states";
import { useLiveFeed } from "../hooks/useLiveFeed";
import { useHealth, useIsRunning } from "../hooks/useSessionData";
import { attentionBand, BAND_LABEL } from "../lib/utils";

export function LivePage() {
  const running = useIsRunning();
  const { data: health } = useHealth();
  const { frame, connected } = useLiveFeed(running);
  const students = frame?.students ?? [];

  return (
    <>
      <PageHeader
        title="Live Monitoring"
        description="Real-time annotated feed with per-student engagement signals"
        actions={
          <Badge variant={running ? "excellent" : "outline"}>
            <CircleDot className="h-3 w-3" aria-hidden />
            {running ? `Session #${health?.active_session_id}` : "Idle"}
          </Badge>
        }
      />

      <div className="flex flex-col gap-4">
        <SessionControls running={running} />

        <div className="grid gap-4 xl:grid-cols-4">
          <div className="xl:col-span-3">
            <LiveMonitor frame={frame} connected={connected} running={running} />
          </div>

          <Card className="flex flex-col">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-4 w-4 text-muted-foreground" aria-hidden />
                In frame ({students.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="max-h-[520px] flex-1 space-y-2 overflow-y-auto">
              {students.length === 0 ? (
                <EmptyState
                  icon={Users}
                  title="No students detected"
                  message="Once the pipeline detects students, each one appears here with a live attention ring."
                />
              ) : (
                students.map((s) => {
                  const band = attentionBand(s.attention);
                  return (
                    <div
                      key={s.track_id}
                      className="flex items-center gap-3 rounded-xl border border-border p-2.5 transition-colors hover:bg-accent/50"
                    >
                      <ProgressRing value={s.attention} size={44} strokeWidth={4} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{s.label}</p>
                        <p className="truncate text-[11px] text-muted-foreground">
                          {s.head_pose} · gaze {s.gaze}
                        </p>
                      </div>
                      <Badge variant={band}>{BAND_LABEL[band]}</Badge>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
