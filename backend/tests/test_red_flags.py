import inspect
from pathlib import Path
import pytest

from app.services.red_flag_engine import evaluate, list_rules, load_rules
import app.services.red_flag_engine as red_flag_engine_mod


def ids(text, bucket="triggered", age_group=None):
    res = getattr(evaluate("s", text, age_group=age_group), bucket)
    matched_ids = {r.rule_id for r in res}
    for r in res:
        for alias in getattr(r, "aliases", []):
            matched_ids.add(alias)
    return matched_ids


def test_chest_pain_and_breathing_trigger():
    t = "দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়।"
    assert {"CHEST_PAIN", "BREATHING_DIFFICULTY"}.issubset(ids(t))


@pytest.mark.parametrize("text,rule", [
    ("দুই ঘণ্টা ধরে বুকে খুব ব্যথা", "CHEST_PAIN"),
    ("নিঃশ্বাস নিতে খুব কষ্ট হচ্ছে", "BREATHING_DIFFICULTY"),
    ("প্রচুর রক্ত পড়ছে", "HEAVY_BLEEDING"),
    ("দুই মাসের বাচ্চার জ্বর", "INFANT_FEVER"),
    ("হঠাৎ অজ্ঞান হয়ে গেছে", "UNCONSCIOUSNESS"),
    ("খিঁচুনি হচ্ছে", "SEIZURE"),
    ("চোখ ভেতরে ঢুকে গেছে এবং প্রস্রাব বন্ধ", "SEVERE_DEHYDRATION"),
    ("মুখ বেঁকে গেছে এবং কথা জড়িয়ে গেছে", "STROKE_SIGNS"),
    ("রক্ত বমি করেছে", "BLOOD_IN_VOMIT_STOOL"),
    ("রক্ত বমি করেছে", "VOMITING_BLOOD"),
    ("পায়খানার সাথে রক্ত যাচ্ছে", "BLOOD_IN_VOMIT_STOOL"),
    ("গর্ভবতী অবস্থায় রক্ত পড়ছে", "PREGNANCY_BLEEDING"),
    ("my father has chest pain", "CHEST_PAIN"),
    ("shortness of breath since morning", "BREATHING_DIFFICULTY"),
])
def test_each_starter_rule_triggers_on_positive_sentence(text, rule):
    assert rule in ids(text)


def test_dialect_expressions_trigger_rules():
    # Sylheti / Chittagonian dialect expressions
    assert "CHEST_PAIN" in ids("ছাতিত বিষ করের")
    assert "BREATHING_DIFFICULTY" in ids("দম আটকি যার")
    assert "UNCONSCIOUSNESS" in ids("হঠাৎ বেহুঁশ হয়ে পড়ছে")


def test_ordinary_symptoms_do_not_trigger():
    assert ids("তিন দিন ধরে মাথায় ব্যথা, অল্প জ্বর আছে।") == set()
    assert ids("পেটে মাঝে মাঝে ব্যথা করে, ওষুধ খাইনি।") == set()


def test_explicit_negation_is_not_a_trigger_but_is_reported():
    r = evaluate("s", "বুকে ব্যথা নেই, মাথা ব্যথা আছে")
    assert r.triggered == []
    assert [x.rule_id for x in r.explicitly_denied] == ["CHEST_PAIN"]
    assert [x.rule_id for x in r.negated] == ["CHEST_PAIN"]
    assert r.explicitly_denied[0].status == "explicitly_denied"


def test_english_negation_reported_as_explicitly_denied():
    r = evaluate("s", "patient denies chest pain, mild headache")
    assert r.triggered == []
    assert [x.rule_id for x in r.explicitly_denied] == ["CHEST_PAIN"]


def test_unrelated_negation_does_not_suppress_alert():
    # 'না' belongs to a different statement in the same clause; the alert must still fire
    assert "CHEST_PAIN" in ids("বুকে ব্যথা, খেতে পারছি না")
    assert "CHEST_PAIN" in ids("খুব বুকে ব্যথা কিন্তু কিছু খেতে পারছি না")


def test_affirmed_beats_negated_when_both_present():
    assert "CHEST_PAIN" in ids("বুকে ব্যথা নেই। আজ সকাল থেকে আবার বুকে ব্যথা হচ্ছে")


def test_infant_fever_without_age_needs_information():
    r = evaluate("s", "বাচ্চার জ্বর আছে")
    assert r.triggered == []
    assert [x.rule_id for x in r.insufficient_information] == ["INFANT_FEVER"]
    assert [x.rule_id for x in r.needs_information] == ["INFANT_FEVER"]
    assert r.insufficient_information[0].status == "insufficient_information"


def test_infant_fever_with_intake_age_group_triggers():
    r = evaluate("s", "বাচ্চার জ্বর ১০৩ ডিগ্রি", age_group="infant")
    assert "INFANT_FEVER" in [x.rule_id for x in r.triggered]


