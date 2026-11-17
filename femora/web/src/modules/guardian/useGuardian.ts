import { useEffect } from "react";
import { useApp } from "../../lib/app-state";
import { usePersistent } from "../../lib/usePersistent";
import { EMPTY_INFO, checkInStatus, type CheckIn, type CheckInLog, type EmergencyInfo, type GuardianContact } from "./logic";

export function useGuardian() {
  const { profile } = useApp();
  const [contacts, setContacts] = usePersistent<GuardianContact[]>(`contacts:${profile.id}`, () => []); // shared with Connections
  const [guardians, setGuardians] = usePersistent<string[]>(`guardians:${profile.id}`, () => []);
  const [info, setInfo] = usePersistent<EmergencyInfo>(`emergency:${profile.id}`, () => EMPTY_INFO);
  const [checkIns, setCheckIns] = usePersistent<CheckIn[]>(`checkins:${profile.id}`, () => []);
  const [log, setLog] = usePersistent<CheckInLog[]>(`checkinlog:${profile.id}`, () => []);
  return { contacts, setContacts, guardians, setGuardians, info, setInfo, checkIns, setCheckIns, log, setLog };
}

/** In-app check-in alerts while Muse is open. Missed check-ins ask HER to alert someone; nothing is sent automatically. */
export function GuardianWatcher() {
  const app = useApp();
  const { checkIns, log } = useGuardian();
  useEffect(() => {
    const tick = () => {
      const dk = new Date().toISOString().slice(0, 10);
      for (const c of checkIns) {
        const s = checkInStatus(c, log);
        if (s === "due") app.notify({ key: `ci-due-${dk}-${c.id}`, category: "safety", priority: "high", title: `Check-in: ${c.label}`, body: "Tap to let Muse know you're okay.", link: "/app/guardian" });
        if (s === "missed") app.notify({ key: `ci-missed-${dk}-${c.id}`, category: "safety", priority: "critical", title: `Missed check-in: ${c.label}`, body: "If you're okay, check in. If not, open Guardian to call or message someone.", link: "/app/guardian" });
      }
    };
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, [checkIns, log, app]);
  return null;
}
