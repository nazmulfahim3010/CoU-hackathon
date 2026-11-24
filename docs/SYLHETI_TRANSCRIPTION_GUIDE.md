# Sylheti Transcription & Clinical Normalization Guide

This guide establishes standard operating procedures for audio transcription, phonetic analysis, glossary matching, and clinician review of Sylheti speech within the **Kotha (কথা)** healthcare intake platform.

---

## 1. Phonetic & Linguistic Characteristics of Sylheti Speech

Sylheti (*সিলেটি*, ISO 639-3: `syl`) belongs to the Eastern Indo-Aryan language family. While closely related to Standard Colloquial Bengali (SCB), it possesses significant phonological, morphological, and lexical divergences that challenge standard Automatic Speech Recognition (ASR) pipelines.

### Key Phonetic Shifts

| Phonetic Process | Sylheti Form | Standard Bangla Equivalent | Clinical Example |
|:---|:---|:---|:---|
| **Spirantization: /pʰ/, /p/ → [ɸ], [f]** | ফানি (*fani*) | পানি (*pani*) | ফানি পিপাসা লাগের (*Pani pipasha lagchhe*) |
| **Spirantization: /tʃʰ/, /tʃ/ → [s]** | চাউল → চাউল / সাউল | চাল | চাউল খাইতে পারি না |
| **Aspiration Loss / De-aspiration: /bʰ/ → [b]** | ভালা (*bala*) | ভালো (*bhalo*) | শরীরটা ভালা নায় (*Shorirta bhalo na*) |
| **Velar Fricative: /kʰ/, /k/ → [x] / [h]** | খাইসিনা (*haisina*) | খাইনি (*khaini*) | কোনো ওষুধ খাইসিনা (*Kono oshudh khaini*) |
| **Dental / Retroflex Affrication** | পেটো (*peto*) | পেটে (*pete*) | পেটো বেদনা করের (*Pete byatha korchhe*) |
| **Glottal Stop / Tone Contour** | অইসে (*oise*) | হয়েছে (*hoyecche*) | বাইচাটার জ্বর অইসে (*Bacchatar jwor hoyecche*) |

### Morphological & Verbal Suffixes

1. **Continuous Aspect Marker (-er / -ar)**:
   - Sylheti: `করের` (*korer*), `লাগের` (*lager*), `যার` (*zar*), `বারর` (*baror*).
   - Standard Bangla: `করছে` (*korchhe*), `লাগছে` (*lagchhe*), `যাচ্ছে` (*yachhe*), `বের হচ্ছে` (*ber hochhe*).
2. **Inflected Negation Suffixes**:
   - Unlike Standard Bangla where negation is often pre-verbal or independent particle `না` / `নেই`, Sylheti frequently fuses negation into the finite verb:
     * `ফারিয়ার না` / `পাররাম না` (*parchhi na* - unable to)
     * `করসিনা` (*korini* - have not done)
     * `খাইসিনা` (*khaini* - have not eaten)
     * `নায়` (*na* - is not / no)

---

## 2. Common Transcription Pitfalls for ASR & Transcribers

1. **Non-Bangla Script Hallucinations**:
   - Zero-shot ASR models occasionally mistake spirantized Sylheti consonants for Icelandic, Welsh, or Latin characters (e.g. producing `"Ánvar fyrirðu..."`).
   - *Kotha Guard*: The `validate_bangla_script` filter deterministic check rejects any ASR output where Bangla script ratio < 50%, raising `ASR_NON_BANGLA` and presenting a clean typed fallback.
2. **Phonetic Spelling Ambiguity**:
   - For example, `বুক বেদনা` vs `বুকর বেদনা` vs `বুকে বেদনা`. Standard Bengali transcribers often instinctively "correct" the text to Standard Bangla during transcription. Transcribers must write the **exact regional expression spoken** in the original transcript field.
3. **Number & Duration Alteration**:
   - Speech recognition models sometimes elide numbers (e.g., hearing `দুই দিন ধরি` as `কয়েক দিন ধরি`). In clinical intake, durations are vital triage parameters.
4. **Invented Symptoms on Ambiguous Utterances**:
   - Low-amplitude audio or slurred speech can lead unconstrained LLM decoders to insert generic medical complaints (e.g., adding `বমি` or `জ্বর` when the patient only reported `মাথা ঘুরা`).
   - *Kotha Guard*: `invented_symptom` check strictly rejects any clinical symptom term in the normalized output that was not present in the original input or backed by a matched glossary item.

