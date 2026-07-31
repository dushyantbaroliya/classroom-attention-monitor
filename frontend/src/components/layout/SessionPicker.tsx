import { Check, ChevronDown, History } from "lucide-react";
import { useSessions } from "../../hooks/useSessionData";
import { useSelectedSession } from "../../hooks/useSelectedSession";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

/** Session selector shown in page headers. */
export function SessionPicker() {
  const { data: sessions = [] } = useSessions();
  const { sessionId, setSessionId } = useSelectedSession();
  const current = sessions.find((s) => s.session_id === sessionId);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <History aria-hidden />
          {current ? `#${current.session_id} ${current.name}` : "Latest session"}
          <ChevronDown aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Sessions</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => setSessionId(undefined)}>
          {sessionId === undefined && <Check className="h-3.5 w-3.5" aria-hidden />}
          <span className={sessionId === undefined ? "" : "ml-5"}>
            Latest session
          </span>
        </DropdownMenuItem>
        {sessions.map((s) => (
          <DropdownMenuItem
            key={s.session_id}
            onSelect={() => setSessionId(s.session_id)}
          >
            {sessionId === s.session_id && (
              <Check className="h-3.5 w-3.5" aria-hidden />
            )}
            <span
              className={`flex-1 truncate ${sessionId === s.session_id ? "" : "ml-5"}`}
            >
              #{s.session_id} {s.name}
            </span>
            <span className="text-[10px] text-muted-foreground">{s.status}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
