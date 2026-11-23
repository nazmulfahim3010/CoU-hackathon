import { expect, test, type Page } from '@playwright/test'

const MOCK_SAMPLES = [
  {
    id: 'B_red_flag',
    scenario: 'B_red_flag',
    audio_file: 'sample_B.wav',
    audio_url: '/api/demo/audio/sample_B.wav',
    title: 'Scenario B — Red-flag symptoms',
    purpose: 'Chest pain with breathing difficulty; deterministic rules should trigger.',
    dialect: 'chittagonian (illustrative)',
    speaker: 'Synthetic standard-Bangla voice (gTTS), not a native dialect speaker',
    original_transcript: 'দুই ঘণ্টা ধরি বুগত খুব ব্যতা, নিঃশ্বাস নিতে কষ্ট অয়।',
    standard_bangla: 'দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়।',
    verified_by: 'Fictional scenario — synthetic demo audio',
  },
]

const MOCK_SUMMARY = {
  session_id: 'e2e-session-123',
  generated_at: new Date().toISOString(),
  mode: 'demo',
  sections: [
    {
      key: 'chief_complaint',
      title_en: 'Chief complaint (patient-reported)',
      title_bn: 'প্রধান সমস্যা (রোগীর বক্তব্য)',
      en: ['Chest pain'],
      bn: ['বুকে ব্যথা'],
      status: 'reported',
      evidence: 'বুকে খুব ব্যথা',
    },
    {
      key: 'symptoms',
      title_en: 'Symptoms',
      title_bn: 'লক্ষণসমূহ',
      en: ['Chest pain', 'Difficulty breathing'],
      bn: ['বুকে ব্যথা', 'নিঃশ্বাস নিতে কষ্ট'],
      status: 'reported',
      evidence: 'বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়',
    },
    {
      key: 'duration',
      title_en: 'Duration',
      title_bn: 'সময়কাল',
      en: ['Two hours'],
      bn: ['দুই ঘণ্টা'],
      status: 'reported',
      evidence: 'দুই ঘণ্টা ধরে',
    },
    {
      key: 'severity',
      title_en: 'Severity',
      title_bn: 'তীব্রতা',
      en: ['Severe'],
      bn: ['খুব'],
      status: 'reported',
      evidence: 'খুব ব্যথা',
    },
    {
      key: 'history',
      title_en: 'Relevant medical history',
      title_bn: 'প্রাসঙ্গিক চিকিৎসা ইতিহাস',
      en: ['Not reported'],
      bn: ['বলা হয়নি'],
      status: 'not_reported',
    },
    {
      key: 'medications',
      title_en: 'Medications taken',
      title_bn: 'গৃহীত ওষুধ',
      en: ['Not reported'],
      bn: ['বলা হয়নি'],
      status: 'not_reported',
    },
    {
      key: 'allergies',
      title_en: 'Allergies (if reported)',
      title_bn: 'অ্যালার্জি (যদি বলা হয়)',
      en: ['Not reported'],
      bn: ['বলা হয়নি'],
      status: 'not_reported',
    },
    {
      key: 'associated',
      title_en: 'Associated symptoms',
      title_bn: 'সংশ্লিষ্ট লক্ষণ',
      en: ['None explicitly stated'],
      bn: ['স্পষ্টভাবে কিছু বলা হয়নি'],
      status: 'not_reported',
    },
    {
      key: 'negatives',
      title_en: 'Important negative symptoms (explicitly denied)',
      title_bn: 'গুরুত্বপূর্ণ নেতিবাচক লক্ষণ (স্পষ্টভাবে অস্বীকৃত)',
      en: ['None explicitly stated'],
      bn: ['স্পষ্টভাবে কিছু বলা হয়নি'],
      status: 'not_reported',
    },
    {
      key: 'uncertain',
      title_en: 'Uncertain or missing information ("Ask about…")',
      title_bn: 'অনিশ্চিত বা অনুপস্থিত তথ্য ("জিজ্ঞাসা করুন…")',
      en: ['Pain radiation and medical history unknown'],
      bn: ['ব্যথা ছড়িয়ে পড়ছে কি না এবং পূর্ববর্তী রোগের ইতিহাস জানা নেই'],
      status: 'uncertain',
    },
    {
      key: 'model_noted',
      title_en: 'Model-noted concerning phrases',
      title_bn: 'মডেল-চিহ্নিত বাক্যাংশ',
      en: ['Chest pain', 'Breathing difficulty'],
      bn: ['বুকে ব্যথা', 'শ্বাসকষ্ট'],
      status: 'reported',
    },
  ],
  red_flags: [
    {
      rule_id: 'CHEST_PAIN',
      status: 'triggered',
      alert_level: 'urgent',
      name_en: 'Chest pain or chest pressure',
      name_bn: 'বুকে ব্যথা বা চাপ',
      explanation_en: 'Patient reported chest pain. Rule-based urgent triage indicator.',
      explanation_bn: 'রোগীর বক্তব্যে বুকে ব্যথার উল্লেখ রয়েছে। জরুরি সতর্কতা।',
      recommended_action_en: 'Seek immediate clinical evaluation at nearest health facility.',
      recommended_action_bn: 'নিকটস্থ স্বাস্থ্যকেন্দ্রে অবিলম্বে যোগাযোগ করুন।',
      required_information: ['Onset and duration', 'Radiation to arm or jaw'],
      matched_text: ['বুকে খুব ব্যথা'],
      matched_span: 'বুকে খুব ব্যথা',
      clinically_reviewed: false,
    },
    {
      rule_id: 'BREATHING_DIFFICULTY',
      status: 'triggered',
      alert_level: 'emergency',
      name_en: 'Difficulty breathing or shortness of breath',
      name_bn: 'শ্বাসকষ্ট বা শ্বাস নিতে সমস্যা',
      explanation_en: 'Patient reported difficulty breathing. Immediate emergency assessment required.',
      explanation_bn: 'শ্বাসকষ্টের লক্ষণ চিহ্নিত হয়েছে।',
      recommended_action_en: 'Immediate emergency evaluation required.',
      recommended_action_bn: 'জরুরি বিভাগে সরাসরি যোগাযোগ করুন।',
      required_information: ['Onset', 'Lip or face colour change'],
      matched_text: ['নিঃশ্বাস নিতে কষ্ট হয়'],
      matched_span: 'নিঃশ্বাস নিতে কষ্ট হয়',
      clinically_reviewed: false,
    },
  ],
  needs_information: [],
  original_statement: 'দুই ঘণ্টা ধরি বুগত খুব ব্যতা, নিঃশ্বাস নিতে কষ্ট অয়।',
  normalized_statement: 'দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়।',
  confirmed_statement: 'দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়। (রোগীর যাচাইকৃত)',
  provenance: {
    speech_to_text: 'demo_sample',
    normalization: 'LLM + Dialect Glossary',
    clinical_extraction: 'LLM structured extraction',
    red_flags: 'deterministic rules (no LLM)',
  },
  label_en: 'AI-assisted patient intake summary — clinician verification required.',
  label_bn: 'এআই-সহায়তায় তৈরি রোগীর প্রাথমিক তথ্যের সারসংক্ষেপ — চিকিৎসকের যাচাই আবশ্যক।',
  disclaimer_en: 'Kotha is not a diagnostic tool. Medical decisions must be made by a qualified healthcare professional.',
  disclaimer_bn: 'কথা কোনো রোগ নির্ণয়ের সরঞ্জাম নয়। চিকিৎসা সংক্রান্ত সব সিদ্ধান্ত যোগ্য স্বাস্থ্যসেবা পেশাদারকে নিতে হবে।',
}

