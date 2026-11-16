// ENTIRELY FICTIONAL demonstration profiles. Not real people, not real health data.
export type Stage = "premenopause" | "perimenopause-early" | "perimenopause-late" | "menopause" | "postmenopause" | "surgical";

export interface Profile {
  id: string;
  name: string;
  age: number;
  country: string;
  city: string;
  language: string;
  stage: Stage;
  cuisine: string[];          // preferred cuisine regions (matches food database `region`)
  diet: string;
  livesAlone: boolean;
  concerns: string[];
  story: string;
}

export const STAGE_LABEL: Record<Stage, string> = {
  premenopause: "Premenopause (planning ahead)",
  "perimenopause-early": "Early menopausal transition",
  "perimenopause-late": "Late menopausal transition",
  menopause: "Around final period (≤12 months)",
  postmenopause: "Postmenopause",
  surgical: "Surgical menopause",
};

// Named after FEMORA's CEO (Bea) and partner (Nancy) at the creator's request. Their HEALTH DETAILS below are
// invented demonstration data and do not describe the real people.
export const PROFILES: Profile[] = [
  { id: "bea", name: "Bea", age: 37, country: "United States", city: "", language: "English", stage: "premenopause",
    cuisine: ["North America", "Latin America", "East Asia"], diet: "Flexitarian", livesAlone: true,
    concerns: ["Understanding what's ahead", "Sleep on busy weeks", "Stress and energy"],
    story: "CEO building a fast-growing company. Cycles are regular; she's tracking now so she'll recognise changes early and wants to stay energised and connected. (Fictional demo data.)" },
  { id: "nancy", name: "Nancy", age: 56, country: "United States", city: "Nashville", language: "English", stage: "postmenopause",
    cuisine: ["North America", "Latin America", "East Asia", "West Africa"], diet: "Omnivore", livesAlone: false,
    concerns: ["Bone health", "Hip and joint stiffness", "Brain fog"],
    story: "Business partner and keen walker who wants to stay strong and sharp for the decades ahead. Last period was 4 years ago. (Fictional demo data.)" },
];

export const DEFAULT_PROFILE = "bea";
