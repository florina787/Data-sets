// Global Sisterhood registry. Every entry's official website was checked (HTTP 200 + page title matched the
// organisation) on the date recorded. Markers are placed at COUNTRY or CITY level only, never an address.
export type PlaceCategory = "Menopause society" | "Support & advocacy" | "Public health" | "Women's health society" | "Yoga & wellness" | "Online support";
export const PLACE_CATEGORIES: PlaceCategory[] = ["Menopause society", "Support & advocacy", "Public health", "Women's health society", "Yoga & wellness", "Online support"];

export interface Place {
  id: string; name: string; category: PlaceCategory; url: string; description: string;
  scope: "country" | "city" | "region" | "online";  // what the marker position represents
  area: string; country: string; lat?: number; lon?: number;  // no coordinates = online, list only
  languages: string[]; free: "free" | "membership" | "mixed"; verifiedAt: string;
}

const V = "2026-11-17";
// Approximate geographic centres for country/region markers (not organisation addresses).
const C = { US: [39.8, -98.6], UK: [54.0, -2.5], AU: [-25.3, 133.8], EU: [50.1, 9.7], IN: [22.0, 79.0], CA: [56.1, -106.3], JP: [36.2, 138.3], NASH: [36.163, -86.781] } as const;

export const PLACES: Place[] = [
  { id: "menopause-society", name: "The Menopause Society", category: "Menopause society", url: "https://www.menopause.org", description: "North American society for menopause science and care; includes a practitioner finder and patient information.", scope: "country", area: "United States", country: "United States", lat: C.US[0], lon: C.US[1], languages: ["English"], free: "mixed", verifiedAt: V },
  { id: "lets-talk-menopause", name: "Let's Talk Menopause", category: "Support & advocacy", url: "https://www.letstalkmenopause.org", description: "Nonprofit offering symptom education and advocacy.", scope: "country", area: "United States", country: "United States", lat: C.US[0] - 2, lon: C.US[1] + 4, languages: ["English"], free: "free", verifiedAt: V },
  { id: "oash", name: "Office on Women's Health (OASH)", category: "Public health", url: "https://www.womenshealth.gov", description: "U.S. Department of Health and Human Services information on women's health, including menopause.", scope: "country", area: "United States", country: "United States", lat: C.US[0] + 2, lon: C.US[1] - 4, languages: ["English", "Spanish"], free: "free", verifiedAt: V },
  { id: "nashville-health", name: "Metro Nashville Public Health Department", category: "Public health", url: "https://www.nashville.gov/departments/health", description: "Local public-health services and clinics in Nashville.", scope: "city", area: "Nashville, Tennessee", country: "United States", lat: C.NASH[0], lon: C.NASH[1], languages: ["English"], free: "mixed", verifiedAt: V },
  { id: "yoga-alliance", name: "Yoga Alliance", category: "Yoga & wellness", url: "https://www.yogaalliance.org", description: "Directory of registered yoga teachers and schools; use it to find classes near you.", scope: "country", area: "United States (global directory)", country: "United States", lat: C.US[0] - 4, lon: C.US[1] - 6, languages: ["English"], free: "mixed", verifiedAt: V },
  { id: "bms", name: "British Menopause Society", category: "Menopause society", url: "https://thebms.org.uk", description: "UK specialist society; lists menopause specialists and resources.", scope: "country", area: "United Kingdom", country: "United Kingdom", lat: C.UK[0], lon: C.UK[1], languages: ["English"], free: "mixed", verifiedAt: V },
  { id: "whc", name: "Women's Health Concern", category: "Support & advocacy", url: "https://www.womens-health-concern.org", description: "Confidential advice, reassurance and education for women (patient arm of the BMS).", scope: "country", area: "United Kingdom", country: "United Kingdom", lat: C.UK[0] - 1.2, lon: C.UK[1] + 1.2, languages: ["English"], free: "free", verifiedAt: V },
  { id: "menopausesupport", name: "menopausesupport.co.uk", category: "Support & advocacy", url: "https://menopausesupport.co.uk", description: "Community organisation supporting people through menopause.", scope: "country", area: "United Kingdom", country: "United Kingdom", lat: C.UK[0] + 1.3, lon: C.UK[1] - 1, languages: ["English"], free: "mixed", verifiedAt: V },
  { id: "emas", name: "European Menopause and Andropause Society", category: "Menopause society", url: "https://emas-online.org", description: "European society for midlife health research and education.", scope: "region", area: "Europe", country: "Europe", lat: C.EU[0], lon: C.EU[1], languages: ["English"], free: "mixed", verifiedAt: V },
  { id: "ams", name: "Australasian Menopause Society", category: "Menopause society", url: "https://www.menopause.org.au", description: "Menopause information, fact sheets and a doctor finder for Australia and New Zealand.", scope: "country", area: "Australia & New Zealand", country: "Australia", lat: C.AU[0], lon: C.AU[1], languages: ["English"], free: "mixed", verifiedAt: V },
  { id: "ims-india", name: "Indian Menopause Society", category: "Menopause society", url: "https://indianmenopausesociety.org", description: "National society for menopause education and care in India.", scope: "country", area: "India", country: "India", lat: C.IN[0], lon: C.IN[1], languages: ["English"], free: "mixed", verifiedAt: V },
  { id: "mfc", name: "The Menopause Foundation of Canada", category: "Support & advocacy", url: "https://menopausefoundationcanada.ca", description: "Canadian nonprofit for menopause awareness and workplace support.", scope: "country", area: "Canada", country: "Canada", lat: C.CA[0], lon: C.CA[1], languages: ["English", "French"], free: "free", verifiedAt: V },
  { id: "jsog", name: "Japan Society of Obstetrics and Gynecology", category: "Women's health society", url: "https://www.jsog.or.jp", description: "National professional society for women's health in Japan.", scope: "country", area: "Japan", country: "Japan", lat: C.JP[0], lon: C.JP[1], languages: ["Japanese"], free: "mixed", verifiedAt: V },
  { id: "who", name: "World Health Organization: menopause", category: "Online support", url: "https://www.who.int/news-room/fact-sheets/detail/menopause", description: "Global, evidence-based information about menopause.", scope: "online", area: "Online · global", country: "Global", languages: ["English", "French", "Spanish", "Arabic", "Chinese", "Russian"], free: "free", verifiedAt: V },
  { id: "helpline", name: "Find A Helpline", category: "Online support", url: "https://www.findahelpline.com", description: "Free, confidential emotional-support lines in many countries.", scope: "online", area: "Online · global", country: "Global", languages: ["Many"], free: "free", verifiedAt: V },
];

export function filterPlaces(places: Place[], q: string, cats: PlaceCategory[], freeOnly = false) {
  const s = q.trim().toLowerCase();
  return places.filter((p) => (!cats.length || cats.includes(p.category)) && (!freeOnly || p.free === "free")
    && (!s || [p.name, p.area, p.country, p.description, p.category, ...p.languages].join(" ").toLowerCase().includes(s)));
}

export function toGeoJSON(places: Place[]) {
  return { type: "FeatureCollection" as const, features: places.filter((p) => p.lat !== undefined && p.lon !== undefined).map((p) => ({
    type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [p.lon!, p.lat!] }, properties: { id: p.id, name: p.name, category: p.category } })) };
}

/** Optional city search via OpenStreetMap Nominatim, only when she presses Search. Sends only the typed text. */
export async function geocode(query: string, fetcher: typeof fetch = fetch): Promise<{ lat: number; lon: number; label: string } | null> {
  const r = await fetcher(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`, { headers: { Accept: "application/json" } });
  if (!r.ok) return null;
  const j = (await r.json()) as { lat: string; lon: string; display_name: string }[];
  return j[0] ? { lat: Number(j[0].lat), lon: Number(j[0].lon), label: j[0].display_name } : null;
}
