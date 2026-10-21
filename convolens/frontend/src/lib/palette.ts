// Consistent categorical colours. Colour is always paired with a text label, legend and table.
export const TOPIC_COLORS: Record<string, string> = {
  billing_refunds: "#087F8C",
  orders_delivery: "#2F4B7C",
  account_access: "#A96308",
  app_technical: "#7A4E8C",
  network_connectivity: "#4F7CAC",
  travel_disruption: "#6B7F2A",
  cancellation: "#A0522D",
  service_experience: "#9C4A6B",
  other: "#5F6B7A",
  unknown: "#AEB8C4",
};
export const RESOLUTION_COLORS: Record<string, string> = {
  resolved_confirmed: "#24734B",
  solution_offered_unconfirmed: "#A96308",
  unresolved_explicit: "#B83D45",
  unknown: "#AEB8C4",
};
export const SENTIMENT_COLORS: Record<string, string> = { positive: "#24734B", neutral: "#5F6B7A", negative: "#B83D45", unknown: "#AEB8C4" };
export const RESOLUTION_LABELS: Record<string, string> = {
  resolved_confirmed: "Customer-confirmed resolved",
  unresolved_explicit: "Explicitly unresolved",
  solution_offered_unconfirmed: "Solution offered, outcome unconfirmed",
  unknown: "Unknown",
};
export const TOPIC_LABELS: Record<string, string> = {
  billing_refunds: "Billing & refunds", orders_delivery: "Orders & delivery", account_access: "Account access",
  app_technical: "App & website issues", network_connectivity: "Network & connectivity", travel_disruption: "Travel disruption",
  cancellation: "Cancellation & retention", service_experience: "Service experience", other: "Other", unknown: "Unknown",
};
export const SENTIMENT_LABELS: Record<string, string> = { negative: "Negative", neutral: "Neutral", positive: "Positive", unknown: "Unknown" };
export const ESCALATION_LABELS: Record<string, string> = { yes: "Escalation requested", no: "No escalation request", unknown: "Unknown" };
export const colorFor = (k: string) => TOPIC_COLORS[k] ?? RESOLUTION_COLORS[k] ?? SENTIMENT_COLORS[k] ?? "#5F6B7A";
export const HANDOFF_LABELS: Record<string, string> = {
  confirmed: "Moved to private channel (customer confirmed)",
  requested: "Support asked to move to private channel",
  none: "Stayed in public thread",
  unknown: "Unknown",
};
