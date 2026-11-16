// Free care & events. Events are EXAMPLES generated for the user's city (clearly labelled); official programme
// links point to real public sources. Production: verified feeds from health services, NGOs and partners.
import { addDays, dayKey } from "../../lib/storage";

export type Category = "Health check-ups" | "Sample collection" | "Consultation" | "Yoga" | "Spiritual & mindfulness" | "Workshop" | "Community" | "Free goodies" | "Deals";
export const CATEGORIES: Category[] = ["Health check-ups", "Sample collection", "Consultation", "Yoga", "Spiritual & mindfulness", "Community", "Workshop", "Free goodies", "Deals"];

export interface Opportunity {
  id: string; category: Category; title: string; host: string; where: string; online: boolean;
  date: string; time: string; free: boolean; details: string; eligibility: string; example: true;
}

export interface OfficialProgramme { title: string; publisher: string; url: string; topic: string }

export const OFFICIAL: OfficialProgramme[] = [
  { topic: "Cervical health", title: "Cervical cancer elimination initiative", publisher: "World Health Organization", url: "https://www.who.int/initiatives/cervical-cancer-elimination-initiative" },
  { topic: "Cervical health", title: "Cervical screening: who is eligible and how it works", publisher: "NHS (UK)", url: "https://www.nhs.uk/conditions/cervical-screening/" },
  { topic: "Breast health", title: "Breast cancer: fact sheet", publisher: "World Health Organization", url: "https://www.who.int/news-room/fact-sheets/detail/breast-cancer" },
  { topic: "Menopause", title: "Menopause: fact sheet", publisher: "World Health Organization", url: "https://www.who.int/news-room/fact-sheets/detail/menopause" },
];

const T: [Category, string, string, string, boolean, string, string][] = [
  ["Health check-ups", "Free cervical screening day", "Community Health Centre", "Walk-in cervical screening (smear / HPV test) with female nurses available. Bring ID if you have it.", false, "Women and people with a cervix aged 25–64 (check local programme)", "09:00–16:00"],
  ["Health check-ups", "Breast health awareness & free clinical check", "Women's Wellness Clinic", "Talk with a nurse about breast changes and learn self-awareness. Referrals to mammography where eligible.", false, "Women 40+ or anyone with concerns", "10:00–14:00"],
  ["Health check-ups", "Free blood pressure & blood sugar checks", "Central Library", "Quick checks for heart and metabolic health, which matter more after menopause.", false, "Everyone", "11:00–15:00"],
  ["Health check-ups", "Free bone density (DEXA) screening day", "Osteoporosis Awareness Partners", "Bone density scans for women at higher risk of osteoporosis, with results explained by a nurse.", false, "Women 50+ or postmenopausal (check eligibility)", "09:00–13:00"],
  ["Health check-ups", "Free thyroid & women's wellness check", "Women's Wellness Clinic", "Short consultation plus a thyroid blood test referral. Thyroid symptoms can look like menopause.", false, "Women 35+", "10:00–15:00"],
  ["Sample collection", "Free at-home HPV self-sampling kit", "Cervical Health Campaign", "Order a free self-collection swab kit, take the sample privately at home and post it back. Results by text or letter.", true, "Women and people with a cervix 30–65 (check local programme)", "Order any time"],
  ["Sample collection", "Free blood-sample collection drive: cholesterol, HbA1c, vitamin D", "Mobile Health Van", "Finger-prick and blood samples collected by trained phlebotomists. Results sent privately within a week.", false, "Adults 35+", "08:00–12:00"],
  ["Sample collection", "Free bowel cancer screening kit pick-up", "Community Pharmacy", "Collect a free home stool test kit (FIT) with instructions. Return it by post.", false, "Adults 50+ (check local programme)", "09:00–18:00"],
  ["Consultation", "Free menopause clinic: ask a specialist", "Women's Health Network", "15-minute one-to-one video consultations with a menopause-trained clinician. Booking required.", true, "Women 40+", "18:00–20:00"],
  ["Consultation", "Free pelvic health physiotherapy session", "Physio Collective", "Advice for bladder leaks, pelvic floor and joint pain.", false, "Women of any age", "13:00–17:00"],
  ["Workshop", "Eating well through menopause (free cooking class)", "Community Kitchen", "Cook protein- and calcium-rich local dishes and take recipes home.", false, "Everyone", "17:30–19:30"],
  ["Workshop", "Sleep better: free online workshop", "Wellbeing Hub", "Practical strategies for night sweats and 3am waking.", true, "Everyone", "19:00–20:00"],
  ["Community", "Sisterhood walk & coffee", "FEMORA circle (example)", "A gentle 3 km walk followed by coffee. All paces welcome.", false, "Women of all ages", "08:00–09:30"],
  ["Community", "Free women's festival: health, music & market", "City Women's Network", "A free day of live music, health stalls, mini check-ups and local women-owned businesses.", false, "Everyone", "12:00–20:00"],
  ["Community", "Free women's mental wellbeing circle", "Women's Centre", "A facilitated peer-support group about stress, mood and midlife change.", false, "Women 35+", "18:30–20:00"],
  ["Free goodies", "Free menopause comfort kits", "Local pharmacy partners", "Cooling fan, lip balm, information leaflets and a symptom diary while stocks last.", false, "Women 40+", "All day"],
  ["Yoga", "Sunrise yoga zone in the park", "Parks & Recreation", "Free outdoor yoga for all levels. Mats provided. Gentle flow for joints and balance.", false, "Everyone", "07:00–08:00"],
  ["Yoga", "Menopause-friendly yoga & breathwork", "Yoga Studio Collective", "Cooling breath, restorative poses and pelvic-floor awareness. Free taster class.", false, "Women 35+", "18:00–19:00"],
  ["Yoga", "Chair yoga online", "Wellbeing Hub", "Seated yoga for stiff hips and knees, from home.", true, "Everyone", "11:00–11:45"],
  ["Spiritual & mindfulness", "Guided meditation & sound bath", "Peace Garden Centre", "A quiet hour of guided meditation and singing bowls. All beliefs welcome.", false, "Everyone", "19:30–20:30"],
  ["Spiritual & mindfulness", "Interfaith women's reflection circle", "Community Interfaith Centre", "Share, pray or simply listen in a respectful circle for women of all faiths and none.", false, "Women of all faiths and none", "17:00–18:30"],
  ["Spiritual & mindfulness", "Mindful nature walk & journaling", "Botanical Garden", "A slow walk with mindfulness prompts and a journaling pause. Free with entry.", false, "Everyone", "10:00–11:30"],
  ["Deals", "20% off cooling bedding & fans", "Local home store (example)", "Seasonal discount on breathable bedding, cooling pillows and quiet fans.", false, "Everyone", "This week"],
  ["Deals", "Half-price strength-training starter class", "Women's Gym (example)", "Discounted 4-week beginner strength course. Muscle and bone health matter after 40.", false, "Women 35+", "Starts next month"],
  ["Deals", "Buy-one-gift-one wellness journal", "Independent bookshop (example)", "Get a symptom & gratitude journal and gift one to a friend.", false, "Everyone", "While stocks last"],
  ["Free goodies", "Free skincare samples for menopausal skin", "Dermatology outreach (example)", "Fragrance-free moisturiser and SPF samples with a free 5-minute skin advice chat.", false, "Everyone", "11:00–17:00"],
  ["Free goodies", "Free period & incontinence products drive", "Women's Aid volunteers", "Free pads, liners and period products, no questions asked.", false, "Anyone who needs them", "10:00–18:00"],
];

