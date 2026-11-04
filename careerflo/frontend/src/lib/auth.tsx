import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import { setLocalToken, signOutLocal, supabase } from "./session";

export type Me = { id: string; email: string; is_admin: boolean; email_verified: boolean };
type Ctx = {
  me: Me | null; loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<string | null>;
  resetPassword: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
};
const AuthCtx = createContext<Ctx>(null as unknown as Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try { setMe(await api<Me>("/api/auth/me")); } catch { setMe(null); } finally { setLoading(false); }
  }, []);
  useEffect(() => {
    refresh();
    const off = () => setMe(null);
    window.addEventListener("cf:signedout", off);
    const sub = supabase?.auth.onAuthStateChange(() => refresh());
    return () => { window.removeEventListener("cf:signedout", off); sub?.data.subscription.unsubscribe(); };
  }, [refresh]);

  const value: Ctx = {
    me, loading,
    async signIn(email, password) {
      if (supabase) {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const r = await api<{ access_token: string }>("/api/auth/login", { method: "POST", json: { email, password } });
        setLocalToken(r.access_token);
      }
      await refresh();
    },
    async signUp(email, password) {
      if (supabase) {
        const { data, error } = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin + "/app" } });
        if (error) throw error;
        if (!data.session) return "Check your inbox to verify your email, then sign in.";
      } else {
        const r = await api<{ access_token: string }>("/api/auth/register", { method: "POST", json: { email, password } });
        setLocalToken(r.access_token);
      }
      await refresh();
      return null;
    },
    async resetPassword(email) {
      if (!supabase) throw new Error("Password reset emails are sent by Supabase Auth in production deployments.");
      const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: window.location.origin + "/login" });
      if (error) throw error;
    },
    async signOut() { if (supabase) await supabase.auth.signOut(); signOutLocal(); },
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
