"""Grounding: every extracted clinical claim must be traceable to the patient's own confirmed words.

This is deterministic code (no LLM). It enforces, after the LLM has produced a structured extraction:
  1. each reported item carries a VERBATIM evidence quote that really occurs in the confirmed text;
  2. a known symptom is never named unless the patient's confirmed text actually mentions it
     (so "মাথাত বেদনা" can never turn into a chest-pain entry);
  3. anything that fails is NOT silently kept: list items are removed and recorded for the clinician,
     and single fields are demoted to 'uncertain' (or cleared if they name a symptom the patient never said).
"""
from __future__ import annotations

import re

from app.schemas.clinical import BilingualField, ClinicalExtraction, Item
from app.services.glossary_service import clean_text

# Symptom groups: all the spellings/variants that count as "the patient mentioned this symptom".
SYMPTOM_GROUPS: dict[str, tuple[str, ...]] = {
    "head_pain": ("মাথাব্যথা", "মাথা ব্যথা", "মাথায় ব্যথা", "মাথাত বেদনা"),
    "chest_pain": ("বুকে ব্যথা", "বুক ব্যথা", "বুক বেদনা", "বুকে বেদনা", "বুকুত বেদনা", "বুকের ব্যথা", "বুকর বাম সাইডে বেদনা", "বুকর বেদনা"),
    "stomach_pain": ("পেটে ব্যথা", "পেট ব্যথা", "পেটো বেদনা", "পেটের ব্যথা"),
    "breathing": ("শ্বাসকষ্ট", "শ্বাস কষ্ট", "শ্বাস নিতে কষ্ট", "নিঃশ্বাস নিতে কষ্ট", "দম বন্ধ", "দম নিতে কষ্ট"),
    "vomiting": ("বমি", "উটকা"),
    "cough": ("কাশি", "কাওয়ানি"),
    "diarrhoea": ("ডায়রিয়া", "পাতলা পায়খানা", "পাতলা আগা"),
    "seizure": ("খিঁচুনি", "খিচুনি", "মিরগি"),
    "fainting": ("অজ্ঞান",),
    "bleeding": ("রক্ত",),
    "fever": ("জ্বর", "তাফ"),
}

_PUNCT = re.compile(r"[।,.;:?!\"'()\[\]{}\-‐‑–—]")


def squash(text: str) -> str:
    """Comparison form: NFC, no zero-width chars, no punctuation, no whitespace."""
    return re.sub(r"\s+", "", _PUNCT.sub(" ", clean_text(text or "")))


def evidence_is_verbatim(evidence: str | None, confirmed_squashed: str) -> bool:
    ev = squash(evidence or "")
    return len(ev) >= 2 and ev in confirmed_squashed


def symptoms_named_but_never_said(text: str | None, confirmed_squashed: str) -> list[str]:
    """Symptom groups that `text` names but the confirmed statement never mentions (any variant)."""
    t = squash(text or "")
    missing = []
    for group, variants in SYMPTOM_GROUPS.items():
        sq = [squash(v) for v in variants]
        if any(v in t for v in sq) and not any(v in confirmed_squashed for v in sq):
            missing.append(group)
    return missing


def _item_problem(item: Item, confirmed_sq: str) -> str | None:
    if not evidence_is_verbatim(item.evidence, confirmed_sq):
        return "no verbatim evidence in the patient's words"
    never_said = symptoms_named_but_never_said(item.bn, confirmed_sq)
    if never_said:
        return f"names a symptom the patient never said ({', '.join(never_said)})"
    return None


def _ground_list(items: list[Item], confirmed_sq: str) -> tuple[list[Item], list[Item]]:
    kept, removed = [], []
    for it in items:
        problem = _item_problem(it, confirmed_sq)
        (removed if problem else kept).append(it)
    return kept, removed


_SCALARS = (
    ("chief_complaint", "Chief complaint", "প্রধান সমস্যা"),
    ("duration", "Duration", "সময়কাল"),
    ("severity", "Severity", "তীব্রতা"),
    ("relevant_history", "Medical history", "চিকিৎসা ইতিহাস"),
    ("current_medications", "Medications", "ওষুধ"),
    ("allergies", "Allergies", "অ্যালার্জি"),
)


def ground_extraction(ext: ClinicalExtraction, confirmed_text: str) -> ClinicalExtraction:
    """Return a grounded copy of `ext`. Idempotent. Never invents anything; only removes or demotes."""
    sq = squash(confirmed_text)
    data = ext.model_copy(deep=True)
    removed: list[Item] = list(data.removed_ungrounded)
    uncertain: list[Item] = list(data.uncertain_or_missing)

    for name, title_en, title_bn in _SCALARS:
        f: BilingualField = getattr(data, name)
        if f.status == "not_reported":
            continue
        if symptoms_named_but_never_said(f.bn, sq):
            # e.g. a chief complaint naming a symptom the patient never mentioned: drop, never keep
            removed.append(Item(bn=f.bn or f.en or "?", en=f.en or f.bn or "?", evidence=f.evidence))
            setattr(data, name, BilingualField(status="not_reported"))
            continue
        if not evidence_is_verbatim(f.evidence, sq):
            # keep the value but it is no longer presented as a reported fact
            setattr(data, name, BilingualField(status="uncertain", bn=f.bn, en=f.en))
            uncertain.append(
                Item(
                    bn=f"“{title_bn}” রোগীর নিজের কথার সঙ্গে মেলানো যায়নি — যাচাই করুন",
                    en=f"“{title_en}” could not be matched to the patient's own words — please verify",
                )
            )

    for list_name in ("symptoms", "associated_symptoms", "negative_symptoms", "model_noted_red_flag_indicators"):
        kept, dropped = _ground_list(getattr(data, list_name), sq)
        setattr(data, list_name, kept)
        removed.extend(dropped)

    data.removed_ungrounded = _dedupe(removed)
    data.uncertain_or_missing = _dedupe(uncertain)
    return data


def _dedupe(items: list[Item]) -> list[Item]:
    seen, out = set(), []
    for it in items:
        key = (it.bn, it.en)
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def describe_problems(before: ClinicalExtraction, after: ClinicalExtraction) -> list[str]:
    """Human-readable list of what grounding changed (used as retry feedback to the LLM)."""
    notes = [f"removed: {i.bn!r} (evidence {i.evidence!r} not found in the patient's words)" for i in after.removed_ungrounded
             if i not in before.removed_ungrounded]
    for name, _, _ in _SCALARS:
        b, a = getattr(before, name), getattr(after, name)
        if b.status != a.status:
            notes.append(f"{name}: evidence {b.evidence!r} not found in the patient's words")
    return notes
