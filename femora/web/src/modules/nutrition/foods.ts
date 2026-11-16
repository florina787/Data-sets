// Curated SAMPLE food database for the demo. Values are approximate per typical serving, compiled as rough
// estimates for demonstration; they are NOT authoritative nutrition data. Production will source from
// national food composition tables (e.g. USDA FoodData Central, IFCT India) with provenance per item.
export type Nutrient =
  | "kcal" | "protein" | "carbs" | "fiber" | "fat" | "satFat" | "addedSugar"
  | "calcium" | "iron" | "vitD" | "b12" | "sodium" | "caffeine" | "alcohol";

export type Nutrients = Record<Nutrient, number>;

export interface Food {
  id: string;
  name: string;
  aliases: string[];
  region: string;
  serving: string;
  emoji: string;
  n: Partial<Nutrients>;      // missing key = unknown (shown as "no data"), not zero
  plantEstrogen?: boolean;   // soy / flax / legumes with isoflavones or lignans
}

export const REGIONS = ["South Asia", "East Asia", "Southeast Asia", "West Africa", "East Africa", "Middle East", "Europe", "North America", "Latin America", "Universal"];

const f = (id: string, name: string, region: string, serving: string, emoji: string, n: Partial<Nutrients>, aliases: string[] = [], plantEstrogen = false): Food =>
  ({ id, name, region, serving, emoji, n, aliases, plantEstrogen });

