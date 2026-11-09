import { Download, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useApp } from "../stores/app";
import { Button } from "./ui";

const LAST_CHECK = "veena.updates.lastCheck";
const DAY_MS = 86_400_000;

type Update = Awaited<ReturnType<NonNullable<typeof window.veena>["checkForUpdates"]>>;

/** Once a day, if the user allows it, shows a banner when a newer VEENA release exists. Never installs anything. */
export function UpdateBanner() {
  const { settings } = useApp();
  const [update, setUpdate] = useState<Update | null>(null);
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    if (!settings?.check_updates || !settings.onboarded || !window.veena?.checkForUpdates) return;
    let last = 0;
    try {
      last = Number(localStorage.getItem(LAST_CHECK) ?? 0);
    } catch {
      /* storage unavailable: check anyway */
    }
    if (Date.now() - last < DAY_MS) return;
    void window.veena.checkForUpdates().then((u) => {
      try {
        localStorage.setItem(LAST_CHECK, String(Date.now()));
      } catch {
        /* ignore */
      }
      if (u.newer) setUpdate(u);
    });
  }, [settings?.check_updates, settings?.onboarded]);
  if (!update || hidden) return null;
  return (
    <div role="status" className="fixed right-4 bottom-4 z-40 flex max-w-sm items-start gap-3 rounded-2xl border border-cream bg-white p-4 shadow-[var(--shadow-lift)]">
      <Download size={18} className="mt-0.5 shrink-0 text-caramel" />
      <div className="text-sm">
        <p className="font-semibold text-espresso">VEENA {update.latest} is available</p>
        <p className="mt-0.5 text-xs text-mocha">You have {update.current}. Download it from the release page and install it over this version; your conversations and settings are kept.</p>
        <Button size="sm" variant="primary" className="mt-2" onClick={() => update.url && void window.veena?.openExternal(update.url)}>
          View release
        </Button>
      </div>
      <button type="button" aria-label="Dismiss update notice" onClick={() => setHidden(true)} className="text-sand hover:text-bark">
        <X size={15} />
      </button>
    </div>
  );
}
