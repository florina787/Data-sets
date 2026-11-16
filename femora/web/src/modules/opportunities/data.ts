// Women's Health Opportunities: a VERIFIED registry. Nothing here is invented.
// - OFFICIAL_RESOURCES: official programme/information pages, each checked (HTTP 200) on the date recorded.
// - Events come only from a verified feed (public/data/opportunities.json, maintained via PR with provenance)
//   or are saved by the user herself (labelled "Added by you").
export type Category = "Screening campaign" | "Free/subsidised consultation" | "Health education" | "Yoga" | "Spiritual & mindfulness" | "Community" | "Free class or activity" | "Discount";
export const CATEGORIES: Category[] = ["Screening campaign", "Free/subsidised consultation", "Health education", "Yoga", "Spiritual & mindfulness", "Community", "Free class or activity", "Discount"];
export const COMMERCIAL: Category[] = ["Discount"];

export interface Opportunity {
  id: string; organization: string; title: string; category: Category;
  country: string; city: string; venue: string; online: boolean;
  start: string; end?: string; eligibility: string;
  cost: "free" | "subsidised" | "paid" | "discount" | "unknown"; registration: string; url: string;
  verifiedAt?: string; provenance: "verified-feed" | "user-added";
  spiritualTags?: ("spiritual" | "religious" | "secular" | "mindfulness" | "yoga" | "nature")[];
  accessibility?: string;
}

export interface OfficialResource { organization: string; title: string; topic: string; country: string; city?: string; url: string; verifiedAt: string; kind: "guideline" | "programme" | "information" | "local health department" | "crisis support" }

const V = "2026-11-16"; // automated HTTP 200 check + manual review
export const OFFICIAL_RESOURCES: OfficialResource[] = [
  { organization: "World Health Organization", title: "Cervical cancer elimination initiative", topic: "Cervical health", country: "Global", url: "https://www.who.int/initiatives/cervical-cancer-elimination-initiative", verifiedAt: V, kind: "programme" },
  { organization: "U.S. Preventive Services Task Force", title: "Cervical cancer screening recommendation", topic: "Cervical health", country: "United States", url: "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/cervical-cancer-screening", verifiedAt: V, kind: "guideline" },
  { organization: "NHS", title: "Cervical screening", topic: "Cervical health", country: "United Kingdom", url: "https://www.nhs.uk/conditions/cervical-screening/", verifiedAt: V, kind: "programme" },
  { organization: "World Health Organization", title: "Breast cancer fact sheet", topic: "Breast health", country: "Global", url: "https://www.who.int/news-room/fact-sheets/detail/breast-cancer", verifiedAt: V, kind: "information" },
  { organization: "World Health Organization", title: "Menopause fact sheet", topic: "Menopause", country: "Global", url: "https://www.who.int/news-room/fact-sheets/detail/menopause", verifiedAt: V, kind: "information" },
  { organization: "NICE", title: "Menopause: identification and management (NG23)", topic: "Menopause", country: "United Kingdom", url: "https://www.nice.org.uk/guidance/ng23", verifiedAt: V, kind: "guideline" },
  { organization: "Metro Nashville Public Health Department", title: "Public health services and clinics", topic: "Local health services", country: "United States", city: "Nashville", url: "https://www.nashville.gov/departments/health", verifiedAt: V, kind: "local health department" },
  { organization: "Find A Helpline", title: "Free, confidential crisis lines worldwide", topic: "Emotional support", country: "Global", url: "https://www.findahelpline.com", verifiedAt: V, kind: "crisis support" },
];

export function resourcesFor(country: string, city?: string) {
  return OFFICIAL_RESOURCES.filter((r) => r.country === "Global" || r.country === country).sort((a, b) =>
    Number(!!b.city && b.city === city) - Number(!!a.city && a.city === city) || Number(b.country === country) - Number(a.country === country));
}

/** Load verified events. A feed item without a URL and verification date is rejected. */
export async function loadVerifiedFeed(base = import.meta.env.BASE_URL): Promise<Opportunity[]> {
  try {
    const r = await fetch(`${base}data/opportunities.json`, { cache: "no-store" });
    const j = (await r.json()) as { items: Opportunity[] };
    return validFeed(j.items);
  } catch { return []; }
}
export const validFeed = (items: Opportunity[]) => items.filter((o) => o.url?.startsWith("https://") && !!o.verifiedAt && o.provenance === "verified-feed");

export function filterFor(items: Opportunity[], opts: { city?: string; country?: string; category?: Category | "All"; commercial: boolean; online?: "all" | "online" | "in-person" }) {
  return items.filter((o) => (opts.commercial || !COMMERCIAL.includes(o.category))
    && (!opts.category || opts.category === "All" || o.category === opts.category)
    && (opts.online === undefined || opts.online === "all" || (opts.online === "online") === o.online)
    && (o.online || !opts.city || o.city.toLowerCase() === opts.city.toLowerCase() || o.provenance === "user-added"))
    .sort((a, b) => a.start.localeCompare(b.start));
}

/** Calendar file so she can save an event to any calendar app (only on her action). */
export function toICS(o: Opportunity): string {
  const d = o.start.replace(/[-:]/g, "").replace(/\.\d+Z?$/, "");
  const esc = (x: string) => x.replace(/[,;\\]/g, (m) => `\\${m}`).replace(/\n/g, "\\n");
  return ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FEMORA Muse//EN", "BEGIN:VEVENT", `UID:${o.id}@femora`, `DTSTAMP:${d.length === 8 ? d + "T000000" : d}`,
    `DTSTART:${d.length === 8 ? d : d}`, `SUMMARY:${esc(o.title)}`, `LOCATION:${esc(o.online ? "Online" : `${o.venue}, ${o.city}`)}`,
    `DESCRIPTION:${esc(`${o.organization}. ${o.registration} ${o.url}`)}`, "END:VEVENT", "END:VCALENDAR"].join("\r\n");
}

/** Gentle, non-factual encouragements, shown only if she opts into "Joy & encouragement". */
export const ENCOURAGEMENTS = [
  "Small steps count: a glass of water, a short walk, a kind word to yourself.",
  "You're allowed to rest. Rest is part of looking after yourself.",
  "Whatever today holds, you've handled hard days before.",
  "Someone would love to hear from you today. Only if you feel like it.",
];
