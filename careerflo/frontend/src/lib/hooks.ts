import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { idem } from "./utils";

export type FeatureUsage = {
  id: string; name: string; description: string; unit: string; trial_limit: number; trial_used: number;
  trial_remaining: number; plan_limit: number; plan_remaining: number; available: number; final_free_use: boolean;
};
export type Usage = { plan: { id: string; name: string }; subscription: any; features: FeatureUsage[] };

export const useUsage = () => useQuery({ queryKey: ["usage"], queryFn: () => api<Usage>("/api/usage") });
export const useFeature = (id: string) => {
  const q = useUsage();
  return q.data?.features.find((f) => f.id === id);
};

/** A metered POST: one idempotency key per user action, usage refreshed afterwards. */
export function useMetered<T = any>(path: string | ((v: any) => string)) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: any) => api<T>(typeof path === "function" ? path(body) : path, { method: "POST", json: body, idempotent: idem() }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["usage"] }),
  });
}
