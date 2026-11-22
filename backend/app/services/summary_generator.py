"""Deterministic assembly of the bilingual doctor summary (no additional model call)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.clinical import BilingualField, ClinicalExtraction, Item
from app.schemas.safety import SafetyResponse
from app.schemas.summary import SummaryCard, SummarySection

LABEL_EN = "AI-assisted patient intake summary — clinician verification required."
LABEL_BN = "এআই-সহায়তায় তৈরি রোগীর প্রাথমিক তথ্যের সারসংক্ষেপ — চিকিৎসকের যাচাই আবশ্যক।"
DISCLAIMER_EN = "Kotha is not a diagnostic tool. Medical decisions must be made by a qualified healthcare professional."
DISCLAIMER_BN = "কথা কোনো রোগ নির্ণয়ের সরঞ্জাম নয়। চিকিৎসা সংক্রান্ত সব সিদ্ধান্ত যোগ্য স্বাস্থ্যসেবা পেশাদারকে নিতে হবে।"

NOT_REPORTED = ("Not reported", "বলা হয়নি")
UNCERTAIN = ("Uncertain: ", "অনিশ্চিত: ")


def _field(key: str, en: str, bn: str, f: BilingualField) -> SummarySection:
    if f.status == "not_reported":
        return SummarySection(key=key, title_en=en, title_bn=bn, en=[NOT_REPORTED[0]], bn=[NOT_REPORTED[1]], status=f.status)
    pre_en, pre_bn = UNCERTAIN if f.status == "uncertain" else ("", "")
    return SummarySection(key=key, title_en=en, title_bn=bn, status=f.status,
                          en=[pre_en + (f.en or f.bn or "")], bn=[pre_bn + (f.bn or f.en or "")])


def _list(key: str, en: str, bn: str, items: list[Item], empty: tuple[str, str]) -> SummarySection:
    if not items:
        return SummarySection(key=key, title_en=en, title_bn=bn, en=[empty[0]], bn=[empty[1]], status="not_reported")
    return SummarySection(key=key, title_en=en, title_bn=bn, en=[i.en for i in items], bn=[i.bn for i in items], status="list")


def generate(session_id: str, mode: str, ext: ClinicalExtraction, safety: SafetyResponse,
             original: str, normalized: str, provenance: dict[str, str]) -> SummaryCard:
    none_stated = ("None explicitly stated", "স্পষ্টভাবে কিছু বলা হয়নি")
    sections = [
        _field("chief_complaint", "Chief complaint (patient-reported)", "প্রধান সমস্যা (রোগীর বক্তব্য)", ext.chief_complaint),
        _list("symptoms", "Symptoms", "লক্ষণসমূহ", ext.symptoms, NOT_REPORTED),
        _field("duration", "Duration", "সময়কাল", ext.duration),
        _field("severity", "Severity", "তীব্রতা", ext.severity),
        _field("history", "Relevant medical history", "প্রাসঙ্গিক চিকিৎসা ইতিহাস", ext.relevant_history),
        _field("medications", "Medications taken", "গৃহীত ওষুধ", ext.current_medications),
        _field("allergies", "Allergies (if reported)", "অ্যালার্জি (যদি বলা হয়)", ext.allergies),
        _list("associated", "Associated symptoms", "সংশ্লিষ্ট লক্ষণ", ext.associated_symptoms, none_stated),
        _list("negatives", "Important negative symptoms (explicitly denied)", "গুরুত্বপূর্ণ নেতিবাচক লক্ষণ (স্পষ্টভাবে অস্বীকৃত)", ext.negative_symptoms, none_stated),
        _list("uncertain", "Uncertain or missing information", "অনিশ্চিত বা অনুপস্থিত তথ্য", ext.uncertain_or_missing, none_stated),
        _list("model_noted", "Model-noted concerning phrases (hint only; not rule-evaluated)", "মডেল-চিহ্নিত উদ্বেগজনক বাক্যাংশ (শুধু ইঙ্গিত)", ext.model_noted_red_flag_indicators, none_stated),
    ]
    return SummaryCard(
        session_id=session_id,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        mode=mode, sections=sections,
        red_flags=safety.triggered, needs_information=safety.needs_information,
        original_statement=original, normalized_statement=normalized, provenance=provenance,
        label_en=LABEL_EN, label_bn=LABEL_BN, disclaimer_en=DISCLAIMER_EN, disclaimer_bn=DISCLAIMER_BN,
    )