async function setupMockApiRoutes(page: Page) {
  await page.route('**/api/health', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'ok',
        live_mode_ready: true,
        providers: {
          speech: { configured: true, provider: 'whisper', model: 'large-v3' },
          llm: { configured: true, provider: 'gemini' },
          tts: { configured: true, provider: 'gtts' },
        },
      }),
    }),
  )

  await page.route('**/api/glossary/stats', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total: 35,
        verified: 0,
        unverified: 35,
        by_dialect: { sylheti: { total: 12, verified: 0, unverified: 12 } },
        by_category: {},
      }),
    }),
  )

  await page.route('**/api/demo/samples', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_SAMPLES),
    }),
  )

  await page.route('**/api/demo/audio/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'audio/wav',
      body: Buffer.from(
        'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00',
      ),
    }),
  )

  await page.route('**/api/demo/live-asr', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        sample_id: 'B_red_flag',
        transcript: 'দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়।',
        source: 'speech_recognition',
        provider: 'whisper',
        model: 'openai/whisper-large-v3',
        mode: 'live',
      }),
    }),
  )

  await page.route('**/api/transcription', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'e2e-session-123',
        mode: 'demo',
        transcript: 'দুই ঘণ্টা ধরি বুগত খুব ব্যতা, নিঃশ্বাস নিতে কষ্ট অয়।',
        source: 'demo_sample',
        provider: 'demo',
        model: null,
        duration_seconds: 5.2,
        confidence: null,
        disclaimer: 'DEMO: prepared sample text. This was NOT produced by speech recognition.',
      }),
    }),
  )

  await page.route('**/api/normalization', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'e2e-session-123',
        original: 'দুই ঘণ্টা ধরি বুগত খুব ব্যতা, নিঃশ্বাস নিতে কষ্ট অয়।',
        normalized: 'দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়।',
        source: 'demo_prepared',
        glossary_matches: [
          {
            regional: 'বুগত',
            standard: 'বুকে',
            english: 'in the chest',
            dialect: 'chittagonian',
            category: 'body_part',
            verification: 'unverified',
          },
        ],
        changes: [
          {
            original: 'বুগত',
            normalized: 'বুকে',
            reason: 'Glossary match (body_part)',
            source: 'glossary',
          },
        ],
        uncertain_segments: [],
        uncertain_spans: ['বুগত'],
        warnings: [],
        provider: 'demo',
        disclaimer: 'Advisory only.',
        mode: 'demo',
      }),
    }),
  )

  await page.route('**/api/confirmation', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'e2e-session-123',
        stage: 'confirmed',
        confirmed_text: 'দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়। (রোগীর যাচাইকৃত)',
        edited_by_patient: true,
        confirmed_by: 'patient',
        warnings: [],
        mode: 'demo',
      }),
    }),
  )

  await page.route('**/api/clinical/extract', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'e2e-session-123',
        source: 'demo_prepared',
        provider: 'demo',
        extraction: {},
        note: 'DEMO note',
        mode: 'demo',
      }),
    }),
  )

  await page.route('**/api/safety/evaluate', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'e2e-session-123',
        triggered: MOCK_SUMMARY.red_flags,
        explicitly_denied: [],
        insufficient_information: [],
        not_mentioned: [],
        negated: [],
        needs_information: [],
        rules_evaluated: 10,
        ruleset_version: '1.0-draft',
        engine: 'deterministic-keyword-rules (no LLM)',
        notice_en: 'Deterministic notice',
        notice_bn: 'বিজ্ঞপ্তি',
        mode: 'demo',
      }),
    }),
  )

  await page.route('**/api/summary/generate', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_SUMMARY),
    }),
  )

  await page.route('**/api/speech/generate', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'e2e-session-123',
        text_bn: 'আপনার কথা গ্রহণ করা হয়েছে। আপনার তথ্যে জরুরি কিছু লক্ষণ দেখা গেছে। অবিলম্বে নিকটস্থ হাসপাতালে যান।',
        audio_base64: 'SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//OEAAAAAAAAAAAAAAAAAAAAAAA=',
        mime_type: 'audio/mpeg',
        provider: 'gtts',
        mode: 'demo',
      }),
    }),
  )

  await page.route('**/api/speech/text/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        text_bn: 'আপনার কথা গ্রহণ করা হয়েছে। আপনার তথ্যে জরুরি কিছু লক্ষণ দেখা গেছে। অবিলম্বে নিকটস্থ হাসপাতালে যান।',
      }),
    }),
  )
}