/** Example opportunities for her city over the next few weeks. */
export function opportunitiesFor(city: string, today = new Date()): Opportunity[] {
  return T.map(([category, title, host, details, online, eligibility, time], i) => ({
    id: `op${i}`, category, title, host: online ? host : `${city} ${host}`, where: online ? "Online" : city, online,
    date: dayKey(addDays(today, 2 + ((i * 3) % 24))), time, free: category !== "Deals", details, eligibility, example: true as const,
  })).sort((a, b) => a.date.localeCompare(b.date));
}

/** Calendar file so she can save an event to any calendar app. */
export function toICS(o: Opportunity): string {
  const d = o.date.replace(/-/g, "");
  const [start, end] = o.time.includes("–") ? o.time.split("–").map((x) => x.replace(":", "") + "00") : ["090000", "170000"];
  const esc = (x: string) => x.replace(/[,;\\]/g, (m) => `\\${m}`).replace(/\n/g, "\\n");
  return ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FEMORA//Demo//EN", "BEGIN:VEVENT", `UID:${o.id}-${d}@femora.demo`, `DTSTAMP:${d}T000000`,
    `DTSTART:${d}T${start}`, `DTEND:${d}T${end}`, `SUMMARY:${esc(o.title)} (example)`, `LOCATION:${esc(o.where)}`,
    `DESCRIPTION:${esc(o.details + " Example event from the FEMORA demo.")}`, "END:VEVENT", "END:VCALENDAR"].join("\r\n");
}

/** Uplifting notes for the daily cheer-up card. Positive without minimising hard days. */
export const GOOD_NEWS = [
  "More workplaces are adopting menopause policies, and conversations that were once whispered are now happening out loud. 💜",
  "Research on women's midlife health is growing fast, and more clinicians are training in menopause care every year.",
  "Small wins count: a glass of water, a walk around the block, a kind word to yourself. You're doing better than you think.",
  "Walking with a friend is good for your heart and your mood. Twice the benefit, half the effort. 🚶‍♀️",
  "Strength training at any age builds muscle and supports bones. It's never too late to start.",
];