def test_fever_without_infant_does_not_trigger_infant_rule():
    r = evaluate("s", "আমার জ্বর আছে")
    assert r.triggered == [] and r.needs_information == [] and r.insufficient_information == []
    infant_rule = next(x for x in r.not_mentioned if x.rule_id == "INFANT_FEVER")
    assert infant_rule.status == "not_mentioned"


def test_missing_mention_is_not_mentioned_never_absent():
    r = evaluate("s", "মাথা ব্যথা")
    assert r.triggered == []
    assert r.explicitly_denied == []
    not_mentioned_ids = {x.rule_id for x in r.not_mentioned}
    assert "CHEST_PAIN" in not_mentioned_ids
    assert "BREATHING_DIFFICULTY" in not_mentioned_ids
    for rule in r.not_mentioned:
        assert rule.status == "not_mentioned"
        assert rule.status != "absent"


def test_every_triggered_rule_carries_bilingual_guidance_and_no_medication():
    r = evaluate("s", "বুকে ব্যথা")
    x = r.triggered[0]
    assert x.explanation_bn and x.explanation_en and x.recommended_action_bn and x.recommended_action_en
    assert x.matched_text and x.clinically_reviewed is False
    assert x.review_status == "pending_clinical_review"
    for word in ("mg", "tablet", "capsule", "paracetamol", "aspirin", "antibiotic", "take ", "ওষুধ খান", "প্যারাসিটামল"):
        assert word not in x.recommended_action_en.lower()
        assert word not in x.recommended_action_bn.lower()


def test_ruleset_is_flagged_unreviewed():
    rules_cfg = load_rules()
    assert rules_cfg["clinically_reviewed"] is False
    for rule in rules_cfg["rules"]:
        assert rule["review_status"] == "pending_clinical_review"


def test_no_llm_imported_in_red_flag_engine():
    """Deterministic requirement: Red-flag engine must NOT import or depend on any LLM."""
    src = Path(red_flag_engine_mod.__file__).read_text(encoding="utf-8")
    forbidden = ["llm_provider", "clinical_extractor", "openai", "anthropic", "transformers", "google.genai"]
    for f in forbidden:
        assert f not in src, f"Forbidden LLM dependency '{f}' found in red_flag_engine.py source"
    
    # Check loaded module attributes
    assert not hasattr(red_flag_engine_mod, "llm_provider")
    assert not hasattr(red_flag_engine_mod, "get_llm")


def test_get_rules_endpoint(client):
    r = client.get("/api/safety/rules")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 10
    rule_ids = {rule["rule_id"] for rule in data}
    expected_starter_rules = {
        "CHEST_PAIN", "BREATHING_DIFFICULTY", "HEAVY_BLEEDING",
        "INFANT_FEVER", "UNCONSCIOUSNESS", "SEIZURE",
        "SEVERE_DEHYDRATION", "STROKE_SIGNS", "BLOOD_IN_VOMIT_STOOL",
        "PREGNANCY_BLEEDING"
    }
    assert expected_starter_rules.issubset(rule_ids)
    for rule in data:
        assert rule["review_status"] == "pending_clinical_review"


def test_safety_route_state_gate(client):
    from conftest import demo_session, demo_confirmed
    # CREATED state
    sid = demo_session(client, "A_ordinary")
    assert client.post("/api/safety/evaluate", json={"session_id": sid}).status_code == 409

    # NORMALIZED state
    client.post("/api/normalization", json={"session_id": sid})
    assert client.post("/api/safety/evaluate", json={"session_id": sid}).status_code == 409

    # CONFIRMED state (extraction not done yet) -> Must be 409
    sid2 = demo_confirmed(client, "A_ordinary")
    assert client.post("/api/safety/evaluate", json={"session_id": sid2}).status_code == 409

    # EXTRACTED state -> Must be 200 and transition to EVALUATED
    ext_res = client.post("/api/clinical/extract", json={"session_id": sid2})
    assert ext_res.status_code == 200
    eval_res = client.post("/api/safety/evaluate", json={"session_id": sid2})
    assert eval_res.status_code == 200
    assert eval_res.json()["engine"] == "deterministic-keyword-rules (no LLM)"


def test_safety_route_end_to_end(client):
    from conftest import demo_confirmed
    sid = demo_confirmed(client, "B_red_flag")
    client.post("/api/clinical/extract", json={"session_id": sid})
    body = client.post("/api/safety/evaluate", json={"session_id": sid}).json()
    assert {r["rule_id"] for r in body["triggered"]} == {"CHEST_PAIN", "BREATHING_DIFFICULTY"}
    assert "not mean the patient is safe" in body["notice_en"].lower()
    assert "Clinician assessment is required" in body["notice_en"]
