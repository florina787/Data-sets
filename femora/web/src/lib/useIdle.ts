import { useEffect, useState } from "react";

/** True once the browser is idle (or after `timeout` ms). Used to defer heavy, below-the-fold work. */
export function useIdle(timeout = 1200) {
  const [idle, setIdle] = useState(false);
  useEffect(() => {
    const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number; cancelIdleCallback?: (id: number) => void };
    if (w.requestIdleCallback) { const id = w.requestIdleCallback(() => setIdle(true), { timeout }); return () => w.cancelIdleCallback?.(id); }
    const id = window.setTimeout(() => setIdle(true), 200);
    return () => clearTimeout(id);
  }, [timeout]);
  return idle;
}
