// Offline Muse: deterministic intent rules + a reviewed response library. Works without any model or network.
// Shown as "Offline" in the UI. A live provider (see liveProvider.ts) implements the same interface.
import type { ChatProvider, Reply, ReplyContext } from "./types";
import { companionize, encourager, precise } from "./persona";
import { populationContext } from "../forecast/forecast";
import { bpNote } from "../body/logic";

type Rule = { test: RegExp; reply: (c: ReplyContext) => Reply };

const r1 = (n: number) => Math.round(n);

const JOKES = [
  "Here's one for you: I asked my thermostat for some personal space. It said, \"Funny, your internal one hasn't asked me in years.\" 🔥\nHonestly, any woman who can sit through a meeting while secretly being her own sauna deserves a standing ovation, or at least a very good fan.",
  "Menopause brain-fog story: I walked into the kitchen, forgot why, walked out, remembered, walked back in… and found my glasses in the fridge next to the butter. They were very well chilled. 😄\nIf you've ever done the same, welcome to the club. The snacks are excellent and nobody remembers the password.",
  "Someone told me midlife is when you stop caring what people think. I said, \"Wonderful, I'll start right after this nap.\" 😴\nLaughter really does help: it eases stress and connects us, and you deserve a lot more of it.",
];
const STORIES = [
  "**The Lighthouse Keeper's Sister** (a short story)\nWhen Ada turned fifty-two, the town assumed she'd retire from the old harbour café. Instead she bought the lighthouse nobody wanted. The first winter the roof leaked, the stairs creaked and the night sweats kept her up anyway, so she used those 3am hours to paint the sea. By spring, fishermen were stopping by just to see what colour the morning had been. \"I didn't stop shining,\" she told her niece. \"I just moved somewhere people could see the light.\"",
  "**The Walking Club of Rue Verte** (a short story)\nIt began with Mireille, alone after her divorce, walking the same street every evening because the walls at home felt too close. One night a woman fell into step beside her: \"Same time tomorrow?\" By autumn there were eleven of them: a widow, a surgeon, two sisters, a grandmother with a pram. They argued about recipes and hot flashes and laughed loud enough to wake the dogs. Years later, the city put a bench at the corner. The little plaque says: *Here, nobody walked alone.*",
  "**Seeds** (a short story)\nPriyanka was told her garden was too small for mangoes. At fifty-five, with her children grown and her knees complaining, she planted one anyway, in a pot, on a balcony, in a city with real winters. Neighbours smiled politely. Every season she moved it inside, sang to it (badly) and kept a journal. In the seventh summer, three small mangoes appeared. She shared them with everyone who had smiled politely. \"It's never too late,\" she said, \"for something sweet to grow.\"",
];

