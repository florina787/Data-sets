// Help centre articles. Each points to a real feature, and many can launch a guided tour.
export interface Article { id: string; title: string; tags: string[]; steps: string[]; tour?: string; video?: string }

export const ARTICLES: Article[] = [
  { id: "talk", title: "How do I talk to Muse?", tags: ["chat", "conversation", "talk", "modes", "voice", "brief"], tour: "copilot", video: "chat",
    steps: ["Open Talk to Muse.", "Type anything and press Enter, or tap the microphone.", "Switch modes at the top, such as Emotional support or Food companion.", "Tick 'Brief answers' for short replies."] },
  { id: "log-food", title: "How do I log a meal?", tags: ["food", "meal", "log", "eat", "nutrition", "sugar", "scan", "photo"], tour: "food", video: "food",
    steps: ["Open Food & nutrition.", "Describe what you ate in a sentence, then press Log.", "Or tap Scan to take a photo and choose the dish.", "Edit servings in the meal list; the charts update instantly."] },
  { id: "sugar", title: "What is the sugar percentage?", tags: ["sugar", "percentage", "who"],
    steps: ["It's the share of calories that came from added sugar.", "WHO advises under 10%, ideally under 5%.", "It is not a blood-sugar measurement."] },
  { id: "reminders", title: "How do I set a medication reminder?", tags: ["medication", "medicine", "reminder", "pill", "dose", "supplement", "refill"], tour: "planner", video: "planner",
    steps: ["Open Health planner.", "Enter the name, prescribed dose, frequency and reminder times (for example 08:00, 20:00).", "Press Add. When a dose is due, mark it Taken, Skipped or Snoozed.", "Allow browser alerts in Profile & privacy → Notifications."] },
  { id: "checkup", title: "How do I add a check-up or appointment?", tags: ["appointment", "checkup", "check-up", "screening", "doctor", "questions"], tour: "planner",
    steps: ["Open Health planner.", "Choose the type and date, then Add check-up.", "Add questions for your clinician under the appointment.", "Muse reminds you as the date approaches."] },
  { id: "period", title: "How do I log my period or symptoms?", tags: ["period", "cycle", "symptom", "hot flash", "menopause", "journey", "forecast"], tour: "journey",
    steps: ["Open Menopause journey.", "Log the first day of each period, and the last day if you like.", "Log symptoms with severity and how they affected your day.", "After a few cycles, Muse shows patterns and a next-period estimate."] },
  { id: "dashboard", title: "How do I track blood pressure, sleep or steps?", tags: ["blood pressure", "sleep", "steps", "weight", "glucose", "dashboard", "body", "mood"], tour: "body",
    steps: ["Open Body, movement & mind.", "Choose a measure, enter the value and press Save.", "Change the date range or compare two measures on the chart.", "Export everything as a spreadsheet anytime."] },
  { id: "sos", title: "How do I use Guardian in an emergency?", tags: ["sos", "emergency", "safety", "guardian", "unsafe", "check-in", "contact"], tour: "guardian",
    steps: ["Open Guardian. The red panel is always at the top.", "Tap Call to dial your local emergency number.", "Tap SOS to my people to open a ready message to trusted contacts; you press send.", "Muse can't confirm delivery, so call if it's urgent."] },
  { id: "map", title: "How do I find support groups near me?", tags: ["community", "support", "group", "map", "sisterhood", "society"], tour: "sisterhood",
    steps: ["Open Global sisterhood.", "Search by name, country or language, or type a city in 'Go to a city'.", "Select an organisation to see details and visit its official site."] },
  { id: "privacy", title: "Where is my data stored, and how do I delete it?", tags: ["privacy", "data", "delete", "export", "memory"],
    steps: ["Everything stays in this browser on this device.", "Profile & privacy → Your data lets you export or delete everything.", "Muse only remembers facts you approve; review them under Memory."] },
  { id: "themes", title: "How do I change the look?", tags: ["theme", "dark", "colour", "color", "design"], tour: "home", video: "themes",
    steps: ["Use the theme menu at the top: Onyx & Champagne, Emerald & Ivory or Midnight & Pearl.", "The moon icon switches light and dark."] },
  { id: "model", title: "How do I connect my own AI model?", tags: ["llama", "model", "ai", "offline"],
    steps: ["Run a llama.cpp server on your computer (llama-server -m model.gguf --port 8080).", "Profile & privacy → Muse model → Test connection.", "Enable it once the test succeeds. Muse falls back to offline mode if it stops."] },
];

const words = (s: string) => s.toLowerCase().split(/[^a-z0-9-]+/).filter((w) => w.length > 2);
const STOP = new Set(["how", "the", "and", "can", "what", "where", "use", "with", "for", "you", "your", "does", "set"]);

/** Simple keyword ranking for search and "Ask Muse how to". */
export function searchHelp(q: string) {
  const qw = words(q).filter((w) => !STOP.has(w));
  if (!qw.length) return ARTICLES;
  return ARTICLES.map((a) => {
    const hay = (a.title + " " + a.tags.join(" ")).toLowerCase();
    const score = qw.reduce((s, w) => s + (a.tags.some((t) => t.includes(w)) ? 3 : 0) + (hay.includes(w) ? 1 : 0), 0);
    return { a, score };
  }).filter((x) => x.score > 0).sort((x, y) => y.score - x.score).map((x) => x.a);
}
