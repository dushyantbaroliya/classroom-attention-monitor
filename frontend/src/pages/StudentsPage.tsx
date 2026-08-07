import { LayoutGrid, List, UserX } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "../components/layout/AppShell";
import { SessionPicker } from "../components/layout/SessionPicker";
import { StudentCard } from "../components/students/StudentCard";
import { StudentsTable } from "../components/students/StudentsTable";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Skeleton } from "../components/ui/skeleton";
import { EmptyState } from "../components/ui/states";
import { useSelectedSession } from "../hooks/useSelectedSession";
import { useAnalytics, useStudentTimelines } from "../hooks/useSessionData";

export function StudentsPage() {
  const { sessionId } = useSelectedSession();
  const analytics = useAnalytics(sessionId);
  const students = analytics.data?.students ?? [];
  const { byStudentId } = useStudentTimelines(students, sessionId);
  const [view, setView] = useState<"grid" | "table">("grid");

  return (
    <>
      <PageHeader
        title="Students"
        description={`${students.length} anonymous tracked student${students.length === 1 ? "" : "s"}, with no face recognition`}
        actions={
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-border p-0.5">
              <Button
                variant={view === "grid" ? "subtle" : "ghost"}
                size="sm"
                onClick={() => setView("grid")}
                aria-label="Grid view"
                aria-pressed={view === "grid"}
              >
                <LayoutGrid aria-hidden />
              </Button>
              <Button
                variant={view === "table" ? "subtle" : "ghost"}
                size="sm"
                onClick={() => setView("table")}
                aria-label="Table view"
                aria-pressed={view === "table"}
              >
                <List aria-hidden />
              </Button>
            </div>
            <SessionPicker />
          </div>
        }
      />

      {analytics.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className="p-4">
              <div className="flex items-center gap-3">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="flex-1">
                  <Skeleton className="h-3.5 w-24" />
                  <Skeleton className="mt-1.5 h-2.5 w-32" />
                </div>
                <Skeleton className="h-12 w-12 rounded-full" />
              </div>
              <Skeleton className="mt-4 h-10 w-full" />
            </Card>
          ))}
        </div>
      ) : students.length === 0 ? (
        <Card>
          <EmptyState
            icon={UserX}
            title="No students detected"
            message="Run a monitoring session. Every student the tracker finds will appear here with their own engagement card."
          />
        </Card>
      ) : view === "grid" ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          {students.map((s, i) => (
            <StudentCard
              key={s.student_id}
              student={s}
              timeline={byStudentId.get(s.student_id)}
              index={i}
            />
          ))}
        </div>
      ) : (
        <StudentsTable students={students} />
      )}
    </>
  );
}
