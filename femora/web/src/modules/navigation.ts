// Single source of truth for navigation. Adding a module = one entry here + one route. Status is shown in the UI.
import { Home, MessageCircleHeart, Salad, CalendarHeart, Activity, Globe2, Stethoscope, ShieldCheck, Smile, Settings, Gift, BellRing, ScanLine, Link2 } from "lucide-react";
import type { Status } from "../components/ui";

export interface NavItem { path: string; label: string; icon: typeof Home; status: Status; milestone?: number; summary: string }

export const NAV: NavItem[] = [
  { path: "/app", label: "Home", icon: Home, status: "demonstrated", summary: "Your day at a glance" },
  { path: "/app/copilot", label: "Talk to FEMORA", icon: MessageCircleHeart, status: "simulated", milestone: 2, summary: "Conversational companion with 8 modes, history, memory and safety rules" },
  { path: "/app/food", label: "Food & nutrition", icon: Salad, status: "demonstrated", milestone: 4, summary: "Global food logging with deterministic nutrient estimates" },
  { path: "/app/medscan", label: "MedScan", icon: ScanLine, status: "simulated", summary: "Home sample collection with results in 2–3 days, lab-report explanations and a quick symptom check" },
  { path: "/app/reminders", label: "Reminders", icon: BellRing, status: "demonstrated", summary: "Medication doses and health check-ups, with notifications" },
  { path: "/app/free-care", label: "Free care & events", icon: Gift, status: "simulated", summary: "Free check-ups, sample collection, yoga & spiritual zones, communities, goodies and deals near you" },
  { path: "/app/joy", label: "My Joy Map", icon: Smile, status: "demonstrated", milestone: 2, summary: "Record what brings you happiness and confidence" },
  { path: "/app/journey", label: "Menopause journey", icon: CalendarHeart, status: "planned", milestone: 3, summary: "Menstrual and ovulation tracking, STRAW+10 stage education, symptom severity and impact" },
  { path: "/app/body", label: "Body, movement & mind", icon: Activity, status: "planned", milestone: 5, summary: "Walking, sleep, hip and joint pain, hair, skin, nails, brain fog and mood" },
  { path: "/app/sisterhood", label: "Global sisterhood", icon: Globe2, status: "planned", milestone: 6, summary: "Interactive MapLibre world map of support organisations, events and circles" },
  { path: "/app/care", label: "Healthcare", icon: Stethoscope, status: "planned", milestone: 7, summary: "Clinician discovery, appointments, questions and downloadable summaries" },
  { path: "/app/guardian", label: "Guardian safety", icon: ShieldCheck, status: "planned", milestone: 7, summary: "Trusted contacts, check-ins and a clearly simulated SOS workflow" },
  { path: "/app/connections", label: "Connections", icon: Link2, status: "demonstrated", summary: "Contacts, WhatsApp, email, text and calendar, with you in control" },
  { path: "/app/settings", label: "Profile & privacy", icon: Settings, status: "demonstrated", summary: "Demo profile, theme, memory consent and reset" },
];