const RULES: Rule[] = [
  // ---- whole-body facts (her own records only)
  { test: /\b(my (blood pressure|bp)|how (am i|have i been) sleeping|my sleep|my steps|how many steps|my mood (this|lately)|my weight)\b/, reply: (c) => {
    const b = c.body ?? {};
    const parts: string[] = [];
    if (b.lastBp) { const n = bpNote(b.lastBp.sys, b.lastBp.dia); parts.push(`Your last blood pressure reading was **${b.lastBp.sys}/${b.lastBp.dia}** on ${new Date(b.lastBp.date + "T12:00").toLocaleDateString()}: ${n.label.toLowerCase()}. ${n.text}`); }
    if (b.sleep7 !== undefined) parts.push(`You've averaged **${b.sleep7} hours** of sleep over the last 7 days.`);
    if (b.steps7 !== undefined) parts.push(`Your 7-day average is **${Math.round(b.steps7).toLocaleString()} steps** a day.`);
    if (b.mood7 !== undefined) parts.push(`Your mood has averaged ${b.mood7} out of 5 this week.`);
    if (b.weightChange30 !== undefined) parts.push(`Your weight changed by ${b.weightChange30 > 0 ? "+" : ""}${b.weightChange30} kg over 30 days.`);
    if (!parts.length) return { text: "I don't have any of those records yet, so I won't guess. You can add them in Body, movement & mind.", actions: [{ kind: "open", label: "Open health dashboard", payload: "/app/body" }] };
    return { text: parts.join("\n") + "\nThese are your own entries. Trends matter more than single readings.", actions: [{ kind: "open", label: "See my trends", payload: "/app/body" }] };
  } },
  // ---- forecasts: personal next period (time series on her logs) and population context (NHANES). Never her final period.
  { test: /\b(next period|when will my period|period (be )?due|predict my period)\b/, reply: (c) => {
    const f = c.journey?.forecast;
    if (!f || f.status !== "ok") return { text: f?.status === "too-irregular" ? "Your recent cycles vary too much for me to forecast honestly, which is common during the menopausal transition. I'd rather not guess." : "I need four or more logged period start dates before I can forecast. Shall we log them?", actions: [{ kind: "open", label: "Open Menopause Journey", payload: "/app/journey" }] };
    const d = (x: string) => new Date(x + "T12:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
    return { text: `Based on your own cycles, your next period is most likely around **${d(f.nextStart!)}**, probably between ${d(f.earliest!)} and ${d(f.latest!)}.${f.backtestMAE !== undefined ? ` On your past cycles this method was off by about ${f.backtestMAE} days.` : ""}\nIt's an estimate, not a fertility or contraception tool.`, actions: [{ kind: "open", label: "See forecast", payload: "/app/journey" }] };
  } },
  { test: /\b(when will i (reach|hit|go through|start) (the )?menopause|age (of|at) menopause|average age.*menopause|how old.*menopause)\b/, reply: (c) => {
    const age = c.journey?.age;
    const p = age && age >= 35 && age <= 60 ? populationContext(age) : null;
    return { text: "Nobody, including me, can predict exactly when your final period will be. Here's what real data shows. In the U.S. national NHANES survey (2013–2018), the median age at natural menopause was **51** (CDC NHANES, analysed by FEMORA)." +
      (p ? `\nAmong women aged ${age}, about ${Math.round(p.reached * 100)}% had reached it.` : "") +
      "\nYour own cycle changes and symptoms tell you more than averages do, and a clinician can help interpret them.", actions: [{ kind: "open", label: "See the curve", payload: "/app/journey" }] };
  } },
  // ---- journey facts (deterministic, from her own records)
  { test: /\b(last period|my cycles?|cycle length|how long (are|is) my cycles?|my symptoms (this|last) (week|fortnight))\b/, reply: (c) => {
    const j = c.journey;
    if (!j || (!j.lastPeriod && !j.topSymptoms14d.length)) return { text: "I don't have any cycles or symptoms recorded yet, so I won't guess. If you log your period start dates and symptoms in your Menopause Journey, I can tell you about your patterns.", actions: [{ kind: "open", label: "Open Menopause Journey", payload: "/app/journey" }] };
    const parts: string[] = [];
    if (j.lastPeriod) parts.push(`Your last recorded period started on **${new Date(j.lastPeriod + "T12:00").toLocaleDateString()}**, ${j.daysSinceLast} days ago.`);
    if (j.avgCycle) parts.push(`Across ${j.cyclesLogged} recorded cycle${j.cyclesLogged > 1 ? "s" : ""}, your average is **${j.avgCycle} days**.`);
    if (j.topSymptoms14d.length) parts.push(`In the last two weeks you logged ${j.topSymptoms14d.map(([n, k]) => `${n.toLowerCase()} (${k})`).join(", ")}.`);
    parts.push("These come straight from your records. Patterns can suggest changes, but only a clinician can assess your stage.");
    return { text: parts.join("\n"), actions: [{ kind: "open", label: "See my journey", payload: "/app/journey" }] };
  } },
  // ---- one companion, from safety to health: route into every feature
  { test: /\b(remind|reminder|medication|medicine|pills?|tablets?|dose|hrt)\b/, reply: () => ({
    text: "I can help you stay on track with that. In Reminders you can add each medicine or supplement with its dose and times, and I'll nudge you when a dose is due. You can mark it as taken in one tap.\nI'll also remind you about health check-ups like cervical screening, mammograms or bone density scans.",
    actions: [{ kind: "open", label: "Open Reminders", payload: "/app/reminders" }] }) },
  { test: /\b(free|screening|check-?ups?|smear|pap|hpv|mammogram|sample|test kit|campaign|events?|goodies)\b/, reply: () => ({
    text: "Looking after your health shouldn't depend on your budget. FEMORA gathers free health check-ups, sample collection (like at-home HPV kits), consultations, community events and free goodies near you.\nFollow the categories you care about and I'll notify you when something comes up.",
    actions: [{ kind: "open", label: "See free care near me", payload: "/app/free-care" }] }) },
  { test: /\b(unsafe|safety|walking home|followed|scared to go out|trusted contact|sos)\b/, reply: () => ({
    text: "Your safety matters most. If you're in danger right now, call your local emergency number.\nFor everyday peace of mind: share your plans with someone you trust, keep your phone charged, and choose well-lit routes. Guardian lets you call emergency services in one tap, send an SOS draft to trusted people (you press send), and schedule check-ins.",
    actions: [{ kind: "open", label: "Open Guardian", payload: "/app/guardian" }] }) },
  // ---- joy: humour and stories (when invited)
  { test: /\b(make me laugh|joke|funny|cheer me up|lighten)\b/, reply: (c) => ({
    text: JOKES[c.history.length % JOKES.length], followUps: ["Another one!", "Tell me a story", "That's so me 😂"] }) },
  { test: /\b(story|stories|inspire me|something inspiring)\b/, reply: (c) => ({
    text: STORIES[c.history.length % STORIES.length] + "\n\nThis is an original story, written to inspire. The characters are fictional.",
    followUps: ["Tell me another story", "Make me laugh", "That inspired me"] }) },
  // ---- loneliness
  { test: /\b(lonel\w*|alone|isolat\w*|no friends|miss my friends)\b/, reply: (c) => ({
    text: `That sounds hard${c.profile.livesAlone ? ", especially when you come home to a quiet place" : ""}. Loneliness is common in midlife, after moves, changes in work or family, and it isn't a personal failing.\n` +
      "Would it help to talk about what a good week of connection used to look like for you? Some women find one small, regular thing easier than a big social plan: a weekly walk with one person, a class, or an online circle with people going through the same change.",
    followUps: ["What used to help me feel connected?", "Show me circles near me", "I just want to vent for a bit"],
    actions: [{ kind: "open", label: "Explore Sisterhood circles", payload: "/app/sisterhood" }, { kind: "log-symptom", label: "Log: feeling lonely", payload: "Loneliness" }],
  }) },

  // ---- companion library: everyday life and emotions (validate → encourage → small ideas → caring question)
  { test: /\b(overwhelm\w*|too much|can'?t cope|exhausted by everything|burn(ed|t)? out)\b/, reply: () => ({
    text: "That sounds like a lot to carry, and it makes complete sense that you feel overwhelmed. You've been holding so many things together.\n" +
      "Let's make it lighter, together. If you like, tell me the three things weighing on you most, and we'll pick just one to look at. Everything else can wait for a moment.\n" +
      "You don't have to do it all today. Being kind to yourself counts as progress.",
    followUps: ["Here are the three things…", "I just need to vent", "Help me plan a gentler day"],
  }) },
  { test: /\b(confiden\w*|not good enough|insecure|imposter|doubt myself)\b/, reply: () => ({
    text: "I hear you, and I want you to know that confidence often wobbles in midlife. Bodies change, roles change, and the world doesn't always notice what women bring. That isn't a reflection of your worth.\n" +
      "Think of the last time you handled something hard: a tough conversation, a crisis at work, caring for someone. That strength is still yours.\n" +
      "Would you like to add a moment you felt proud of to your Joy Map, so it's there on harder days?",
    actions: [{ kind: "open", label: "Open My Joy Map", payload: "/app/joy" }],
    followUps: ["What am I good at?", "I had a hard day at work", "Help me feel stronger"],
  }) },
  { test: /\b(body image|hate my body|my body|look old|ugly|unattractive|my weight|gained weight|weight gain|belly)\b/, reply: () => ({
    text: "Thank you for trusting me with this. Changes in shape and weight around menopause are very common, partly because shifting hormones change where the body stores fat. It isn't a failure of willpower.\n" +
      "Your body has carried you through so much. Many women find it helps to focus on how they want to feel, like strong, energised and rested, rather than on a number.\n" +
      "Strength training, enough protein and good sleep support how you feel, whatever the scale says.",
    followUps: ["What helps with energy?", "Suggest strength exercises", "How is my protein?"],
  }) },
  { test: /\b(hair (loss|thinning|falling)|losing (my )?hair|thinning hair|bald)\b/, reply: () => ({
    text: "Hair changes can feel so personal, and it's completely understandable to feel upset. Thinning hair is common around menopause, and it can also be linked to thyroid, iron levels or stress, so it's worth mentioning to a clinician, who can check.\n" +
      "You're not vain for caring about this. It's part of how you recognise yourself.",
    followUps: ["What should I ask my doctor?", "Foods with iron in my cuisine"],
    actions: [{ kind: "log-symptom", label: "Log: hair thinning", payload: "Hair thinning" }],
  }) },
  { test: /\b(old|ageing|aging|getting older|invisible|past it|50|fifty|sixty)\b/, reply: () => ({
    text: "So many women tell me they feel more invisible as they get older, and it hurts. But this chapter can hold real freedom: knowing what you want, caring less about others' opinions, and new beginnings.\n" +
      "You have decades of wisdom, and the world needs it. What's something you've always wanted to try, or come back to?",
    followUps: ["Things I used to love doing", "Find a community near me"],
  }) },
  { test: /\b(husband|wife|partner|marriage|married|divorce\w*|relationship|boyfriend|girlfriend|intimacy|sex)\b/, reply: () => ({
    text: "Relationships go through their own changes in midlife, and it's brave to talk about it. Shifts in mood, sleep, libido and energy can affect closeness, and partners don't always understand what's happening.\n" +
      "Some couples find it helps to share a simple explainer about menopause, or to pick a calm moment to say, \"Here's what I'm going through, and here's what would help me.\"\n" +
      "You deserve to feel understood and supported at home.",
    followUps: ["Help me explain menopause to my partner", "I feel disconnected", "Is low libido normal?"],
  }) },
  { test: /\b(kids?|children|son|daughter|teen\w*|empty nest|grandchild\w*|mum|mom|mother)\b/, reply: () => ({
    text: "Family can bring so much love and so much load, often at the same time. Many women in midlife are caring for children, ageing parents and work all at once, and it's a lot.\n" +
      "Your care for them is beautiful. Just remember that you count too. Who looks after you when you're looking after everyone?",
    followUps: ["I never get time for myself", "My kids are leaving home", "Caring for my parents"],
  }) },
  { test: /\b(work|job|career|boss|colleague|meeting|promotion|retire\w*)\b/, reply: () => ({
    text: "Work can be tough during this transition, especially with hot flashes in meetings, broken sleep or brain fog on deadline days. You're doing your job while your body is doing a lot of work too, and that deserves credit.\n" +
      "Some women find small adjustments help: a fan at their desk, water nearby, layers, or a quiet word with a manager. Many workplaces now have menopause policies.\n" +
      "You have so much experience to offer. That doesn't disappear on a hard day.",
    followUps: ["How do I talk to my manager?", "I can't focus at work", "I'm thinking about a career change"],
  }) },
  { test: /\b(grief|griev\w*|lost (my|a)|passed away|died|death|miss (him|her|them))\b/, reply: () => ({
    text: "I'm so sorry. Grief is love with nowhere to go, and there's no right way or timeline to feel it.\n" +
      "Be gentle with yourself. Grief can affect sleep, appetite and energy, especially on top of menopause.\n" +
      "Would you like to tell me about them? I'd be honoured to hear.",
    followUps: ["Tell you about them", "Find a grief support group"],
  }) },
  { test: /\b(nobody (understands|listens|cares)|no one (understands|listens|cares)|misunderstood|unheard)\b/, reply: () => ({
    text: "Feeling unheard is so lonely, and I'm really glad you're telling me. I'm listening, and what you feel makes sense.\n" +
      "Many women going through menopause say the people around them just don't get it yet. That's one reason FEMORA's sisterhood circles exist: women who truly understand.",
    actions: [{ kind: "open", label: "Explore Sisterhood circles", payload: "/app/sisterhood" }],
    followUps: ["Tell me more", "Find women like me"],
  }) },
  { test: /\b(guilty|guilt|ashamed|shame|selfish)\b/, reply: () => ({
    text: "Guilt can be so heavy. Taking care of yourself isn't selfish. It's what lets you keep showing up for the people and things you love.\n" +
      "If a friend told you what you've just told me, what would you say to her? You deserve that same kindness.",
    followUps: ["I feel guilty resting", "Help me set a boundary"],
  }) },
  // ---- memory-worthy self-disclosures (proposed, never auto-saved)
  { test: /\bi('m| am) (a )?(vegetarian|vegan|pescatarian)\b/, reply: (c) => {
    const diet = c.text.toLowerCase().match(/vegetarian|vegan|pescatarian/)![0];
    return { text: `Thanks for telling me. I'll keep ${diet} options in mind when we talk about food.`, memory: `Eats a ${diet} diet` }; } },

  // ---- sleep
  { test: /\b(sleep\w*|slept|insomnia|wake up|waking|night sweats?|tired|exhausted)\b/, reply: (c) => ({
    text: "Poor sleep wears everything down: mood, patience, focus. During the menopausal transition, night sweats and earlier waking are common reasons [S1].\n" +
      "A few things worth noticing for a week or two:\n- What time you wake, and whether you're hot or anxious when you do\n- Caffeine after midday" +
      (c.food.weekCaffeineAvg ? ` (you've logged about ${r1(c.food.weekCaffeineAvg)} mg a day on average this week)` : "") +
      "\n- Alcohol in the evening" + (c.food.weekAlcoholDays ? ` (logged on ${c.food.weekAlcoholDays} of the last ${c.food.weekDays} days)` : "") +
      "\nIf sleep problems are affecting your days, a clinician can discuss options, including treatments for night sweats [S3]. Want me to log tonight's sleep as a symptom so we can look at the pattern?",
    sources: ["S1", "S3"],
    followUps: ["Does alcohol affect my sleep?", "Give me a wind-down routine", "What should I ask my doctor?"],
    actions: [{ kind: "log-symptom", label: "Log: poor sleep", payload: "Sleep disruption" }],
  }) },

  // ---- cycles
  { test: /\b(periods?|cycles?|bleeding|spotting|skipped|irregular)\b/, reply: () => ({
    text: "Changes in cycle length are often the first sign of the menopausal transition. Researchers describe stages using cycle patterns: in the **early transition** cycle length varies by 7 or more days from your usual, and in the **late transition** there are gaps of 60 days or more [S2].\n" +
      "Those are descriptions for research and care, not a test. Hormonal contraception, thyroid conditions, pregnancy and other causes can change cycles too, and nobody can predict the exact date of a final period.\n" +
      "Logging start dates for a few months gives you and your clinician a clearer picture.",
    sources: ["S2"],
    followUps: ["What stage might I be in?", "When should I see a doctor about bleeding?", "Log my period"],
    actions: [{ kind: "open", label: "Open cycle tracker", payload: "/app/journey" }, { kind: "log-symptom", label: "Log: irregular cycle", payload: "Cycle change" }],
  }) },

  // ---- hot flashes
  { test: /\b(hot flash|hot flush|flush|sweating|overheat)/, reply: () => ({
    text: "Hot flashes are the most common menopausal symptom and can last for several years [S1]. Some people notice triggers like alcohol, caffeine, spicy food or warm rooms, though triggers vary person to person.\n" +
      "Effective treatments exist, including hormonal and non-hormonal options, so it's worth discussing with a clinician if they disrupt your day or sleep [S3].",
    sources: ["S1", "S3"],
    followUps: ["Do any foods help?", "Prepare questions for my doctor", "Log a hot flash"],
    actions: [{ kind: "log-symptom", label: "Log: hot flash", payload: "Hot flash" }],
  }) },

  // ---- food questions (deterministic numbers from the nutrition engine)
  { test: /\bprotein\b/, reply: (c) => ({
    text: `Over the last ${c.food.weekDays} days you logged **${r1(c.food.weekProtein)} g of protein**, about **${r1(c.food.weekProtein / Math.max(c.food.weekDays, 1))} g a day**, against your goal of ${c.food.proteinTarget} g.\n` +
      "These totals come straight from your food log (estimates, not lab measurements). Protein helps maintain muscle, which naturally declines with age." +
      ((c.profile.diet ?? "").toLowerCase().includes("veg") ? "\nVegetarian sources that fit your log: dal, curd, paneer, tofu, chickpeas." : ""),
    followUps: ["Suggest meals from my cuisine", "How is my calcium?", "Open my food log"],
    actions: [{ kind: "open", label: "Open food log", payload: "/app/food" }],
  }) },
  { test: /\b(calcium|bone)/, reply: (c) => ({
    text: `Today you've logged **${r1(c.food.todayCalcium)} mg of calcium** of your ${c.food.calciumTarget} mg reference. Bone loss speeds up after menopause, so calcium, vitamin D, protein and strength exercise all matter [S1].\n` +
      "Foods in your cuisine that are good calcium sources include dairy, fortified soy milk, tofu set with calcium, sardines and leafy greens.",
    sources: ["S1"], followUps: ["Open my food log", "What exercise helps bones?"],
    actions: [{ kind: "open", label: "Open food log", payload: "/app/food" }],
  }) },
  { test: /\b(alcohol|wine|drink)/, reply: (c) => ({
    text: `You logged alcohol on **${c.food.weekAlcoholDays} of the last ${c.food.weekDays} days**. Sleep tracking isn't recorded yet, so I can't compare the two honestly. Once sleep tracking is on, I'll show both side by side, as a pattern rather than proof of cause.`,
    followUps: ["How much protein did I eat this week?", "Help me sleep better"],
  }) },
  { test: /\b(eat|food|meal|recipe|cook|hungry|diet|suggest)/, reply: (c) => ({
    text: `Here are a few ideas${c.profile.cuisine.length ? ` from ${c.profile.cuisine.join(" and ")} cooking` : ""} that bring protein, fiber and calcium together:\n` +
      (c.profile.cuisine.includes("South Asia") ? "- Dal with roti and a bowl of curd\n- Palak paneer with brown rice\n- Sprouted moong salad with lemon" :
       c.profile.cuisine.includes("East Asia") ? "- Tofu stir-fry with greens\n- Salmon with rice and miso soup\n- Edamame as a snack" :
       c.profile.cuisine.includes("Latin America") ? "- Black beans and rice with salsa\n- Chicken tacos on corn tortillas with cheese\n- Pozole with lots of vegetables" :
       c.profile.cuisine.includes("West Africa") ? "- Egusi soup with fish\n- Akara with pap and milk\n- Jollof rice with grilled fish and greens" :
       "- Shakshuka with whole-grain bread\n- Lentil soup with a yogurt side\n- Hummus, salad and grilled chicken") +
      "\nNo food cures menopause, but an overall pattern rich in plants, protein and calcium supports bone, muscle and heart health.",
    followUps: ["How much protein did I eat this week?", "Log a meal"],
    actions: [{ kind: "open", label: "Log a meal", payload: "/app/food" }],
  }) },

  // ---- emotions
  { test: /\b(anxious|anxiety|worried|panic|stressed|overwhelm)/, reply: () => ({
    text: "That sounds exhausting. Anxiety can rise during the menopausal transition, and life in midlife often stacks up at the same time: work, children, parents.\n" +
      "If you'd like, we can try a slow breath together: in for 4, hold for 4, out for 6, three times. Or you can just tell me what's on your mind.\n" +
      "If anxiety is affecting your daily life, please talk to a clinician. You deserve real support.",
    followUps: ["Let's do the breathing", "I just want to talk", "Log my mood"],
    actions: [{ kind: "log-symptom", label: "Log: anxiety", payload: "Anxiety" }],
  }) },
  { test: /\b(sad|sadness|cry\w*|feeling down|feel low|depressed|irritab\w*|angry)\b/, reply: () => ({
    text: "Thank you for trusting me with that. Mood changes are common around menopause, and they're real, not something to just push through.\n" +
      "Would you like to talk about what's been weighing on you, or would it help more to write it down in your journal?\n" +
      "If low mood lasts more than two weeks or makes daily life hard, a clinician or counsellor can help.",
    followUps: ["Open my journal", "Find a support circle", "Help me find a therapist"],
    actions: [{ kind: "log-symptom", label: "Log: low mood", payload: "Low mood" }],
  }) },

  // ---- joy
  { test: /\b(happy|joy|proud|grateful|great day|achiev|confident)/, reply: () => ({
    text: "I love hearing that. What made it feel good? Moments like this are worth remembering, especially on harder days.",
    followUps: ["Add this to my Joy Map", "What usually makes me happy?"],
    actions: [{ kind: "joy", label: "Add to My Joy Map", payload: "" }],
  }) },

  // ---- doctor prep
  { test: /\b(doctor|appointment|gp|gyn|clinician|questions)\b/, reply: (c) => ({
    text: `Let's prepare. A useful one-page summary for your appointment could include:\n- Your stage notes and cycle history (${c.profile.stage})\n- Your top three symptoms, how often they happen, and how they affect your day\n- Medicines and supplements you take\n- What you want from the visit: understanding, treatment options, referrals\n` +
      "Questions you might ask: \"Could my symptoms be menopause or something else?\" \"What are my treatment options, hormonal and non-hormonal?\" [S3]",
    sources: ["S3"], followUps: ["Find a menopause-trained clinician"],
    actions: [{ kind: "open", label: "Healthcare & appointments", payload: "/app/care" }],
  }) },

  // ---- greetings / small talk
  { test: /^(hi|hello|hey|good (morning|evening|afternoon))\b/, reply: (c) => ({
    text: `Hi ${c.profile.name}. How are you, really, today? We can talk about anything: how you're feeling, food, sleep, family, work, or just your day.`,
    followUps: ["I've been sleeping badly", "I feel lonely lately", "How much protein did I eat this week?"],
  }) },
];

