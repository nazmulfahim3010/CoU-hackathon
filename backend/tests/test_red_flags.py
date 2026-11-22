import pytest

from app.services.red_flag_engine import evaluate, load_rules


def ids(text, bucket="triggered"):
    return {r.rule_id for r in getattr(evaluate("s", text), bucket)}


def test_chest_pain_and_breathing_trigger():
    t = "দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়।"
    assert ids(t) == {"CHEST_PAIN", "BREATHING_DIFFICULTY"}


@pytest.mark.parametrize("text,rule", [
    ("প্রচুর রক্ত পড়ছে", "HEAVY_BLEEDING"),
    ("রক্ত বমি করেছে", "VOMITING_BLOOD"),
    ("হঠাৎ অজ্ঞান হয়ে গেছে", "UNCONSCIOUSNESS"),
    ("খিঁচুনি হচ্ছে", "SEIZURE"),
    ("মুখ বেঁকে গেছে", "STROKE_SIGNS"),
    ("দুই মাসের বাচ্চার জ্বর", "INFANT_FEVER"),
    ("my father has chest pain", "CHEST_PAIN"),
])
def test_each_rule_triggers(text, rule):
    assert rule in ids(text)


def test_ordinary_symptoms_do_not_trigger():
    assert ids("তিন দিন ধরে মাথায় ব্যথা, অল্প জ্বর আছে।") == set()
    assert ids("পেটে মাঝে মাঝে ব্যথা করে, ওষুধ খাইনি।") == set()


def test_explicit_negation_is_not_a_trigger_but_is_reported():
    r = evaluate("s", "বুকে ব্যথা নেই, মাথা ব্যথা আছে")
    assert r.triggered == []
    assert [x.rule_id for x in r.negated] == ["CHEST_PAIN"]


def test_unrelated_negation_does_not_suppress_alert():
    # 'না' belongs to a different statement in the same clause; the alert must still fire
    assert "CHEST_PAIN" in ids("বুকে ব্যথা, খেতে পারছি না")
    assert "CHEST_PAIN" in ids("খুব বুকে ব্যথা কিন্তু কিছু খেতে পারছি না")


def test_affirmed_beats_negated_when_both_present():
    assert "CHEST_PAIN" in ids("বুকে ব্যথা নেই। আজ সকাল থেকে আবার বুকে ব্যথা হচ্ছে")


def test_infant_fever_without_age_needs_information():
    r = evaluate("s", "বাচ্চার জ্বর আছে")
    assert r.triggered == []
    assert [x.rule_id for x in r.needs_information] == ["INFANT_FEVER"]


def test_fever_without_infant_does_not_trigger_infant_rule():
    r = evaluate("s", "আমার জ্বর আছে")
    assert r.triggered == [] and r.needs_information == []


def test_missing_mention_is_not_negation():
    r = evaluate("s", "মাথা ব্যথা")
    assert r.negated == [] and r.triggered == []


def test_every_triggered_rule_carries_bilingual_guidance_and_no_medication():
    r = evaluate("s", "বুকে ব্যথা")
    x = r.triggered[0]
    assert x.explanation_bn and x.explanation_en and x.recommended_action_bn and x.recommended_action_en
    assert x.matched_text and x.clinically_reviewed is False
    for word in ("mg", "tablet", "take ", "ওষুধ খান"):
        assert word not in x.recommended_action_en.lower()


def test_ruleset_is_flagged_unreviewed():
    assert load_rules()["clinically_reviewed"] is False


def test_safety_route_end_to_end(client):
    from conftest import demo_confirmed
    sid = demo_confirmed(client, "B_red_flag")
    body = client.post("/api/safety/evaluate", json={"session_id": sid}).json()
    assert {r["rule_id"] for r in body["triggered"]} == {"CHEST_PAIN", "BREATHING_DIFFICULTY"}
    assert "NOT mean the patient is safe" in body["notice_en"]
