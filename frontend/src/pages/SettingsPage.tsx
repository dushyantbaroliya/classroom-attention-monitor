import { Cpu, Moon, ShieldCheck, Sun } from "lucide-react";
import { PageHeader } from "../components/layout/AppShell";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { useTheme } from "../hooks/useTheme";
import { useHealth } from "../hooks/useSessionData";

export function SettingsPage() {
  const { theme, toggle } = useTheme();
  const { data: health } = useHealth();

  return (
    <>
      <PageHeader
        title="Settings"
        description="Appearance, system status and data handling"
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
            <CardDescription>
              Theme preference is stored locally in your browser
            </CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              {theme === "dark" ? (
                <Moon className="h-4 w-4 text-muted-foreground" aria-hidden />
              ) : (
                <Sun className="h-4 w-4 text-muted-foreground" aria-hidden />
              )}
              {theme === "dark" ? "Dark" : "Light"} theme
            </div>
            <Button variant="outline" size="sm" onClick={toggle}>
              Switch to {theme === "dark" ? "light" : "dark"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-muted-foreground" aria-hidden />
              System status
            </CardTitle>
            <CardDescription>Backend health and pipeline readiness</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2.5 text-sm">
            <Row label="API">
              <Badge variant={health ? "excellent" : "critical"}>
                {health ? `online · v${health.version}` : "unreachable"}
              </Badge>
            </Row>
            <Row label="CV pipeline">
              <Badge variant={health?.pipeline_available ? "excellent" : "warning"}>
                {health?.pipeline_available
                  ? "YOLO + MediaPipe ready"
                  : "CV deps not installed"}
              </Badge>
            </Row>
            <Row label="Active session">
              <Badge variant={health?.active_session_id ? "primary" : "outline"}>
                {health?.active_session_id
                  ? `#${health.active_session_id}`
                  : "none"}
              </Badge>
            </Row>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-status-excellent" aria-hidden />
              Privacy & ethics
            </CardTitle>
            <CardDescription>
              Guardrails built into this system by design
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-2.5 text-xs leading-relaxed text-muted-foreground sm:grid-cols-2">
              <li className="rounded-xl border border-border p-3">
                <span className="font-medium text-foreground">
                  No face recognition.
                </span>{" "}
                Students exist only as tracker IDs. No embeddings, names or
                biometric identifiers are computed or stored.
              </li>
              <li className="rounded-xl border border-border p-3">
                <span className="font-medium text-foreground">
                  Local processing.
                </span>{" "}
                Video never leaves the machine; only derived numeric analytics
                are written to the local database.
              </li>
              <li className="rounded-xl border border-border p-3">
                <span className="font-medium text-foreground">
                  Behavior, not cognition.
                </span>{" "}
                Scores estimate observable proxies and carry real uncertainty.
                They are not measurements of what a student is thinking.
              </li>
              <li className="rounded-xl border border-border p-3">
                <span className="font-medium text-foreground">
                  Not for grading.
                </span>{" "}
                Intended as teaching feedback and decision support, never for
                automated evaluation or discipline.
              </li>
            </ul>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Pipeline configuration</CardTitle>
            <CardDescription>
              Scoring weights, thresholds and model paths are managed
              server-side
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-xs leading-relaxed text-muted-foreground">
              All tunable behavior lives in{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">
                config.yaml
              </code>{" "}
              on the backend: detector confidence, tracker thresholds, head
              pose and EAR cutoffs, gaze ratios, and the attention scoring
              weights. Edit that file and restart the API to apply changes;
              the dashboard picks them up automatically.
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      {children}
    </div>
  );
}
