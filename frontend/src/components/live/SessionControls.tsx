import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Download, Play, Square, Upload, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, DEMO_NOTICE, IS_STATIC_DEMO } from "../../api";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";

interface SessionControlsProps {
  running: boolean;
}

/** Start/stop live sessions, upload videos, export CSV, with inline toasts. */
export function SessionControls({ running }: SessionControlsProps) {
  const [source, setSource] = useState("0");
  const [toast, setToast] = useState<{ ok: boolean; text: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const invalidate = () => queryClient.invalidateQueries();

  const start = useMutation({
    mutationFn: () => api.streamStart(source, "Live session"),
    onSuccess: (r) => {
      setToast({ ok: true, text: `Session #${r.session_id} started` });
      invalidate();
    },
    onError: (e) => setToast({ ok: false, text: e.message }),
  });

  const stop = useMutation({
    mutationFn: api.streamStop,
    onSuccess: () => {
      setToast({ ok: true, text: "Session stopped" });
      invalidate();
    },
    onError: (e) => setToast({ ok: false, text: e.message }),
  });

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadVideo(file),
    onSuccess: (r) => {
      setToast({ ok: true, text: `Analyzing ${r.filename}…` });
      invalidate();
    },
    onError: (e) => setToast({ ok: false, text: e.message }),
  });

  const busy = start.isPending || stop.isPending || upload.isPending;
  const locked = IS_STATIC_DEMO;

  // In the static demo the capture controls can't work, so disable them and
  // explain why on hover, rather than letting clicks fail mysteriously.
  const withDemoTooltip = (node: React.ReactNode) =>
    locked ? (
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0}>{node}</span>
        </TooltipTrigger>
        <TooltipContent>{DEMO_NOTICE}</TooltipContent>
      </Tooltip>
    ) : (
      node
    );

  return (
    <Card className="no-print flex flex-wrap items-center gap-2.5 p-4">
      <label
        htmlFor="video-source"
        className="text-xs font-medium text-muted-foreground"
      >
        Source
      </label>
      <Input
        id="video-source"
        value={source}
        onChange={(e) => setSource(e.target.value)}
        placeholder="0 = webcam, or a video path"
        disabled={running || busy || locked}
        className="w-48"
      />

      {running ? (
        <Button
          variant="destructive"
          disabled={busy}
          onClick={() => stop.mutate()}
        >
          <Square aria-hidden /> Stop session
        </Button>
      ) : (
        withDemoTooltip(
          <Button disabled={busy || locked} onClick={() => start.mutate()}>
            <Play aria-hidden /> Start stream
          </Button>,
        )
      )}

      {withDemoTooltip(
        <Button
          variant="outline"
          disabled={busy || running || locked}
          onClick={() => fileInput.current?.click()}
        >
          <Upload aria-hidden /> Upload video
        </Button>,
      )}
      <input
        ref={fileInput}
        type="file"
        accept=".mp4,.avi,.mov,.mkv,.webm"
        className="hidden"
        aria-label="Upload a video file"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload.mutate(file);
          e.target.value = "";
        }}
      />

      <Button variant="ghost" onClick={() => window.open(api.csvUrl(), "_blank")}>
        <Download aria-hidden /> CSV
      </Button>

      <AnimatePresence>
        {toast && (
          <motion.span
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0 }}
            role="status"
            className={`ml-auto flex items-center gap-1.5 text-xs font-medium ${
              toast.ok ? "text-status-excellent" : "text-status-critical"
            }`}
          >
            {toast.ok ? (
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
            ) : (
              <XCircle className="h-3.5 w-3.5" aria-hidden />
            )}
            {toast.text}
          </motion.span>
        )}
      </AnimatePresence>
    </Card>
  );
}
