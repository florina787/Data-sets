import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

/** Fetch a resource and refresh it on an interval. Errors are surfaced, not hidden. */
export function usePoll<T>(path: string | null, intervalMs = 3000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const pathRef = useRef(path);
  pathRef.current = path;

  const refresh = useCallback(async () => {
    const current = pathRef.current;
    if (!current) {
      setLoading(false);
      return;
    }
    try {
      const result = await api<T>(current);
      if (pathRef.current === current) {
        setData(result);
        setError(null);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    setData(null);
    refresh();
    if (!path) return;
    const id = window.setInterval(refresh, intervalMs);
    return () => window.clearInterval(id);
  }, [path, intervalMs, refresh]);

  return { data, error, loading, refresh };
}

/** Run an action, track its busy state and keep the last error/result message. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const run = useCallback(async (fn: () => Promise<unknown>, success?: string) => {
    setBusy(true);
    setMessage(null);
    try {
      await fn();
      if (success) setMessage({ kind: "ok", text: success });
    } catch (e) {
      setMessage({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, message, run, setMessage };
}
