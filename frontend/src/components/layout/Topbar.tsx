import { AnimatePresence, motion } from "framer-motion";
import { Bell, Moon, Search, Sun } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../../hooks/useTheme";
import { useAnalytics, useHealth } from "../../hooks/useSessionData";
import { deriveEvents } from "../../lib/events";
import { cn, fmtClock } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Input } from "../ui/input";

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(t);
  }, []);
  return now;
}

export function Topbar() {
  const { theme, toggle } = useTheme();
  const { data: health } = useHealth();
  const { data: analytics } = useAnalytics();
  const navigate = useNavigate();
  const now = useClock();
  const running = health?.active_session_id != null;

  const notifications = useMemo(
    () =>
      deriveEvents(analytics?.timeline ?? [], analytics?.session).slice(0, 6),
    [analytics],
  );

  return (
    <header className="topbar glass sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border px-4 lg:px-6">
      {/* Search */}
      <div className="relative w-full max-w-xs">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          type="search"
          placeholder="Search students, sessions…"
          aria-label="Search"
          className="bg-muted/50 pl-8 transition-all focus:max-w-none"
          onKeyDown={(e) => {
            if (e.key === "Enter") navigate("/students");
          }}
        />
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        {/* Session status */}
        <Badge
          variant={running ? "excellent" : "outline"}
          className="hidden sm:inline-flex"
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              running ? "animate-pulse bg-status-excellent" : "bg-muted-foreground/50",
            )}
          />
          {running ? `Session #${health?.active_session_id} live` : "No live session"}
        </Badge>

        <span className="hidden px-1 text-xs tabular-nums text-muted-foreground md:inline">
          {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>

        {/* Notifications */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Notifications">
              <span className="relative">
                <Bell aria-hidden />
                {notifications.length > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-primary" />
                )}
              </span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-80">
            <DropdownMenuLabel>Recent activity</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {notifications.length === 0 ? (
              <p className="px-2.5 py-6 text-center text-xs text-muted-foreground">
                Nothing yet — start a session to see activity.
              </p>
            ) : (
              notifications.map((n, i) => (
                <DropdownMenuItem key={i} className="flex-col items-start gap-0.5">
                  <span className="flex w-full items-center justify-between">
                    <span className="text-xs font-medium">{n.title}</span>
                    <span className="text-[10px] tabular-nums text-muted-foreground">
                      {fmtClock(n.timestamp)}
                    </span>
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    {n.detail}
                  </span>
                </DropdownMenuItem>
              ))
            )}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Theme toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggle}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={theme}
              initial={{ rotate: -90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 90, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="flex"
            >
              {theme === "dark" ? <Sun aria-hidden /> : <Moon aria-hidden />}
            </motion.span>
          </AnimatePresence>
        </Button>

        {/* Avatar */}
        <div
          className="ml-1 flex h-8 w-8 select-none items-center justify-center rounded-full bg-gradient-to-br from-primary/80 to-primary/40 text-xs font-semibold text-primary-foreground"
          aria-label="Teacher account"
          title="Teacher"
        >
          T
        </div>
      </div>
    </header>
  );
}