---

## 3. Glossary Matching Rules & Edge Cases

Kotha maintains a 120-entry team-verified clinical glossary (`sylheti_glossary_120-final.csv`). The matching engine enforces strict deterministic rules:

### A. Longest-Match-First Priority
Multi-word clinical phrases always take precedence over substrings or component words:
- Example: `বুকর বাম সাইডে বেদনা` (*syl_010*, left-sided chest pain)
  - Matches: `বুকর বাম সাইডে বেদনা` → `বাম পাশে বুকে ব্যথা`
  - Prevents premature matching of `বুক বেদনা` (*syl_009*) or single-word `বেদনা` (*syl_011*).

### B. Word Boundary Guard
Bengali words with grammatical case inflections (`-র`, `-তে`, `-য়ে`) must be isolated cleanly using Bengali Unicode boundary lookaheads `(?<![ঀ-৿])` and `(?![ঀ-৿])`. This prevents corrupting unrelated roots that share substrings.

### C. Category Preservation
Every matched term retains its semantic category:
- `symptom`: Clinical symptoms (e.g., `দম বন্ধ অইজার` → `দম বন্ধ হয়ে আসছে`)
- `pain_description`: Qualitative pain descriptors (e.g., `কুসাই কুসাই বেদনা` → `খোঁচা মারা ব্যথা`)
- `fever`: Fever and temperature expressions (e.g., `উতালা জ্বর` → `উচ্চ তাপমাত্রা`)
- `common_medical`: General medical and administrative terms (e.g., `সুই দেওয়া` → `ইনজেকশন দেওয়া`)

---

## 4. How to Add New Verified Terms

To add a new verified term to the Sylheti dialect glossary:

1. **Open the Canonical CSV**:
   - Location: `data/glossary/sylheti_glossary_120-final.csv`
2. **Add a Row Following the 13-Field Schema**:
   ```csv
   id,regional_expression,standard_bangla,english_meaning,dialect,category,example_sentence,source,contributor,verification_status,verified_by,verification_date,verification_note
   ```
   - **`id`**: Unique sequential identifier (`syl_121`, `syl_122`, etc.).
   - **`regional_expression`**: Spoken regional term in Bengali script.
   - **`standard_bangla`**: Clinically accurate Standard Colloquial Bangla equivalent.
   - **`english_meaning`**: Concise English translation for medical audit.
   - **`dialect`**: `sylheti`.
   - **`category`**: One of `body_part`, `symptom`, `pain_description`, `fever`, `time_expression`, `severity`, `common_medical`.
   - **`example_sentence`**: Realistic patient sentence demonstrating context.
   - **`source`**: Dataset origin or clinical recording.
   - **`contributor`**: Name of authoring team member.
   - **`verification_status`**: Set to `verified` only after dual-review.
   - **`verified_by`**: Named reviewer (e.g., `Fahim`, `Noyon`).
   - **`verification_date`**: `YYYY-MM-DD`.
   - **`verification_note`**: Explicit note explaining phonetic/clinical rationale.
3. **Synchronize JSON & Run Tests**:
   ```bash
   python backend/scripts/import_glossary.py --csv data/glossary/sylheti_glossary_120-final.csv
   pytest backend/tests/test_sylheti_glossary_120.py
   ```

---

## 5. Guidelines for Health Workers Reviewing Transcripts

Health workers and Community Healthcare Workers (CHCPs) play an indispensable verification role in the Kotha workflow.

### Review Checklist on Confirmation Screen

1. **Audio vs. Original Transcript Verification**:
   - Health worker plays the original audio clip via the UI audio player.
   - Check if any key symptom or word was omitted or truncated by background noise.
2. **Negation Accuracy**:
   - Verify that negated statements (`খাইসিনা` / `করসিনা` / `ভালা নায়`) were correctly captured as Standard Bangla negations (`খাইনি` / `করিনি` / `ভালো না`).
   - **Critical Safety Guard**: A negation inversion (changing "no fever" to "has fever" or vice-versa) directly alters the triage category.
3. **Numerical and Temporal Details**:
   - Check numbers (`এক`, `দুই`, `তিন`), frequencies (`দিনে দুইবার`), and durations (`তিন দিন ধরি`).
4. **Editable Confirmation**:
   - If the transcript or normalized text requires refinement, click **"সম্পাদনা করুন" (Edit)** to directly modify the text into Standard Bangla.
   - Downstream triage and doctor summaries update dynamically based solely on the confirmed text.
