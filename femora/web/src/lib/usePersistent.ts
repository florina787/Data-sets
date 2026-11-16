import { useEffect, useState } from "react";
import { load, save } from "./storage";

/** useState that persists to browser-local demo storage. */
export function usePersistent<T>(key: string, init: () => T) {
  const [v, setV] = useState<T>(() => load<T>(key, undefined as T) ?? init());
  useEffect(() => save(key, v), [key, v]);
  return [v, setV] as const;
}
