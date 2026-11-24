import { expect, test, type Page } from '@playwright/test'
import * as path from 'path'
import * as fs from 'fs'

const SCREENSHOT_DIR = 'C:/Users/ASUS/.gemini/antigravity/brain/5ee6cc71-8361-4ef5-89a1-3ca8b379ea6a/screenshots'

// Ensure screenshot directory exists
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
}

const VIEWPORTS = [
  { name: '360px', width: 360, height: 800 },
  { name: '768px', width: 768, height: 1024 },
  { name: '1280px', width: 1280, height: 800 },
  { name: '1920px', width: 1920, height: 1080 },
]

const MOCK_SAMPLES = [
  {
    id: 'sample_sylheti_01',
    scenario: 'B_red_flag',
    audio_file: 'sample_sylheti_01.wav',
    audio_url: '/api/demo/audio/sample_sylheti_01.wav',
    title: 'Scenario B — Red-flag symptoms',
    purpose: 'Chest pain and breathing difficulty',
    dialect: 'sylheti',
    speaker: 'Native Sylheti speaker',
    original_transcript: 'দুই ঘণ্টা ধরি বুগত খুব ব্যতা, নিঃশ্বাস নিতে কষ্ট অয়।',
    standard_bangla: 'দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়।',
    verified_by: 'team-verified',
  },
]

const MOCK_SUMMARY = {
  session_id: 'e2e-session-responsive',
  generated_at: new Date().toISOString(),
  mode: 'demo',
  sections: [
    {
      key: 'chief_complaint',
      title_en: 'Chief complaint',
      title_bn: 'প্রধান সমস্যা',
      en: ['Chest pain', 'Breathing difficulty'],
      bn: ['বুকে ব্যথা', 'শ্বাসকষ্ট'],
      status: 'reported',
      evidence: 'বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়',
    },
    {
      key: 'duration',
      title_en: 'Duration & onset',
      title_bn: 'সময়কাল ও শুরু',
      en: ['2 hours'],
      bn: ['২ ঘণ্টা'],
      status: 'reported',
      evidence: 'দুই ঘণ্টা ধরে',
    },
    {
      key: 'history',
      title_en: 'Relevant medical history',
      title_bn: 'প্রাসঙ্গিক চিকিৎসা ইতিহাস',
      en: ['Hypertension reported'],
      bn: ['উচ্চ রক্তচাপ রয়েছে'],
      status: 'reported',
    },
    {
      key: 'uncertain',
      title_en: 'Uncertain or missing information ("Ask about…")',
      title_bn: 'অনিশ্চিত বা অনুপস্থিত তথ্য ("জিজ্ঞাসা করুন…")',
      en: ['Pain radiation and current medications unknown'],
      bn: ['ব্যথা অন্যত্র ছড়াচ্ছে কি না এবং বর্তমান ওষুধের তথ্য জানা নেই'],
      status: 'uncertain',
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
  disclaimer_en: 'Kotha is an experimental communication aid, not a diagnostic device.',
  disclaimer_bn: 'কথা একটি পরীক্ষামূলক যোগাযোগের মাধ্যম, কোনো রোগ নির্ণয়কারী চিকিৎসা সরঞ্জাম নয়।',
}

async function setupMocks(page: Page) {
  await page.route('**/api/health', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'ok',
        version: '0.1.0',
        live_mode_ready: true,
        providers: {
          speech: { configured: true, provider: 'whisper', model: 'openai/whisper-large-v3' },
          llm: { configured: true, provider: 'openai', model: 'gpt-4o' },
          tts: { configured: true, provider: 'gtts' },
        },
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

  await page.route('**/api/transcription', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'e2e-session-responsive',
        mode: 'demo',
        transcript: 'দুই ঘণ্টা ধরি বুগত খুব ব্যতা, নিঃশ্বাস নিতে কষ্ট অয়।',
        source: 'demo_sample',
        provider: 'demo',
        duration_seconds: 4.5,
      }),
    }),
  )

  await page.route('**/api/normalization', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'e2e-session-responsive',
        original: 'দুই ঘণ্টা ধরি বুগত খুব ব্যতা, নিঃশ্বাস নিতে কষ্ট অয়।',
        normalized: 'দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়।',
        source: 'demo_prepared',
        glossary_matches: [
          {
            regional: 'বুগত',
            standard: 'বুকে',
            english: 'in chest',
            dialect: 'sylheti',
            category: 'body_part',
            verification: 'verified',
          },
        ],
        changes: [],
        uncertain_segments: [],
        uncertain_spans: [],
        warnings: [],
        mode: 'demo',
      }),
    }),
  )

  await page.route('**/api/confirmation', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'e2e-session-responsive',
        stage: 'confirmed',
        confirmed_text: 'দুই ঘণ্টা ধরে বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়। (রোগীর যাচাইকৃত)',
        edited_by_patient: false,
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
      body: JSON.stringify({ session_id: 'e2e-session-responsive', mode: 'demo' }),
    }),
  )

  await page.route('**/api/safety/evaluate', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ session_id: 'e2e-session-responsive', mode: 'demo' }),
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
        session_id: 'e2e-session-responsive',
        text_bn: 'আপনার কথা গ্রহণ করা হয়েছে। জরুরি লক্ষণ চিহ্নিত হয়েছে।',
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
        text_bn: 'আপনার কথা গ্রহণ করা হয়েছে। জরুরি লক্ষণ চিহ্নিত হয়েছে।',
      }),
    }),
  )
}

