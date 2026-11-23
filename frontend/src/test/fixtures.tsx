import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { FlowProvider, type FlowInitial } from '../state/FlowContext'
import type { NormalizationResponse, SummaryCard, TranscriptionResponse } from '../types/api'

export const transcription: TranscriptionResponse = {
  session_id: 's1', mode: 'demo', transcript: 'মূল', source: 'demo_prepared_text', provider: 'demo',
  model: null, confidence: null, disclaimer: 'DEMO: prepared sample text. This was NOT produced by speech recognition.',
}
export const normalization: NormalizationResponse = {
  session_id: 's1', original: 'মোর মাতাত ব্যতা', normalized: 'আমার মাথায় ব্যথা', source: 'demo_prepared',
  glossary_matches: [{ regional: 'মাতাত', standard: 'মাথায়', english: 'on the head', dialect: 'sylheti', category: 'body_part', verification: 'unverified' }],
  uncertain_spans: [], warnings: [], provider: 'demo', disclaimer: 'check it',
}
const rule = {
  rule_id: 'CHEST_PAIN', status: 'triggered', alert_level: 'emergency' as const, name_en: 'Chest pain', name_bn: 'বুকে ব্যথা',
  explanation_en: 'Chest pain was mentioned.', explanation_bn: 'বুকে ব্যথার কথা বলা হয়েছে।',
  recommended_action_en: 'Seek urgent medical care immediately.', recommended_action_bn: 'এখনই জরুরি চিকিৎসা নিন।',
  required_information: ['Onset'], matched_text: ['বুকে ব্যথা'], clinically_reviewed: false,
}
export const summary = (flags = true): SummaryCard => ({
  session_id: 's1', generated_at: '2026-11-22T10:00:00+00:00', mode: 'demo',
  sections: [
    { key: 'chief_complaint', title_en: 'Chief complaint', title_bn: 'প্রধান সমস্যা', en: ['Chest pain'], bn: ['বুকে ব্যথা'], status: 'reported' },
    { key: 'severity', title_en: 'Severity', title_bn: 'তীব্রতা', en: ['Not reported'], bn: ['বলা হয়নি'], status: 'not_reported' },
  ],
  red_flags: flags ? [rule] : [], needs_information: [],
  original_statement: 'বুগত ব্যতা', normalized_statement: 'বুকে ব্যথা', confirmed_statement: 'বুকে ব্যথা',
  provenance: { speech_to_text: 'demo_prepared_text', normalization: 'demo_prepared', extraction: 'demo_prepared', red_flags: 'deterministic rules', patient_edited_text: 'no' },
  label_en: 'AI-assisted patient intake summary — clinician verification required.', label_bn: 'এআই-সহায়তায় তৈরি…',
  disclaimer_en: 'Kotha is not a diagnostic tool. Medical decisions must be made by a qualified healthcare professional.', disclaimer_bn: 'কথা …',
})

export function renderAt(path: string, ui: ReactNode, initial: FlowInitial = {}) {
  return render(
    <FlowProvider initial={initial}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={path} element={ui} />
          <Route path="*" element={<div data-testid="elsewhere">elsewhere</div>} />
        </Routes>
      </MemoryRouter>
    </FlowProvider>,
  )
}
