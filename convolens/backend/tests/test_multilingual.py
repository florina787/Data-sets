from app.multilingual.language import detect_language
from app.multilingual.translation import check_translation


def test_message_level_detection():
    assert detect_language("Mi pedido no ha llegado y el seguimiento no cambia desde hace días")["language"] == "es"
    assert detect_language("Seit heute Morgen kein Netz in meiner Gegend. Gibt es eine Störung?")["language"] == "de"
    assert detect_language("hello??")["language"] == "unknown"  # too short: never forced


def test_code_switching_and_romanized_text():
    mixed = detect_language("I can't log in to my cuenta, la contraseña no funciona desde ayer and support is not helping")
    assert mixed["language"] in ("mixed", "es")  # code-switched; exact split is model-dependent
    hl = detect_language("mera refund abhi tak nahi aaya hai, 2 hafte ho gaye kya kar rahe ho aap log")
    assert hl["language"] in ("hi-Latn", "mixed") and hl["detail"].get("transliteration") == "hi-Latn"


def test_translation_checks_flag_lost_numbers_and_negation():
    ok = check_translation("No he recibido el reembolso de 45,99 € del 12/11", "I have not received the refund of €45.99 from 12/11")
    assert not ok["needs_review"], ok
    bad = check_translation("No he recibido el reembolso de 45,99 €", "I have received the money")
    assert bad["needs_review"] and {"numbers", "negation", "terminology", "currency"} <= set(bad["failed"])


def test_synthetic_multilingual_dataset_is_separate(client, demo_ids):
    dss = {d["id"]: d for d in client.get("/api/datasets").json()["datasets"]}
    ml = dss[demo_ids["multilingual"]]
    assert ml["synthetic"] and ml["kind"] == "synthetic_multilingual"
    dash = client.get(f"/api/datasets/{demo_ids['multilingual']}/languages").json()
    assert dash["groups"] and all("suppressed_reason" in g or g["comparison_allowed"] for g in dash["groups"])
    assert any(t["method"] == "reference" for t in dash["translations"])
    demo = client.get(f"/api/datasets/{demo_ids['demo']}/overview").json()
    assert demo["summary"]["denominator"] == dss[demo_ids["demo"]]["conversations"]  # multilingual scenarios never added
