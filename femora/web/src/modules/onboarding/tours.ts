// Guided tours: each step points at a real element marked with data-tour="…". Only features that exist.
export interface TourStep { target: string; title: string; text: string }
export interface Tour { id: string; path: string; title: string; steps: TourStep[] }

export const TOURS: Tour[] = [
  { id: "home", path: "/app", title: "Your home", steps: [
    { target: "nav", title: "Everything in one place", text: "Every part of Muse is here. Items marked 'Coming' are still being built." },
    { target: "home-hero", title: "Muse greets you", text: "Muse suggests next steps from what you've recorded, never from guesses." },
    { target: "bell", title: "Notifications", text: "Reminders and updates arrive here. Snooze, dismiss, or tell Muse what's useful." },
    { target: "theme", title: "Make it yours", text: "Choose Onyx & Champagne, Emerald & Ivory or Midnight & Pearl, in light or dark." } ] },
  { id: "copilot", path: "/app/copilot", title: "Talking to Muse", steps: [
    { target: "modes", title: "Conversation modes", text: "Switch between talking, menopause guidance, food, emotional support and more, mid-conversation." },
    { target: "composer", title: "Say anything", text: "Write as much as you like, or use the microphone. Press Enter to send." },
    { target: "brief", title: "Brief answers", text: "Tick this when you want short, precise replies." } ] },
  { id: "food", path: "/app/food", title: "Logging food", steps: [
    { target: "food-describe", title: "Log in a sentence", text: "Type something like '2 idli and sambar for breakfast'. Muse matches it to dishes from 10 world regions." },
    { target: "food-scan", title: "Photo-assisted logging", text: "Take a photo for your record and choose the dish." },
    { target: "food-glance", title: "Sugar percentage", text: "See where your energy came from and how much was added sugar, against WHO guidance." } ] },
  { id: "journey", path: "/app/journey", title: "Your menopause journey", steps: [
    { target: "journey-calendar", title: "Cycle calendar", text: "Periods and symptom days appear here." },
    { target: "journey-forecast", title: "Forecasts", text: "Your next-period estimate from your own cycles, and your age in context from national data." },
    { target: "journey-summary", title: "Doctor-ready summary", text: "Download a clear summary to take to your appointment." } ] },
  { id: "planner", path: "/app/reminders", title: "Health planner", steps: [
    { target: "planner-today", title: "Today's doses", text: "Mark each dose taken, skipped or snoozed. Reminders follow exactly what you enter." },
    { target: "planner-checkups", title: "Check-ups", text: "Add appointments and the questions you want to ask. Muse reminds you before the day." } ] },
  { id: "body", path: "/app/body", title: "Health dashboard", steps: [
    { target: "body-tiles", title: "Your measures", text: "Pick any measure, from sleep and steps to blood pressure, joints and mood." },
    { target: "body-chart", title: "Trends & comparisons", text: "Change the date range or compare two measures. Patterns, not diagnoses." } ] },
  { id: "guardian", path: "/app/guardian", title: "Guardian safety", steps: [
    { target: "guardian-emergency", title: "Always one tap away", text: "Call emergency services or open an SOS message to your trusted people. You press send." },
    { target: "guardian-checkins", title: "Check-ins", text: "Schedule check-ins after walks or before bed." } ] },
  { id: "sisterhood", path: "/app/sisterhood", title: "Global sisterhood", steps: [
    { target: "sisterhood-search", title: "Search the world", text: "Find menopause societies and support groups by country, language or topic." },
    { target: "sisterhood-map", title: "Map or list", text: "Explore on the map, or switch to the list view. Both show the same verified organisations." } ] },
];
export const tourById = (id: string) => TOURS.find((t) => t.id === id);

// Tiny external store for the active tour.
type State = { tour: Tour | null; step: number };
let state: State = { tour: null, step: 0 };
const subs = new Set<() => void>();
const emit = () => subs.forEach((f) => f());
export const tourStore = {
  get: () => state,
  subscribe: (f: () => void) => { subs.add(f); return () => subs.delete(f); },
  start: (id: string) => { const t = tourById(id); if (t) { state = { tour: t, step: 0 }; emit(); } },
  next: () => { if (!state.tour) return; state = state.step + 1 < state.tour.steps.length ? { ...state, step: state.step + 1 } : { tour: null, step: 0 }; emit(); },
  back: () => { if (state.step > 0) { state = { ...state, step: state.step - 1 }; emit(); } },
  stop: () => { state = { tour: null, step: 0 }; emit(); },
};
