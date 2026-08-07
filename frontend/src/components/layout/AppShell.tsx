import { AnimatePresence, motion } from "framer-motion";
import { Github, Info } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { IS_STATIC_DEMO } from "../../api";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

const REPO_URL = "https://github.com/dushyantbaroliya/classroom-attention-monitor";

/** Explains that the hosted demo shows a recorded session, not live capture. */
function DemoBanner() {
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 border-b border-primary/20 bg-primary/10 px-4 py-2 text-center text-xs">
      <Info className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
      <span className="text-foreground">
        <strong className="font-semibold">Interactive demo</strong> showing
        real analytics from a recorded session. Live webcam capture runs the
        Python CV pipeline locally.
      </span>
      <a
        href={REPO_URL}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1 font-medium text-primary underline-offset-2 hover:underline"
      >
        <Github className="h-3.5 w-3.5" aria-hidden />
        View source
      </a>
    </div>
  );
}

const SIDEBAR_KEY = "cam-sidebar-collapsed";
const AUTO_COLLAPSE_BELOW = 1024; // tablets and narrow laptops

export function AppShell({ children }: { children: ReactNode }) {
  const [userCollapsed, setUserCollapsed] = useState(
    () => localStorage.getItem(SIDEBAR_KEY) === "1",
  );
  const [narrow, setNarrow] = useState(
    () => window.innerWidth < AUTO_COLLAPSE_BELOW,
  );
  const location = useLocation();

  // Reclaim horizontal space automatically on smaller viewports; the user's
  // explicit preference still applies once there's room for it.
  useEffect(() => {
    const onResize = () =>
      setNarrow(window.innerWidth < AUTO_COLLAPSE_BELOW);
    onResize(); // sync on mount, in case the viewport changed before hydration
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const collapsed = narrow || userCollapsed;

  const toggle = () =>
    setUserCollapsed((c) => {
      localStorage.setItem(SIDEBAR_KEY, c ? "0" : "1");
      return !c;
    });

  return (
    <div className="flex min-h-screen">
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <div className="flex min-w-0 flex-1 flex-col">
        {IS_STATIC_DEMO && <DemoBanner />}
        <Topbar />
        <AnimatePresence mode="wait">
          <motion.main
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="mx-auto w-full max-w-[1500px] flex-1 p-4 lg:p-6"
          >
            {children}
          </motion.main>
        </AnimatePresence>
      </div>
    </div>
  );
}

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight lg:text-2xl">
          {title}
        </h1>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
