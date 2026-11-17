// FEMORA Guardian: deterministic safety helpers. Nothing here sends anything by itself.
export interface GuardianContact { id: string; name: string; phone?: string; email?: string; role: string }
export interface EmergencyInfo { fullName: string; dateOfBirth: string; bloodType: string; conditions: string; allergies: string; medications: string; clinician: string; notes: string; pets: string }
export interface CheckIn { id: string; time: string; days: number[]; graceMin: number; label: string; enabled: boolean }  // days: 0=Sun..6
export interface CheckInLog { checkInId: string; date: string; at: number; status: "ok" | "missed-acknowledged" }

export const EMPTY_INFO: EmergencyInfo = { fullName: "", dateOfBirth: "", bloodType: "", conditions: "", allergies: "", medications: "", clinician: "", notes: "", pets: "" };

/** Main public emergency numbers (verify locally; 112 also works on most mobile networks in many countries). */
const NUMBERS: Record<string, string> = {
  "United States": "911", Canada: "911", Mexico: "911", "United Kingdom": "999", Ireland: "112", India: "112", Australia: "000", "New Zealand": "111",
  Japan: "119", "South Korea": "119", China: "120", Singapore: "995", Nigeria: "112", "South Africa": "10111", Kenya: "999", Brazil: "192", Philippines: "911",
  Germany: "112", France: "112", Spain: "112", Italy: "112", Netherlands: "112", Sweden: "112", Norway: "113", "United Arab Emirates": "999", "Saudi Arabia": "997",
};
export function emergencyNumber(country: string) { return NUMBERS[country] ?? "112"; }
export const knownCountry = (country: string) => country in NUMBERS;

export function sosMessage(name: string, location?: { lat: number; lon: number; accuracy: number }) {
  const where = location ? ` My location (accurate to about ${Math.round(location.accuracy)} m): https://maps.google.com/?q=${location.lat.toFixed(5)},${location.lon.toFixed(5)}` : "";
  return `URGENT from ${name || "me"}: I need help. Please call or come to me as soon as you can.${where}`;
}

export const checkInMessage = (name: string, label: string) => `Hi, it's ${name || "me"}. I missed my "${label}" safety check-in. Could you call me to make sure I'm okay?`;

const mins = (t: string) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };

/** Status of each enabled check-in for today: not-today, upcoming, due (in grace window), missed, done. */
export function checkInStatus(c: CheckIn, log: CheckInLog[], now = new Date()) {
  const dk = now.toISOString().slice(0, 10);
  if (!c.enabled || !c.days.includes(now.getDay())) return "not-today" as const;
  if (log.some((l) => l.checkInId === c.id && l.date === dk)) return "done" as const;
  const n = now.getHours() * 60 + now.getMinutes(), t = mins(c.time);
  if (n < t) return "upcoming" as const;
  if (n <= t + c.graceMin) return "due" as const;
  return "missed" as const;
}

export function emergencyCard(info: EmergencyInfo, contacts: GuardianContact[]) {
  const line = (k: string, v: string) => (v.trim() ? `${k}: ${v}` : "");
  return ["EMERGENCY INFORMATION", line("Name", info.fullName), line("Date of birth", info.dateOfBirth), line("Blood type", info.bloodType), line("Conditions", info.conditions),
    line("Allergies", info.allergies), line("Medications", info.medications), line("Clinician", info.clinician), line("Notes", info.notes), line("Pet care", info.pets),
    contacts.length ? `Emergency contacts: ${contacts.map((c) => `${c.name} (${c.role}) ${c.phone ?? c.email ?? ""}`.trim()).join("; ")}` : ""].filter(Boolean).join("\n");
}

/** What works today vs what needs infrastructure. Shown in the UI, verbatim. */
export const CAPABILITIES: { feature: string; status: "works" | "server" | "mobile"; detail: string }[] = [
  { feature: "Call emergency services", status: "works", detail: "Opens your phone dialler with the local number." },
  { feature: "SOS to trusted contacts", status: "works", detail: "Opens WhatsApp or SMS with your message (and location, if you allow) ready. You press send; Muse can't confirm delivery." },
  { feature: "Share location once", status: "works", detail: "Uses your browser's location only when you tap, and only in a message you send." },
  { feature: "Check-in reminders", status: "works", detail: "Alerts while Muse is open; a missed check-in prompts you to message someone." },
  { feature: "Emergency information card", status: "works", detail: "Stored on this device; print it or save it to your phone." },
  { feature: "Automatic alert when a check-in is missed", status: "server", detail: "Needs a secure server with verified SMS delivery and failure handling." },
  { feature: "Live location sharing", status: "server", detail: "Needs an encrypted, time-limited sharing service." },
  { feature: "Alerts when the app is closed or the phone is locked", status: "mobile", detail: "Needs the mobile app's operating-system notifications." },
  { feature: "Fall or crash detection", status: "mobile", detail: "Needs device sensors and the mobile app." },
];
