# Kotha (কথা) — 3-Minute Judge Demonstration Script

> **Event:** CoU AI Hackathon 2026  
> **Target Audience:** Hackathon Judges & Clinical Evaluators  
> **Total Time:** Exactly 3 Minutes (180 Seconds)  
> **Core Premise:** "Every voice deserves to be understood. Kotha turns rural dialect voice into safe, clinician-verified intake summaries."

---

## Pre-Demo Checklist (T-minus 5 Minutes)
- [ ] Backend running: `http://localhost:8000` (`python -m uvicorn app.main:app --port 8000`)
- [ ] Frontend running: `http://localhost:5173` (`npm run dev`)
- [ ] Browser window open to `http://localhost:5173`, maximized, audio unmuted.
- [ ] Network check: If venue Wi-Fi is shaky, stay on **Demo Mode** (`APP_MODE=demo`).

---

## 3-Minute Pitch & Demonstration Walkthrough

```
  0:00 - 0:30  ─── The Problem & Bangladesh Context
  0:30 - 1:00  ─── Dialect Speech & Intake (Scenario B)
  1:00 - 1:30  ─── Side-by-Side Review & Confirmation Gate
  1:30 - 2:00  ─── Deterministic Red Flags & Emergency Triage
  2:00 - 2:35  ─── Bilingual Doctor Summary Dashboard
  2:35 - 3:00  ─── Spoken Patient Reply & Safety Architecture
```

---

### Step 1: The Problem (0:00 – 0:30)
* **Visual:** Stand on the **Landing Page** (`/`). Scroll briefly to the *Dialects* and *8-Step Pipeline* sections.
* **Spoken Script (English/Bangla):**
  > "Honorable judges, over 170 million people speak Bengali, but in rural Bangladesh, patients don't speak textbook Bangla. In Sylhet, Chittagong, and Noakhali, a patient describing an emergency uses words like *'বুগত বিষ'* or *'ছাতিত ব্যতা'*.
  > 
  > Standard speech recognition models fail on regional phonetics and drop critical negation words like *'নাই'*. Worse, naive LLMs hallucinate diagnoses.
  > 
  > This is **Kotha (কথা)**: an AI-assisted dialect-to-clinical-note assistant with a **mandatory human confirmation gate** and a **zero-LLM deterministic safety engine**."

---

### Step 2: Intake & Audio Capture (0:30 – 1:00)
* **Action:** Click **"শুরু করুন (Start Intake)"** to go to `/intake`.
* **Visual:** Show the microphone interface, VU audio level meter, and dialect selector.
* **Demonstration Action:** Select **Demo Samples** -> **Scenario B (Red Flag — Chittagonian)**:
  * *"দুই ঘণ্টা ধরি বুগত খুব ব্যতা, নিঃশ্বাস নিতে কষ্ট অয়।"* (Severe chest pain & shortness of breath for 2 hours).
  * Click the Play Audio button to play the sample audio clip (`sample_B.wav`).
* **Spoken Script:**
  > "Here, a patient or community health worker in Chittagong speaks into the phone. Notice our live VU level meter and 90-second duration limiter.
  > 
  > For our demonstration, we'll select **Scenario B**, a patient presenting with severe acute chest tightness and dyspnea in Chittagonian dialect. Listen to the audio."

---

### Step 3: Dialect Normalization & The Confirmation Gate (1:00 – 1:30)
* **Action:** Click **"পরবর্তী (Process Audio)"** -> Lands on `/confirm`.
* **Visual:** Show the side-by-side comparison cards:
  * Left: **"আপনার কথা (মূল)"** — *দুই ঘণ্টা ধরি বুগত খুব ব্যতা, নিঃশ্বাস নিতে কষ্ট অয়।*
  * Right: **"প্রমিত বাংলা"** — *দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়।*
  * Highlighted terms: *বুগত* -> *বুকে*, *অয়* -> *হয়*.
* **Demonstration Action:**
  * Click **"সম্পাদনা করুন (Edit)"**. Modify a word (e.g. clarify *"খুব বেশি ব্যথা"*).
  * Tick the checkbox: *"আমি পড়েছি এবং এটি সঠিক (I have reviewed and confirmed)"*.
  * Click **"ঠিক আছে, নিশ্চিত করছি (Confirm & Proceed)"**.
