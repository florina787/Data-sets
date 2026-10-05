"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

/** GET a JSON endpoint as the current user, with loading / error state and manual reload. */
export function useApi<T>(path: string | null, userId: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(() => {
    if (!path) return;
    setLoading(true);
    setError(null);
    api.get<T>(path, userId)
      .then((d) => setData(d))
      .catch((e: ApiError) => { setError(e); setData(null); })
      .finally(() => setLoading(false));
  }, [path, userId]);
  useEffect(() => { load(); }, [load]);
  return { data, error, loading, reload: load };
}
