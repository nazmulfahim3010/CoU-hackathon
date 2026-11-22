"""Deterministic assembly of the bilingual doctor summary (no LLM call, purely rule-based)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas.clinical import BilingualField, ClinicalExtraction, Item
from app.schemas.safety import SafetyResponse
from app.schemas.summary import SummaryCard, SummarySection

LABEL_EN = "AI-assisted patient intake summary — clinician verification required."
LABEL_BN = "এআই-সহায়তায় তৈরি রোগীর প্রাথমিক তথ্যের সারসংক্ষেপ — চিকিৎসকের যাচাই আবশ্যক।"
DISCLAIMER_EN = "Kotha is not a diagnostic tool. Medical decisions must be made by a qualified healthcare professional."
DISCLAIMER_BN = "কথা কোনো রোগ নির্ণয়ের সরঞ্জাম নয়। চিকিৎসা সংক্রান্ত সব সিদ্ধান্ত যোগ্য স্বাস্থ্যসেবা পেশাদারকে নিতে হবে।"

NOT_REPORTED_EN = "Not reported"
NOT_REPORTED_BN = "বলা হয়নি"
UNCERTAIN_EN = "Uncertain: "
UNCERTAIN_BN = "অনিশ্চিত: "


def _field(key: str, en: str, bn: str, f: BilingualField, evidence: str | None = None) -> SummarySection:
    if f.status == "not_reported":
        return SummarySection(
            key=key,
            title_en=en,
            title_bn=bn,
            en=[NOT_REPORTED_EN],
            bn=[NOT_REPORTED_BN],
            status="not_reported",
            evidence=None,
        )
    pre_en, pre_bn = (UNCERTAIN_EN, UNCERTAIN_BN) if f.status == "uncertain" else ("", "")
    val_en = f.en or f.bn or ""
    val_bn = f.bn or f.en or ""
    return SummarySection(
        key=key,
        title_en=en,
        title_bn=bn,
        status=f.status,
        en=[pre_en + val_en],
        bn=[pre_bn + val_bn],
        evidence=evidence or val_bn,
    )


def _list(key: str, en: str, bn: str, items: list[Item], empty_label: tuple[str, str]) -> SummarySection:
    if not items:
        return SummarySection(
            key=key,
            title_en=en,
            title_bn=bn,
            en=[empty_label[0]],
            bn=[empty_label[1]],
            status="not_reported",
            evidence=None,
        )
    return SummarySection(
        key=key,
        title_en=en,
        title_bn=bn,
        en=[i.en for i in items],
        bn=[i.bn for i in items],
        status="list",
        evidence=", ".join(i.bn for i in items),
    )


def generate(
    session_id: str,
    mode: str,
    ext: ClinicalExtraction,
    safety: SafetyResponse,
    original: str,
    normalized: str,
    confirmed: str,
    provenance: dict[str, str],
) -> SummaryCard:
    """Builds the bilingual doctor summary deterministically from stored extraction, safety results, and transcripts."""
    none_stated = ("None explicitly stated", "স্পষ্টভাবে কিছু বলা হয়নি")
    sections = [
        _field("chief_complaint", "Chief complaint (patient-reported)", "প্রধান সমস্যা (রোগীর বক্তব্য)", ext.chief_complaint),
        _list("symptoms", "Symptoms", "লক্ষণসমূহ", ext.symptoms, (NOT_REPORTED_EN, NOT_REPORTED_BN)),
        _field("duration", "Duration", "সময়কাল", ext.duration),
        _field("severity", "Severity", "তীব্রতা", ext.severity),
        _field("history", "Relevant medical history", "প্রাসঙ্গিক চিকিৎসা ইতিহাস", ext.relevant_history),
        _field("medications", "Medications taken", "গৃহীত ওষুধ", ext.current_medications),
        _field("allergies", "Allergies (if reported)", "অ্যালার্জি (যদি বলা হয়)", ext.allergies),
        _list("associated", "Associated symptoms", "সংশ্লিষ্ট লক্ষণ", ext.associated_symptoms, none_stated),
        _list("negatives", "Important negative symptoms (explicitly denied)", "গুরুত্বপূর্ণ নেতিবাচক লক্ষণ (স্পষ্টভাবে অস্বীকৃত)", ext.negative_symptoms, none_stated),
        _list("uncertain", "Uncertain or missing information (\"Ask about…\")", "অনিশ্চিত বা অনুপস্থিত তথ্য (\"জিজ্ঞাসা করুন…\")", ext.uncertain_or_missing, none_stated),
        _list("model_noted", "Model-noted concerning phrases (hint only; not rule-evaluated)", "মডেল-চিহ্নিত উদ্বেগজনক বাক্যাংশ (শুধু ইঙ্গিত)", ext.model_noted_red_flag_indicators, none_stated),
    ]

    return SummaryCard(
        session_id=session_id,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        mode=mode,
        sections=sections,
        red_flags=safety.triggered,
        needs_information=safety.needs_information or safety.insufficient_information,
        original_statement=original,
        normalized_statement=normalized,
        confirmed_statement=confirmed,
        provenance=provenance,
        label_en=LABEL_EN,
        label_bn=LABEL_BN,
        disclaimer_en=DISCLAIMER_EN,
        disclaimer_bn=DISCLAIMER_BN,
    )
