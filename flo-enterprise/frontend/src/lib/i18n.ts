export type Lang = "en" | "fr" | "es" | "hi" | "ta" | "ko";
export const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "English" }, { id: "fr", label: "Français" }, { id: "es", label: "Español" },
  { id: "hi", label: "हिन्दी" }, { id: "ta", label: "தமிழ்" }, { id: "ko", label: "한국어" },
];
const T: Record<string, Record<Lang, string>> = {
  executive: { en: "Executive Command Center", fr: "Centre de commandement", es: "Centro de mando ejecutivo", hi: "कार्यकारी कमांड सेंटर", ta: "நிர்வாக கட்டுப்பாட்டு மையம்", ko: "경영 지휘 센터" },
  investment: { en: "Investment Intelligence", fr: "Intelligence d'investissement", es: "Inteligencia de inversión", hi: "निवेश इंटेलिजेंस", ta: "முதலீட்டு நுண்ணறிவு", ko: "투자 인텔리전스" },
  scenarios: { en: "Scenario Simulator", fr: "Simulateur de scénarios", es: "Simulador de escenarios", hi: "परिदृश्य सिम्युलेटर", ta: "சூழ்நிலை உருவகப்படுத்தி", ko: "시나리오 시뮬레이터" },
  wealth: { en: "Wealth Advisor 360", fr: "Conseiller 360", es: "Asesor patrimonial 360", hi: "वेल्थ एडवाइज़र 360", ta: "செல்வ ஆலோசகர் 360", ko: "자산 어드바이저 360" },
  products: { en: "Product Research", fr: "Recherche de produits", es: "Investigación de productos", hi: "उत्पाद अनुसंधान", ta: "தயாரிப்பு ஆய்வு", ko: "상품 리서치" },
  compliance: { en: "Regulatory & Risk", fr: "Réglementation et risque", es: "Regulación y riesgo", hi: "नियामक और जोखिम", ta: "ஒழுங்குமுறை & இடர்", ko: "규제 및 리스크" },
  approvals: { en: "Approvals", fr: "Approbations", es: "Aprobaciones", hi: "अनुमोदन", ta: "ஒப்புதல்கள்", ko: "승인" },
  decisions: { en: "Decision Memory", fr: "Mémoire des décisions", es: "Memoria de decisiones", hi: "निर्णय स्मृति", ta: "முடிவு நினைவகம்", ko: "의사결정 기록" },
  knowledge: { en: "Knowledge Search", fr: "Recherche documentaire", es: "Búsqueda de conocimiento", hi: "ज्ञान खोज", ta: "அறிவுத் தேடல்", ko: "지식 검색" },
  aiops: { en: "AI Operations", fr: "Opérations IA", es: "Operaciones de IA", hi: "एआई संचालन", ta: "AI செயல்பாடுகள்", ko: "AI 운영" },
  governance: { en: "Governance & Audit", fr: "Gouvernance et audit", es: "Gobernanza y auditoría", hi: "शासन और ऑडिट", ta: "ஆளுகை & தணிக்கை", ko: "거버넌스 및 감사" },
  privacy: { en: "Privacy Console", fr: "Console de confidentialité", es: "Consola de privacidad", hi: "गोपनीयता कंसोल", ta: "தனியுரிமை பணியகம்", ko: "개인정보 콘솔" },
  data: { en: "Data Products", fr: "Produits de données", es: "Productos de datos", hi: "डेटा उत्पाद", ta: "தரவு தயாரிப்புகள்", ko: "데이터 상품" },
  ask: { en: "Ask Flo", fr: "Demander à Flo", es: "Pregunte a Flo", hi: "Flo से पूछें", ta: "Flo-விடம் கேளுங்கள்", ko: "Flo에게 질문" },
  explain: { en: "Explain with Flo", fr: "Expliquer avec Flo", es: "Explicar con Flo", hi: "Flo से समझें", ta: "Flo மூலம் விளக்கு", ko: "Flo로 설명" },
  dataAsOf: { en: "Data as of", fr: "Données au", es: "Datos al", hi: "डेटा तिथि", ta: "தரவு தேதி", ko: "기준일" },
  synthetic: { en: "Synthetic data", fr: "Données synthétiques", es: "Datos sintéticos", hi: "कृत्रिम डेटा", ta: "செயற்கை தரவு", ko: "합성 데이터" },
  search: { en: "Search clients, funds, documents…", fr: "Rechercher clients, fonds, documents…", es: "Buscar clientes, fondos, documentos…", hi: "ग्राहक, फंड, दस्तावेज़ खोजें…", ta: "வாடிக்கையாளர்கள், நிதிகள், ஆவணங்கள் தேடு…", ko: "고객, 펀드, 문서 검색…" },
};
export const t = (key: string, lang: Lang) => T[key]?.[lang] ?? T[key]?.en ?? key;
