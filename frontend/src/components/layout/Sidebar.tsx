import { motion } from "framer-motion";
import {
  BarChart3,
  ChevronsLeft,
  FileText,
  LayoutDashboard,
  ScanFace,
  Settings,
  Users,
  Video,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "../../lib/utils";
import { Button } from "../ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/live", label: "Live Monitoring", icon: Video },
  { to: "/students", label: "Students", icon: Users },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/settings", label: "Settings", icon: Settings },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <aside
      className={cn(
        "glass sticky top-0 z-40 flex h-screen shrink-0 flex-col border-r border-border",
        "transition-[width] duration-300 ease-out motion-reduce:transition-none",
        collapsed ? "w-[68px]" : "w-[232px]",
      )}
      aria-label="Primary navigation"
    >
      {/* Logo */}
      <div className="flex h-14 items-center gap-2.5 px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/15">
          <ScanFace className="h-5 w-5 text-primary" aria-hidden />
        </div>
        {!collapsed && (
          <span className="truncate text-sm font-semibold tracking-tight">
            Attentio
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-1 px-2.5 py-3">
        {NAV.map(({ to, label, icon: Icon, end }) => {
          const link = (
            <NavLink key={to} to={to} end={end} className="block">
              {({ isActive }) => (
                <span
                  className={cn(
                    "relative flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm transition-colors",
                    isActive
                      ? "font-medium text-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  {isActive && (
                    <motion.span
                      layoutId="nav-active"
                      className="absolute inset-0 rounded-lg bg-accent"
                      transition={{ type: "spring", stiffness: 400, damping: 34 }}
                    />
                  )}
                  <Icon className="relative z-10 h-4 w-4 shrink-0" aria-hidden />
                  {!collapsed && (
                    <span className="relative z-10 truncate">{label}</span>
                  )}
                  {isActive && (
                    <span className="absolute -left-2.5 top-1/2 z-10 h-4 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
                  )}
                </span>
              )}
            </NavLink>
          );
          return collapsed ? (
            <Tooltip key={to}>
              <TooltipTrigger asChild>{link}</TooltipTrigger>
              <TooltipContent side="right">{label}</TooltipContent>
            </Tooltip>
          ) : (
            link
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-border p-2.5">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="w-full"
        >
          <ChevronsLeft
            className={cn(
              "transition-transform duration-300",
              collapsed && "rotate-180",
            )}
            aria-hidden
          />
        </Button>
      </div>
    </aside>
  );
}
