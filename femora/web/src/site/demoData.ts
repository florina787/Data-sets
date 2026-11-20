// SYNTHETIC demo data for the interactive demo. Fictional values, stored only in the separate
// "femora:demo:" namespace of this browser. It never touches a visitor's real records.
import { DEMO_PREFIX, clearNamespace, setDemoMode } from "../lib/storage";

const dk = (o: number) => { const d = new Date(); d.setDate(d.getDate() + o); return d.toISOString().slice(0, 10); };
const ts = (o: number) => Date.now() + o * 864e5;
const hm = (o: number) => new Date(Date.now() + o * 60000).toTimeString().slice(0, 5);

export function demoData(): Record<string, unknown> {
  const body: Record<string, unknown>[] = [];
  for (let i = 0; i < 28; i++) {
    body.push({ id: "sl" + i, metric: "sleep", date: dk(-27 + i), value: +(6 + Math.sin(i / 2.3) * 0.9 + i * 0.02).toFixed(1) });
    body.push({ id: "mo" + i, metric: "mood", date: dk(-27 + i), value: Math.max(1, Math.min(5, Math.round(3.4 + Math.sin(i / 2.3) * 1.2))) });
    body.push({ id: "st" + i, metric: "steps", date: dk(-27 + i), value: 5200 + Math.round(Math.sin(i / 1.7) * 1800 + i * 60) });
    if (i % 4 === 0) body.push({ id: "bp" + i, metric: "bp", date: dk(-27 + i), value: 126 + (i % 3), value2: 80 + (i % 2) });
  }
  const meals: [string, string, number][] = [["eggs", "Breakfast", -6], ["coffee", "Breakfast", -6], ["chicken-salad", "Lunch", -6], ["tofu", "Dinner", -6], ["oats", "Breakfast", -5], ["dal", "Lunch", -5], ["roti", "Lunch", -5], ["salmon-rice", "Dinner", -5],
    ["greek-yogurt", "Breakfast", -4], ["tacos", "Lunch", -4], ["miso", "Dinner", -4], ["edamame", "Dinner", -4], ["idli", "Breakfast", -3], ["sambar", "Breakfast", -3], ["beans-rice", "Lunch", -3], ["sardines", "Dinner", -3],
    ["milk", "Breakfast", -2], ["hummus", "Lunch", -2], ["shakshuka", "Dinner", -2], ["eggs", "Breakfast", -1], ["lentil-soup", "Lunch", -1], ["tofu", "Dinner", -1], ["oats", "Breakfast", 0], ["coffee", "Breakfast", 0]];
  const symptoms: [string, number, number][] = [["Hot flash", -1, 2], ["Night sweats", -2, 2], ["Hot flash", -3, 3], ["Sleep disruption", -5, 2], ["Hot flash", -8, 2], ["Mood changes", -10, 1], ["Brain fog", -12, 2], ["Hot flash", -15, 1], ["Night sweats", -17, 2], ["Joint pain", -20, 1], ["Hot flash", -24, 2], ["Sleep disruption", -27, 3]];
  return {
    onboarded: true,
    profile: "bea",
    locations: { bea: { region: "North America", city: "Nashville" } },
    profileEdits: { bea: { name: "Demo Bea", age: 48, interests: ["Preventive health", "Food & cooking", "Yoga", "Mental wellbeing"], cuisine: ["North America", "South Asia", "East Asia"] } },
    "food:bea": meals.map(([f, m, o], i) => ({ id: "f" + i, foodId: f, meal: m, portion: 1, date: dk(o) })),
    "periods:bea": [-142, -112, -84, -49, -18].map((o, i) => ({ id: "p" + i, start: dk(o), end: dk(o + 4), flow: i % 2 ? "medium" : "heavy" })),
    symptoms: symptoms.map(([n, o, s], i) => ({ id: "s" + i, profileId: "bea", name: n, severity: s, at: ts(o), source: "form" })),
    "body:bea": body,
    "meds2:bea": [{ id: "m1", profileId: "bea", name: "Vitamin D", dose: "1000 IU", frequency: "Once daily", times: [hm(-30)], log: {} }, { id: "m2", profileId: "bea", name: "Magnesium", dose: "200 mg", frequency: "Once daily", times: ["21:30"], log: {} }],
    "checkups2:bea": [{ id: "c1", profileId: "bea", kind: "Cervical screening", next: dk(3), questions: ["Which test do you recommend for me: HPV or Pap?", "When should I be screened next?"] }],
    "contacts:bea": [{ id: "k1", name: "Demo friend", phone: "+1 555 0100", role: "Friend" }], "guardians:bea": ["k1"],
    "checkins:bea": [{ id: "ci1", label: "After evening walk", time: "20:30", days: [0, 1, 2, 3, 4, 5, 6], graceMin: 30, enabled: true }],
  };
}

/** Start (or restart) the demo: fresh synthetic data in the demo namespace only. */
export function startDemo() {
  clearNamespace(DEMO_PREFIX);
  for (const [k, v] of Object.entries(demoData())) localStorage.setItem(DEMO_PREFIX + k, JSON.stringify(v));
  setDemoMode(true);
}
export function exitDemo() { clearNamespace(DEMO_PREFIX); setDemoMode(false); }
