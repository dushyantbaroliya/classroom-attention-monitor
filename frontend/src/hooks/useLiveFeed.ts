import { useEffect, useRef, useState } from "react";
import { liveSocketUrl } from "../api";
import type { LiveFrame } from "../types";

/** Subscribes to the backend's live WebSocket feed with auto-reconnect. */
export function useLiveFeed(enabled: boolean) {
  const [frame, setFrame] = useState<LiveFrame | null>(null);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) {
      socketRef.current?.close();
      socketRef.current = null;
      setConnected(false);
      return;
    }

    let cancelled = false;
    let retryTimer: number | undefined;

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(liveSocketUrl());
      socketRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data) as LiveFrame;
        if (payload.type === "frame") setFrame(payload);
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) retryTimer = window.setTimeout(connect, 2000);
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      cancelled = true;
      window.clearTimeout(retryTimer);
      socketRef.current?.close();
    };
  }, [enabled]);

  return { frame, connected };
}