// Helper to assert no horizontal overflow
async function assertNoHorizontalOverflow(page: Page) {
  const offenders = await page.evaluate(() => {
    const list: string[] = []
    const docW = document.documentElement.clientWidth
    document.querySelectorAll('*').forEach((el) => {
      const rect = el.getBoundingClientRect()
      if (rect.right > docW + 2) {
        list.push(`${el.tagName}.${el.className} [right=${rect.right}, clientW=${docW}, text=${el.textContent?.slice(0, 30)}]`)
      }
    })
    return list
  })
  if (offenders.length > 0) {
    console.log('Horizontal overflow offenders:', offenders.slice(0, 5))
  }
  expect(offenders.length).toBe(0)
}

test.describe('Responsive Multi-Viewport Verification & Screenshot Capture', () => {
  for (const vp of VIEWPORTS) {
    test(`capture responsive screenshots at ${vp.name} (${vp.width}x${vp.height})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height })
      await setupMocks(page)

      // 1. Landing Page
      await page.goto('/')
      await page.waitForLoadState('networkidle')
      await assertNoHorizontalOverflow(page)
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `landing_${vp.name}.png`),
        fullPage: true,
      })

      // 2. Intake Page
      await page.goto('/intake')
      await page.waitForLoadState('networkidle')
      await assertNoHorizontalOverflow(page)
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `intake_${vp.name}.png`),
        fullPage: true,
      })

      // Select Demo Samples to proceed to confirm
      const demoBtn = page.getByRole('button', { name: 'Demo samples' })
      if (await demoBtn.isVisible()) {
        await demoBtn.click()
      }
      const useSampleBtn = page.getByRole('button', { name: /Use this sample/ })
      await expect(useSampleBtn).toBeVisible()
      await useSampleBtn.click()

      // 3. Confirm Page
      await expect(page).toHaveURL(/.*\/(review|confirm)/)
      await page.waitForLoadState('networkidle')
      await assertNoHorizontalOverflow(page)
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `confirm_${vp.name}.png`),
        fullPage: true,
      })

      // Confirm and go to summary
      const ackCheckbox = page.getByTestId('ack-warning-checkbox')
      if (await ackCheckbox.isVisible()) {
        await ackCheckbox.check()
      }
      const checkbox = page.getByRole('checkbox', { name: /আমি পড়েছি এবং এটি সঠিক/ })
      await checkbox.check()
      const confirmBtn = page.getByRole('button', { name: /ঠিক আছে, নিশ্চিত করছি/ })
      await confirmBtn.click()

      // 4. Summary Page
      await expect(page).toHaveURL(/.*\/summary/, { timeout: 15_000 })
      await page.waitForLoadState('networkidle')
      await assertNoHorizontalOverflow(page)
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `summary_${vp.name}.png`),
        fullPage: true,
      })

      // 5. About Page
      await page.goto('/about')
      await page.waitForLoadState('networkidle')
      await assertNoHorizontalOverflow(page)
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `about_${vp.name}.png`),
        fullPage: true,
      })
    })
  }
})
