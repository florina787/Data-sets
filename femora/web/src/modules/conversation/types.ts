export type Mode = "talk" | "menopause" | "food" | "emotional" | "coach" | "doctor" | "sisterhood" | "journal";

export const MODES: { id: Mode; label: string; blurb: string }[] = [
  { id: "talk", label: "Talk with me", blurb: "Anything on your mind: life, people, plans" },
  { id: "menopause", label: "Menopause guide", blurb: "Stages, symptoms, what the evidence says" },
  { id: "food", label: "Food companion", blurb: "Questions about what you've logged and what to eat" },
  { id: "emotional", label: "Emotional support", blurb: "A calm space when things feel heavy" },
  { id: "coach", label: "Wellness coach", blurb: "Small, realistic steps for sleep, movement, energy" },
  { id: "doctor", label: "Doctor assistant", blurb: "Prepare questions and summaries for appointments" },
  { id: "sisterhood", label: "Sisterhood guide", blurb: "Find circles and communities" },
  { id: "journal", label: "Personal journal", blurb: "Write freely; nothing is analysed unless you ask" },
];

export type ActionKind = "log-symptom" | "open" | "joy";
export interface Action { kind: ActionKind; label: string; payload: string }

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  mode: Mode;
  at: number;
  sources?: string[];          // source ids, e.g. "S2"
  actions?: Action[];
  followUps?: string[];
  memory?: string;             // proposed memory; stored only after user approval
  safety?: "crisis" | "urgent-medical";
  provider?: string;
}

export interface Conversation { id: string; title: string; mode: Mode; messages: Message[]; archived: boolean; updatedAt: number }

export interface ReplyContext {
  text: string;
  mode: Mode;
  brief?: boolean;            // "precise" answers requested
  history: Message[];
  profile: { name: string; stage?: string; cuisine: string[]; diet?: string; livesAlone?: boolean };
  memory: string[];
  food: { weekProtein: number; weekDays: number; weekAlcoholDays: number; weekCaffeineAvg: number; todayCalcium: number; calciumTarget: number; proteinTarget: number };
}

export interface Reply { text: string; sources?: string[]; actions?: Action[]; followUps?: string[]; memory?: string; safety?: Message["safety"] }

/** Any model backend implements this. The UI never imports a concrete provider. */
export interface ChatProvider { id: string; label: string; live: boolean; respond(ctx: ReplyContext): Promise<Reply> }
