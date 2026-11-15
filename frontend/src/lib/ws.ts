"use client";

import { useEffect, useRef, useState } from "react";
import { eventsUrl } from "./api";
import type { EventEnvelope } from "./types";

/** Subscribes to the tenant event stream with automatic reconnect. Returns connection state. */
export function useEventStream(onEvent: (e: EventEnvelope) => void): boolean {
  const [connected, setConnected] = useState(false);
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;
    let delay = 1000;

    const connect = () => {
      const url = eventsUrl();
      if (!url || closed) return;
      ws = new WebSocket(url);
      ws.onopen = () => {
        delay = 1000;
        setConnected(true);
      };
      ws.onmessage = (m) => {
        try {
          handler.current(JSON.parse(String(m.data)) as EventEnvelope);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (closed) return;
        timer = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 15000);
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, []);

  return connected;
}