test.describe('End-to-End Workflow Sequence (Mocked Providers)', () => {
  test('full sequence in demo mode: sample pick -> transcribe -> normalize -> edit -> confirm -> extract -> safety -> summary -> spoken reply', async ({
    page,
  }) => {
    await setupMockApiRoutes(page)

    // 1. Visit landing page
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /Every Voice Deserves to Be Understood/ })).toBeVisible()

    // 2. Click Start Voice Consultation
    await page.getByRole('link', { name: /Start Voice Consultation/ }).click()
    await expect(page).toHaveURL(/.*\/intake/)

    // 3. Switch to Demo samples
    await page.getByRole('button', { name: 'Demo samples' }).click()
    await expect(page.getByText('Scenario B — Red-flag symptoms')).toBeVisible()

    // 4. Click Use this sample
    await page.getByRole('button', { name: /Use this sample/ }).click()

    // 5. Lands on Review / Confirm screen after automatic transcription & normalization
    await expect(page).toHaveURL(/.*\/(review|confirm)/)
    await expect(page.getByRole('heading', { name: /আপনার কথা যাচাই ও নিশ্চিতকরণ/ })).toBeVisible()
    await expect(page.getByText('Demo sample (ডেমো নমুনা)')).toBeVisible()

    // 6. Edit confirmed text directly in textarea
    const textarea = page.getByRole('textbox', { name: /Standard Bangla transcript/i })
    await textarea.fill('দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়। (রোগীর যাচাইকৃত)')

    // 7. Verify checkbox & confirm
    const checkbox = page.getByRole('checkbox')
    await checkbox.check()
    const confirmBtn = page.getByRole('button', { name: /ঠিক আছে, নিশ্চিত করছি/ })
    await expect(confirmBtn).toBeEnabled()
    await confirmBtn.click()

    // 8. Processing completes and navigates to summary
    await expect(page).toHaveURL(/.*\/summary/, { timeout: 15_000 })
    await expect(page.getByRole('heading', { name: /Doctor Summary Dashboard|চিকিৎসকের সারসংক্ষেপ/ })).toBeVisible()

    // Verify Red Flag Alerts are prominently rendered
    const redFlagPanel = page.getByTestId('red-flag-panel')
    await expect(redFlagPanel).toBeVisible()
    await expect(redFlagPanel).toContainText('Chest pain')
    await expect(redFlagPanel).toContainText('Difficulty breathing')

    // 9. Generate and play spoken guidance reply
    const listenBtn = page.getByRole('button', { name: /উত্তর শুনুন/ })
    await listenBtn.click()
    await expect(page.getByTestId('spoken-text')).toBeVisible()
    await expect(page.getByTestId('spoken-text')).toContainText('নিকটস্থ হাসপাতালে যান')
  })

  test('full sequence with fake microphone audio capture: record -> stop -> submit -> confirm -> summary', async ({
    page,
  }) => {
    await setupMockApiRoutes(page)

    await page.goto('/intake')
    await expect(page.getByRole('button', { name: /রেকর্ড শুরু করুন/ })).toBeVisible()

    // 1. Click Record button (fake media stream active via chromium flags)
    await page.getByRole('button', { name: /রেকর্ড শুরু করুন/ }).click()
    await expect(page.getByRole('button', { name: /থামান/ })).toBeVisible()

    // Wait 1.5s for audio collection in fake recorder
    await page.waitForTimeout(1500)

    // 2. Click Stop button
    await page.getByRole('button', { name: /থামান/ }).click()

    // 3. Audio review section appears
    await expect(page.getByText(/আপনার রেকর্ডিং শুনে দেখুন/)).toBeVisible()
    const submitBtn = page.getByRole('button', { name: /Use this recording/ })
    await expect(submitBtn).toBeVisible()
    await submitBtn.click()

    // 4. Lands on Confirm screen
    await expect(page).toHaveURL(/.*\/(review|confirm)/)
    await expect(page.getByRole('heading', { name: /আপনার কথা যাচাই ও নিশ্চিতকরণ/ })).toBeVisible()

    // 5. Confirm directly
    await page.getByRole('checkbox').check()
    await page.getByRole('button', { name: /ঠিক আছে, নিশ্চিত করছি/ }).click()

    // 6. Navigates to summary
    await expect(page).toHaveURL(/.*\/summary/, { timeout: 15_000 })
    await expect(page.getByTestId('red-flag-panel')).toBeVisible()
  })
})

