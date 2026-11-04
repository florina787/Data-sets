/** Session handling: Supabase Auth when VITE_SUPABASE_URL is set, otherwise the backend's local auth. */
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
export const supabase: SupabaseClient | null = url && anon ? createClient(url, anon) : null;
const KEY = "cf.token";

export async function getToken(): Promise<string | null> {
  if (supabase) return (await supabase.auth.getSession()).data.session?.access_token ?? null;
  try { return localStorage.getItem(KEY); } catch { return null; }
}

export function setLocalToken(t: string) { try { localStorage.setItem(KEY, t); } catch { /* private mode */ } }

export function signOutLocal() {
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
  window.dispatchEvent(new Event("cf:signedout"));
}
