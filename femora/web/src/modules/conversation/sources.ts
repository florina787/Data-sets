// Health-information sources cited by the demo copilot. Kept short on purpose: every item must be a real,
// retrievable source. Each will be re-verified and graded in the research workstream (docs/AUDIT.md §14).
export interface Source { id: string; title: string; publisher: string; year: number; url: string }

export const SOURCES: Source[] = [
  { id: "S1", title: "Menopause: fact sheet", publisher: "World Health Organization", year: 2024, url: "https://www.who.int/news-room/fact-sheets/detail/menopause" },
  { id: "S2", title: "Executive summary of the Stages of Reproductive Aging Workshop +10 (STRAW+10)", publisher: "Harlow SD et al., J Clin Endocrinol Metab", year: 2012, url: "https://doi.org/10.1210/jc.2011-3362" },
  { id: "S3", title: "Menopause: identification and management (NG23)", publisher: "NICE", year: 2024, url: "https://www.nice.org.uk/guidance/ng23" },
];

export const sourceById = (id: string) => SOURCES.find((s) => s.id === id);