* **Spoken Script:**
  > "Here is Kotha's most critical safety boundary: **The Patient Confirmation Gate**.
  > 
  > Our dialect normalizer matched regional terms using our longest-match glossary and guided LLM rewrite with negation-preservation guards.
  > 
  > But AI is never allowed to send data directly to the doctor without verification. The patient or health worker must review and confirm the text. Notice that our backend API enforces this—any direct attempt to extract clinical notes before confirmation throws an HTTP 409 Conflict."

---

### Step 4: Deterministic Red-Flag Safety Engine (1:30 – 2:00)
* **Action:** Automatically progresses through `/processing` to `/summary`.
* **Visual:** The top of the summary screen displays a prominent red emergency banner (`#C62828`):
  * **🚨 জরুরি সতর্কতা (Emergency Alert)**
  * Triggered Rules: `CHEST_PAIN` (*বুকে ব্যথা*) and `BREATHING_DIFFICULTY` (*শ্বাসকষ্ট*).
  * Recommended Action: *অবিলম্বে নিকটস্থ জরুরি চিকিৎসা কেন্দ্রে বা হাসপাতালে যান।* (Immediate emergency facility referral).
* **Spoken Script:**
  > "Look at the top of the screen: a high-priority red alert immediately fired.
  > 
  > Crucially: **No LLM made this safety decision.** 
  > Our red-flag engine is 100% deterministic, running keyword and clause-bounded negation rules. It detected acute chest pain and breathing distress and triggered emergency triage instructions without hallucination.
  > 
  > Notice our universal disclaimer: *'No alert does NOT mean safe'*. Kotha never shows a green 'safe' badge."

---

### Step 5: Bilingual Clinician Summary Dashboard (2:00 – 2:35)
* **Visual:** Toggle the language button from **"English"** to **"বাংলা"** and back.
* **Demonstration Action:**
  * Scroll through Chief Complaint, Symptoms, Duration (2 hours), Severity.
  * Show the **"Not Reported"** fields: Allergies and Medical History are greyed out as *Not Reported* (never assumed negative).
  * Show the **"Ask Patient (Uncertain / Missing)"** section.
  * Click **"প্রিন্ট / PDF"** to show the browser print dialog preview with clean clinical layout.
* **Spoken Script:**
  > "For the attending physician, the note is instant, structured, and bilingual. With one click, an English-speaking specialist or a Bangla-speaking resident sees Chief Complaint, duration, and severity.
  > 
  > Notice what Kotha did NOT do: it did not invent a diagnosis like 'Myocardial Infarction', and it did not prescribe Aspirin. Unmentioned items are explicitly marked *Not Reported*—never falsely inferred as absent."

---

### Step 6: Spoken Patient Reply & Safety Architecture (2:35 – 3:00)
* **Action:** Click the **Spoken Reply** audio player at the bottom:
  * Audio plays: *"আপনার কিছু জরুরি লক্ষণ চিহ্নিত হয়েছে। অনুগ্রহ করে অবিলম্বে কর্তব্যরত স্বাস্থ্যকর্মী বা চিকিৎসকের সাথে কথা বলুন।"*
* **Closing Words:**
  > "Finally, for illiterate or rural patients, Kotha synthesizes an immediate Bangla audio confirmation from a fixed, non-clinical template. No patient health data is ever sent to external TTS.
  > 
  > When the session ends, our zero-storage architecture purges all in-memory data.
  > 
  > Kotha bridges the dialect divide, protects patient safety, and saves lives in rural Bangladesh. Thank you!"

---

## Emergency Backup & Contingency Plans

| Failure Mode | Immediate Symptom | 5-Second Fix During Demo |
|---|---|---|
| **No Internet / Wi-Fi Drops** | Cloud LLM/STT fails with timeout or 502. | 1. Ensure the top toggle is set to **"Demo Mode"**.<br>2. All 3 scenarios (`A`, `B`, `C`) use bundled local WAV audio and pre-cached extractions.<br>3. Summary and red-flag rules run 100% locally on localhost without internet. |
| **Microphone Permission Blocked** | Browser blocks mic access on Chrome. | 1. Use the **"টাইপ করুন (Type text)"** tab on `/intake`.<br>2. Or click the **Demo Samples** tab to pick Scenario A, B, or C with zero microphone required. |
| **API Provider Rate Limit (429/401)** | Red error toast appears on transcription or normalization. | 1. Switch immediately to Demo Mode in the navbar switch.<br>2. Explain to judges: *"Our system gracefully handles provider downtime by isolating live external models from our deterministic core."* |
| **Audio Playback Silent** | Speaker/Bluetooth muted on presentation laptop. | The exact Bangla spoken template text is prominently rendered on screen directly below the audio player as a visual fallback. |