test.describe('Live Backend Integration (@live)', () => {
  test('end-to-end flow with real backend providers @live', async ({ page, request }) => {
    // Check if backend is alive
    let backendUp = false
    try {
      const res = await request.get('http://127.0.0.1:8000/api/health')
      backendUp = res.ok()
    } catch {
      backendUp = false
    }

    test.skip(!backendUp, 'Live backend not running on http://127.0.0.1:8000')

    await page.goto('/')
    await page.getByRole('link', { name: /Start Voice Consultation/ }).click()
    await expect(page).toHaveURL(/.*\/intake/)

    // Switch to demo mode
    await page.getByRole('button', { name: 'Demo samples' }).click()
    await expect(page.getByText(/Scenario A — Ordinary symptoms/)).toBeVisible()

    // Pick Scenario A
    const useBtns = page.getByRole('button', { name: /Use this sample/ })
    await useBtns.first().click()

    // Wait for confirmation page
    await expect(page).toHaveURL(/.*\/(review|confirm)/, { timeout: 15_000 })
    await expect(page.getByRole('heading', { name: /আপনার কথা যাচাই ও নিশ্চিতকরণ/ })).toBeVisible()

    // Confirm
    await page.getByRole('checkbox').check()
    await page.getByRole('button', { name: /ঠিক আছে, নিশ্চিত করছি/ }).click()

    // Wait for summary
    await expect(page).toHaveURL(/.*\/summary/, { timeout: 15_000 })
    await expect(page.getByTestId('ai-label')).toBeVisible()
  })
})
