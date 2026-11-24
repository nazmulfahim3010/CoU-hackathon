export type Mode = 'live' | 'demo'

export interface DemoScenario {
  id: string
  title: string
  purpose: string
  dialect_label: string
  patient_note: string
}

export interface Health {
  status: string
  ffmpeg?: { available: boolean }
  providers: {
    speech: { configured: boolean; provider: string; model: string }
    llm: { configured: boolean; provider: string }
    tts: { configured: boolean; provider: string }
  }
  live_mode_ready: boolean
}

export type TranscriptionSource =
  | 'speech_recognition'
  | 'speech_model'
  | 'demo_prepared_text'
  | 'demo_sample'
  | 'typed_by_user'

export interface DemoSample {
  id: string
  scenario: string
  audio_file: string
  audio_url: string
  title: string
  purpose: string
  dialect: string
  speaker: string
  original_transcript: string
  standard_bangla: string
  verified_by: string
}

export interface GlossaryStats {
  total: number
  verified: number
  unverified: number
  by_dialect: Record<string, { total: number; verified: number; unverified: number }>
  by_category: Record<string, number>
}

export interface TranscriptionResponse {
  session_id: string
  mode: Mode
  transcript: string
  source: TranscriptionSource
  provider: string
  model: string | null
  confidence: number | null
  disclaimer: string
}

export interface GlossaryMatch {
  regional: string
  standard: string
  english: string
  dialect: string
  category: string
  verification: string
}

export interface NormalizationResponse {
  session_id: string
  original: string
  original_text?: string
  transliterated_text?: string | null
  script_type?: 'bangla_script' | 'romanized' | 'mixed'
  normalized: string
  source: 'llm_with_glossary' | 'glossary_only' | 'demo_prepared' | 'cached_demo_output'
  glossary_matches: GlossaryMatch[]
  uncertain_spans: string[]
  warnings: string[]
  provider: string
  disclaimer: string
}

export interface ConfirmationResponse {
  session_id: string
  stage: string
  edited_by_patient: boolean
}

export interface RuleResult {
  rule_id: string
  status: string
  alert_level: 'emergency' | 'urgent' | 'info'
  name_en: string
  name_bn: string
  explanation_en: string
  explanation_bn: string
  recommended_action_en: string
  recommended_action_bn: string
  required_information: string[]
  matched_text: string[]
  clinically_reviewed: boolean
}

export interface SafetyResponse {
  triggered: RuleResult[]
  needs_information: RuleResult[]
  negated: RuleResult[]
  notice_en: string
  notice_bn: string
}

export interface SummarySection {
  key: string
  title_en: string
  title_bn: string
  en: string[]
  bn: string[]
  status: string
  evidence?: string | null
}

export interface SummaryCard {
  session_id: string
  generated_at: string
  mode: Mode
  sections: SummarySection[]
  red_flags: RuleResult[]
  needs_information: RuleResult[]
  original_statement: string
  normalized_statement: string
  confirmed_statement: string
  provenance: Record<string, string>
  label_en: string
  label_bn: string
  disclaimer_en: string
  disclaimer_bn: string
}

export interface SpeechResponse {
  text_bn: string
  audio_base64: string
  mime_type: string
  provider: string
}
