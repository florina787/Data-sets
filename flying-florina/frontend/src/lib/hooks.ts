import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { get, post } from "./api";
import { useSession } from "./store";
import type { RunView } from "./types";

export function useApi<T>(key: unknown[], path: string, enabled = true) {
  const actor = useSession((s) => s.actor?.id);
  return useQuery({ queryKey: [...key, actor], queryFn: () => get<T>(path).then((r) => r.data), enabled });
}

/** Runs a natural-language workflow synchronously and returns its run view (used by domain pages). */
export function useWorkflow() {
  const [run, setRun] = useState<RunView | null>(null);
  const m = useMutation({
    mutationFn: (args: { query: string; options?: Record<string, unknown> }) => post<RunView>("/api/chat/query", { query: args.query, wait: true, options: args.options ?? {} }),
    onSuccess: (r) => setRun(r.data),
  });
  return { run, run_: m.mutate, pending: m.isPending, error: m.error };
}