const FALLBACK: Record<string, string> = {
  journal: "Thank you for writing that down. I've kept it here in your conversation. Would you like me to reflect anything back, or simply hold it?",
  default: "Thank you for sharing that with me. I'm right here with you, and there's no rush.\nWhat feels most important about it for you right now?",
};

export const scriptedProvider: ChatProvider = {
  id: "muse-offline",
  label: "Muse offline (rule-based responses)",
  live: false,
  async respond(ctx) {
    const t = ctx.text.toLowerCase();
    const seed = ctx.history.length;
    const rule = RULES.find((x) => x.test.test(t));
    const r: Reply = rule ? rule.reply(ctx) : { text: FALLBACK[ctx.mode] ?? FALLBACK.default, followUps: ["I've been sleeping badly", "I feel overwhelmed", "Help me feel more confident"] };
    // Emotional-support mode adds a sincere word of encouragement up front.
    const text = ctx.mode === "emotional" && rule ? `${encourager(seed)} ${r.text}` : r.text;
    // Precise when asked (toggle or "keep it short"), otherwise the full companion reply.
    const wantsBrief = ctx.brief || /\b(brief|short answer|keep it short|quick answer|tl;?dr|in short)\b/.test(t);
    const full = companionize(text, ctx.mode, seed);
    return { ...r, text: wantsBrief ? precise(full) : full };
  },
};