export const FOODS: Food[] = [
  // South Asia
  f("idli", "Idli", "South Asia", "2 pieces", "🍚", { kcal: 120, protein: 4, carbs: 25, fiber: 1.5, fat: 0.5, satFat: 0.1, addedSugar: 0, calcium: 20, iron: 0.8, sodium: 250 }, ["idly"]),
  f("sambar", "Sambar", "South Asia", "1 bowl", "🍲", { kcal: 150, protein: 7, carbs: 22, fiber: 6, fat: 4, satFat: 0.6, addedSugar: 1, calcium: 60, iron: 2, sodium: 550 }, [], true),
  f("dal", "Dal (lentils)", "South Asia", "1 bowl", "🍛", { kcal: 200, protein: 12, carbs: 30, fiber: 8, fat: 4, satFat: 1, addedSugar: 0, calcium: 40, iron: 3, sodium: 450 }, ["daal", "lentil curry"], true),
  f("roti", "Whole-wheat roti", "South Asia", "2 pieces", "🫓", { kcal: 200, protein: 7, carbs: 36, fiber: 6, fat: 4, satFat: 0.8, addedSugar: 0, calcium: 30, iron: 2, sodium: 300 }, ["chapati"]),
  f("paneer", "Palak paneer", "South Asia", "1 bowl", "🥬", { kcal: 300, protein: 15, carbs: 10, fiber: 4, fat: 22, satFat: 11, addedSugar: 0, calcium: 380, iron: 2.5, vitD: 0.2, b12: 0.5, sodium: 600 }),
  f("curd", "Curd / dahi", "South Asia", "1 cup", "🥣", { kcal: 140, protein: 8, carbs: 11, fiber: 0, fat: 7, satFat: 4.5, addedSugar: 0, calcium: 280, iron: 0.1, vitD: 0.1, b12: 0.9, sodium: 100 }, ["yogurt", "dahi"]),
  f("chai", "Masala chai with milk & sugar", "South Asia", "1 cup", "🍵", { kcal: 110, protein: 3, carbs: 16, fiber: 0, fat: 3.5, satFat: 2, addedSugar: 10, calcium: 110, iron: 0.2, sodium: 40, caffeine: 40 }, ["tea", "chai"]),
  f("rajma", "Rajma chawal", "South Asia", "1 plate", "🍛", { kcal: 450, protein: 16, carbs: 78, fiber: 12, fat: 8, satFat: 1.5, addedSugar: 0, calcium: 80, iron: 4, sodium: 700 }, ["kidney beans"], true),
  // East Asia
  f("tofu", "Tofu stir-fry", "East Asia", "1 plate", "🥢", { kcal: 280, protein: 20, carbs: 14, fiber: 4, fat: 16, satFat: 2.5, addedSugar: 3, calcium: 450, iron: 3.5, sodium: 750 }, ["tofu"], true),
  f("miso", "Miso soup", "East Asia", "1 bowl", "🥣", { kcal: 60, protein: 4, carbs: 6, fiber: 1, fat: 2, satFat: 0.3, addedSugar: 0, calcium: 40, iron: 1, sodium: 900 }, [], true),
  f("congee", "Fish congee", "East Asia", "1 bowl", "🍥", { kcal: 250, protein: 15, carbs: 38, fiber: 1, fat: 4, satFat: 1, addedSugar: 0, calcium: 30, iron: 1, vitD: 2, b12: 1, sodium: 800 }, ["porridge"]),
  f("salmon-rice", "Grilled salmon & rice", "East Asia", "1 plate", "🍣", { kcal: 520, protein: 32, carbs: 55, fiber: 2, fat: 17, satFat: 3, addedSugar: 2, calcium: 30, iron: 1.2, vitD: 12, b12: 3.5, sodium: 600 }, ["salmon"]),
  f("edamame", "Edamame", "East Asia", "1 cup", "🫛", { kcal: 190, protein: 17, carbs: 14, fiber: 8, fat: 8, satFat: 1, addedSugar: 0, calcium: 100, iron: 3.5, sodium: 10 }, [], true),
  f("green-tea", "Green tea", "East Asia", "1 cup", "🍵", { kcal: 2, protein: 0, carbs: 0, fiber: 0, fat: 0, satFat: 0, addedSugar: 0, calcium: 0, iron: 0, sodium: 2, caffeine: 30 }),
  // Southeast Asia
  f("laksa", "Laksa", "Southeast Asia", "1 bowl", "🍜", { kcal: 600, protein: 22, carbs: 60, fiber: 4, fat: 30, satFat: 18, addedSugar: 4, calcium: 120, iron: 3, sodium: 1800 }),
  f("tempeh", "Tempeh sambal", "Southeast Asia", "1 serving", "🌶️", { kcal: 260, protein: 19, carbs: 12, fiber: 6, fat: 15, satFat: 3, addedSugar: 3, calcium: 110, iron: 2.5, sodium: 500 }, ["tempe"], true),
  f("gado", "Gado-gado", "Southeast Asia", "1 plate", "🥗", { kcal: 400, protein: 16, carbs: 30, fiber: 8, fat: 24, satFat: 4, addedSugar: 5, calcium: 180, iron: 3, sodium: 650 }, [], true),
  // West / East Africa
  f("jollof", "Jollof rice", "West Africa", "1 plate", "🍛", { kcal: 450, protein: 9, carbs: 75, fiber: 3, fat: 12, satFat: 2, addedSugar: 2, calcium: 40, iron: 2, sodium: 800 }),
  f("egusi", "Egusi soup with fish", "West Africa", "1 bowl", "🥘", { kcal: 420, protein: 24, carbs: 10, fiber: 4, fat: 32, satFat: 8, addedSugar: 0, calcium: 150, iron: 4, vitD: 3, b12: 2, sodium: 700 }),
  f("akara", "Akara (bean fritters)", "West Africa", "4 pieces", "🧆", { kcal: 300, protein: 12, carbs: 24, fiber: 6, fat: 18, satFat: 2.5, addedSugar: 0, calcium: 60, iron: 2.5, sodium: 350 }, [], true),
  f("injera", "Injera with shiro", "East Africa", "1 plate", "🫓", { kcal: 420, protein: 16, carbs: 70, fiber: 10, fat: 9, satFat: 1.5, addedSugar: 0, calcium: 120, iron: 6, sodium: 600 }, ["shiro"], true),
  // Middle East
  f("hummus", "Hummus with pita", "Middle East", "1 serving", "🥙", { kcal: 330, protein: 11, carbs: 42, fiber: 7, fat: 13, satFat: 2, addedSugar: 0, calcium: 70, iron: 2.5, sodium: 600 }, ["houmous"], true),
  f("shakshuka", "Shakshuka", "Middle East", "1 pan", "🍳", { kcal: 280, protein: 15, carbs: 14, fiber: 4, fat: 18, satFat: 5, addedSugar: 2, calcium: 100, iron: 3, vitD: 2, b12: 1.1, sodium: 700 }),
  f("lentil-soup", "Red lentil soup", "Middle East", "1 bowl", "🍲", { kcal: 230, protein: 14, carbs: 34, fiber: 9, fat: 4, satFat: 0.6, addedSugar: 0, calcium: 45, iron: 4, sodium: 650 }, [], true),
  // Europe
  f("oats", "Porridge oats with milk", "Europe", "1 bowl", "🥣", { kcal: 280, protein: 12, carbs: 42, fiber: 5, fat: 7, satFat: 3, addedSugar: 0, calcium: 280, iron: 2, vitD: 1, b12: 1.1, sodium: 120 }, ["oatmeal", "porridge oats"]),
  f("sardines", "Sardines on toast", "Europe", "1 serving", "🐟", { kcal: 330, protein: 25, carbs: 26, fiber: 3, fat: 14, satFat: 3, addedSugar: 1, calcium: 330, iron: 2.5, vitD: 4, b12: 7, sodium: 750 }, ["sardine"]),
  f("greek-yogurt", "Greek yogurt with berries", "Europe", "1 bowl", "🫐", { kcal: 200, protein: 18, carbs: 20, fiber: 3, fat: 5, satFat: 3, addedSugar: 4, calcium: 230, iron: 0.4, vitD: 0, b12: 1, sodium: 70 }, ["yogurt", "yoghurt"]),
  f("red-wine", "Red wine", "Europe", "1 glass (150 ml)", "🍷", { kcal: 125, protein: 0, carbs: 4, fiber: 0, fat: 0, satFat: 0, addedSugar: 0, calcium: 10, iron: 0.7, sodium: 6, alcohol: 14 }, ["wine"]),
  // North America
  f("eggs", "Scrambled eggs on whole-grain toast", "North America", "1 plate", "🍳", { kcal: 340, protein: 20, carbs: 26, fiber: 4, fat: 17, satFat: 5, addedSugar: 2, calcium: 120, iron: 3, vitD: 2.5, b12: 1.2, sodium: 550 }, ["eggs", "egg"]),
  f("chicken-salad", "Grilled chicken salad", "North America", "1 bowl", "🥗", { kcal: 380, protein: 35, carbs: 14, fiber: 5, fat: 20, satFat: 4, addedSugar: 3, calcium: 90, iron: 2, b12: 0.4, sodium: 650 }, ["salad", "chicken"]),
  f("coffee", "Coffee", "Universal", "1 cup", "☕", { kcal: 5, protein: 0, carbs: 0, fiber: 0, fat: 0, satFat: 0, addedSugar: 0, calcium: 5, iron: 0, sodium: 5, caffeine: 95 }, ["latte", "espresso"]),
  f("soda", "Cola", "Universal", "1 can", "🥤", { kcal: 140, protein: 0, carbs: 39, fiber: 0, fat: 0, satFat: 0, addedSugar: 39, calcium: 0, iron: 0, sodium: 45, caffeine: 34 }, ["coke", "soft drink"]),
  // Latin America
  f("beans-rice", "Black beans & rice", "Latin America", "1 plate", "🍚", { kcal: 420, protein: 15, carbs: 76, fiber: 13, fat: 5, satFat: 1, addedSugar: 0, calcium: 70, iron: 3.5, sodium: 500 }, ["frijoles"], true),
  f("tacos", "Chicken tacos (corn)", "Latin America", "2 tacos", "🌮", { kcal: 380, protein: 24, carbs: 34, fiber: 5, fat: 16, satFat: 4, addedSugar: 1, calcium: 110, iron: 2, b12: 0.3, sodium: 700 }, ["taco"]),
  f("pozole", "Pozole", "Latin America", "1 bowl", "🥣", { kcal: 350, protein: 22, carbs: 32, fiber: 6, fat: 14, satFat: 4, addedSugar: 0, calcium: 60, iron: 2.5, sodium: 1000 }),
  f("chilaquiles", "Chilaquiles with cheese", "Latin America", "1 plate", "🌶️", { kcal: 520, protein: 18, carbs: 50, fiber: 6, fat: 28, satFat: 9, addedSugar: 2, calcium: 300, iron: 2, sodium: 1100 }),
  // Universal
  f("milk", "Milk (fortified)", "Universal", "1 glass (250 ml)", "🥛", { kcal: 120, protein: 8, carbs: 12, fiber: 0, fat: 5, satFat: 3, addedSugar: 0, calcium: 300, iron: 0.1, vitD: 2.5, b12: 1.1, sodium: 100 }),
  f("soy-milk", "Soy milk (fortified)", "Universal", "1 glass (250 ml)", "🥛", { kcal: 100, protein: 7, carbs: 8, fiber: 1, fat: 4, satFat: 0.5, addedSugar: 4, calcium: 300, iron: 1, vitD: 2.5, b12: 1, sodium: 90 }, ["soya milk"], true),
  f("flax", "Ground flaxseed", "Universal", "2 tbsp", "🌾", { kcal: 75, protein: 3, carbs: 4, fiber: 4, fat: 6, satFat: 0.5, addedSugar: 0, calcium: 50, iron: 1, sodium: 5 }, ["linseed"], true),
  f("almonds", "Almonds", "Universal", "30 g", "🥜", { kcal: 170, protein: 6, carbs: 6, fiber: 3.5, fat: 15, satFat: 1, addedSugar: 0, calcium: 75, iron: 1, sodium: 0 }, ["nuts"]),
  f("banana", "Banana", "Universal", "1 medium", "🍌", { kcal: 105, protein: 1.3, carbs: 27, fiber: 3, fat: 0.4, satFat: 0.1, addedSugar: 0, calcium: 6, iron: 0.3, sodium: 1 }),
  f("cake", "Chocolate cake", "Universal", "1 slice", "🍰", { kcal: 350, protein: 4, carbs: 50, fiber: 2, fat: 16, satFat: 6, addedSugar: 30, calcium: 40, iron: 1.5, sodium: 300, caffeine: 5 }, ["dessert"]),
];

export const foodById = (id: string) => FOODS.find((x) => x.id === id);
