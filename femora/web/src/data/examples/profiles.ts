// Example profile configurations (not real accounts). Health details are never assumed: everything beyond the
// basics below is entered by the user, with consent.
export type Stage = "premenopause" | "perimenopause-early" | "perimenopause-late" | "menopause" | "postmenopause" | "surgical";

export interface Profile {
  id: string;
  name: string;
  age: number;
  country: string;
  city: string;
  language: string;
  stage?: Stage;              // only if the user chooses to record it
  cuisine: string[];          // preferred cuisine regions, chosen by the user
  diet?: string;
  livesAlone?: boolean;
  interests: string[];        // chosen by the user
  story?: string;
}

export const STAGE_LABEL: Record<Stage, string> = {
  premenopause: "Premenopause (planning ahead)",
  "perimenopause-early": "Early menopausal transition",
  "perimenopause-late": "Late menopausal transition",
  menopause: "Around final period (≤12 months)",
  postmenopause: "Postmenopause",
  surgical: "Surgical menopause",
};

export const PROFILES: Profile[] = [
  { id: "bea", name: "Bea", age: 37, country: "United States", city: "", language: "English", cuisine: [], interests: [] },
  { id: "nancy", name: "Nancy", age: 0, country: "United States", city: "Nashville", language: "English", cuisine: [], interests: [] },
];

export const INTEREST_OPTIONS = ["Preventive health", "Fitness", "Food & cooking", "Mental wellbeing", "Women's health education", "Menopause", "Yoga", "Walking", "Community", "Spiritual life", "Career", "Travel"];

export const DEFAULT_PROFILE = "bea";
