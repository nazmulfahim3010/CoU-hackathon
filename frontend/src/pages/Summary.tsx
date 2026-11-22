import {
  AlertOctagon,
  Check,
  ChevronDown,
  Clipboard,
  FileText,
  HelpCircle,
  LogOut,
  Printer,
  Quote,
  RefreshCw,
} from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import SpokenReply from '../components/SpokenReply'
import { Button, Disclaimer, ModeBadge, StepDots } from '../components/ui'
import { api } from '../services/api'
import { useFlow } from '../state/FlowContext'
import { summaryToText, type Lang } from '../utils/summaryText'

const T = {
  bn: {
    title: 'চিকিৎসকের সারসংক্ষেপ',
    subtitle: 'রোগীর প্রাথমিক তথ্যের সারসংক্ষেপ — চিকিৎসকের সরাসরি যাচাই আবশ্যক',
    redFlags: 'জরুরি সতর্কতা — নিয়মভিত্তিক এলার্ট',
    noFlags: 'কোনো নির্ধারিত নিয়ম ট্রিগার হয়নি। এর অর্থ এই নয় যে রোগী নিরাপদ। চিকিৎসকের প্রত্যক্ষ মূল্যায়ন আবশ্যক।',
    needInfo: 'অতিরিক্ত তথ্য প্রয়োজন (ডাক্তারের প্রশ্ন)',
    compare: 'বক্তব্য তুলনা (Original / Normalized / Confirmed)',
    original: 'রোগীর মূল বক্তব্য (Dialect)',
    normalized: 'প্রমিত বাংলায় রূপান্তর',
    confirmed: 'রোগী বা সহকারী কর্তৃক নিশ্চিতকৃত পাঠ্য',
    extractionDetails: 'ক্লিনিক্যাল তথ্যের উৎস ও প্রমাণ (Evidence Quotes)',
    evidence: 'বক্তব্যের প্রমাণ',
    provenance: 'প্রক্রিয়াকরণ উৎস (Provenance)',
    copy: 'সারসংক্ষেপ কপি',
    copied: 'কপি হয়েছে!',
    print: 'প্রিন্ট / PDF ডাউনলোড',
    endSession: 'পরামর্শ সমাপ্ত করুন (End session)',
    confirmEnd: 'আপনি কি নিশ্চিত যে এই পরামর্শ শেষ করতে চান? সমস্ত রোগীর তথ্য মেমরি থেকে মুছে যাবে।',
    time: 'উৎপন্ন সময়',
    rule: 'নিয়ম আইডি',
    next: 'প্রস্তাবিত পদক্ষেপ',
    matched: 'চিহ্নিত শব্দ',
    askAbout: 'রোগীকে জিজ্ঞাসা করুন',
  },
  en: {
    title: 'Doctor Summary Dashboard',
    subtitle: 'AI-assisted intake summary — clinician verification required before care decisions',
    redFlags: 'Red Flag Alerts — Deterministic Keyword Rules',
    noFlags: 'No predefined rule was triggered. This does not mean the patient is safe. Direct clinical assessment is required.',
    needInfo: 'Missing Information Needed (Ask Patient)',
    compare: 'Transcript Comparison (Original / Normalized / Confirmed)',
    original: 'Original Dialect Statement',
    normalized: 'Normalized Standard Bangla',
    confirmed: 'Patient/Helper Confirmed Note',
    extractionDetails: 'Clinical Extraction Evidence Quotes',
    evidence: 'Evidence Quote',
    provenance: 'Processing Provenance',
    copy: 'Copy summary',
    copied: 'Copied!',
    print: 'Print / Save PDF',
    endSession: 'End Session (Clear Data)',
    confirmEnd: 'Are you sure you want to end this consultation? All session data will be permanently wiped from memory.',
    time: 'Generated',
    rule: 'Rule ID',
    next: 'Recommended Action',
    matched: 'Matched Span',
    askAbout: 'Ask about',
  },
} as const

const PROV: Record<string, string> = {
  speech_recognition: 'Speech recognition (ASR)',
  speech_model: 'Speech model (ASR)',
  demo_prepared_text: 'Demo prepared transcript (sample)',
  demo_sample: 'Demo prepared transcript (sample)',
  typed_by_user: 'Manually typed by user/helper',
  demo_prepared: 'Demo prepared clinical note',
  llm_with_glossary: 'LLM + Dialect Glossary',
  glossary_only: 'Glossary only (no LLM)',
  llm: 'LLM structured extraction',
  'deterministic rules (no LLM)': 'Deterministic Rules (no LLM)',
  'deterministic rules': 'Deterministic Rules (no LLM)',
  yes: 'Yes (modified)',
  no: 'No (accepted as normalized)',
}

export default function Summary() {
  const { summary, sessionId, reset } = useFlow()
  const nav = useNavigate()
  const [lang, setLang] = useState<Lang>('en')
  const [copied, setCopied] = useState(false)
  const [ending, setEnding] = useState(false)

  if (!summary || !sessionId) return <Navigate to="/intake" replace />
  const t = T[lang]
  const bn = lang === 'bn'

  const copy = async () => {
    const textToCopy = summaryToText(summary, lang)
    try {
      await navigator.clipboard.writeText(textToCopy)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      window.prompt('Copy summary to clipboard:', textToCopy)
    }
  }

  const endSession = async () => {
    if (!window.confirm(t.confirmEnd)) return
    setEnding(true)
    try {
      await api.endSession(sessionId)
    } catch {
      // Proceed even if network error
    } finally {
      reset()
      nav('/intake')
    }
  }

  return (
    <div className="space-y-5 max-w-5xl mx-auto pb-10">
      {/* Step Indicator (Hidden in Print) */}
      <div className="no-print">
        <StepDots step={3} />
      </div>

      {/* Header and Control Bar */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-deep/15 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-deep font-bangla" lang={lang}>
            {t.title}
          </h1>
          <p className="text-sm font-medium text-brand font-bangla mt-0.5" lang={lang} data-testid="ai-label">
            {bn ? summary.label_bn : summary.label_en}
          </p>
          <p className="text-xs text-ink/70 mt-1">
            {t.time}: {new Date(summary.generated_at).toLocaleString(bn ? 'bn-BD' : 'en-GB')} · Memory only (30-min TTL, never stored to disk)
          </p>
        </div>

        {/* Action Buttons (Hidden in Print) */}
        <div className="no-print flex flex-wrap items-center gap-2">
          <ModeBadge mode={summary.mode} />

          {/* Bilingual Toggle */}
          <div className="inline-flex rounded-xl border border-deep/20 bg-white p-1" role="group" aria-label="Language Toggle">
            {(['en', 'bn'] as const).map((l) => (
              <button
                key={l}
                aria-pressed={lang === l}
                onClick={() => setLang(l)}
                className={`min-h-9 rounded-lg px-3.5 text-xs font-bold transition-colors ${
                  lang === l ? 'bg-deep text-white shadow-sm' : 'text-deep hover:bg-soft'
                }`}
              >
                {l === 'en' ? 'English' : 'বাংলা'}
              </button>
            ))}
          </div>

          <Button variant="secondary" className="min-h-10 text-xs font-semibold" onClick={copy}>
            {copied ? <Check className="h-4 w-4 text-ok" /> : <Clipboard className="h-4 w-4" />}
            {copied ? t.copied : t.copy}
          </Button>

          <Button variant="secondary" className="min-h-10 text-xs font-semibold" onClick={() => window.print()}>
            <Printer className="h-4 w-4" /> {t.print}
          </Button>

          <Button
            variant="danger"
            className="min-h-10 text-xs font-semibold bg-[#c62828] text-white hover:bg-red-800"
            onClick={endSession}
            disabled={ending}
          >
            <LogOut className="h-4 w-4 mr-1" /> {t.endSession}
          </Button>
        </div>
      </div>

      {/* 1. Red-Flag Panel (At Top) */}
      <section
        aria-label={t.redFlags}
        className={`print-card rounded-2xl border-2 p-5 transition-all shadow-sm ${
          summary.red_flags.length > 0
            ? 'border-[#c62828] bg-red-50/70'
            : 'border-deep/20 bg-white'
        }`}
        data-testid="red-flag-panel"
      >
        <div className="flex items-center justify-between gap-2 border-b border-deep/10 pb-3 mb-3">
          <h2
            className={`flex items-center gap-2 text-lg font-bold ${
              summary.red_flags.length ? 'text-[#c62828]' : 'text-deep'
            }`}
            lang={lang}
          >
            <AlertOctagon className={`h-5 w-5 ${summary.red_flags.length ? 'text-[#c62828]' : 'text-ink/60'}`} aria-hidden />
            {t.redFlags}
          </h2>
          {summary.red_flags.length > 0 && (
            <span className="rounded-full bg-[#c62828] text-white text-xs font-bold px-2.5 py-0.5">
              {summary.red_flags.length} Alert{summary.red_flags.length > 1 ? 's' : ''} Triggered
            </span>
          )}
        </div>

        {summary.red_flags.length === 0 ? (
          <div className="py-2">
            <p className="text-sm font-medium text-ink/80 leading-relaxed font-bangla" lang={lang}>
              {t.noFlags}
            </p>
          </div>
        ) : (
          <ul className="space-y-3.5">
            {summary.red_flags.map((r) => {
              const isEmergency = r.alert_level === 'emergency'
              return (
                <li
                  key={r.rule_id}
                  className={`rounded-xl border p-4 shadow-xs bg-white ${
                    isEmergency ? 'border-[#c62828]/40 border-l-6 border-l-[#c62828]' : 'border-[#e5a000]/60 border-l-6 border-l-[#e5a000]'
                  }`}
                  lang={lang}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className={`text-base font-bold font-bangla ${isEmergency ? 'text-[#c62828]' : 'text-amber-900'}`}>
                      {bn ? r.name_bn : r.name_en}
                    </p>
                    <span
                      className={`rounded px-2.5 py-0.5 text-xs font-bold uppercase text-white ${
                        isEmergency ? 'bg-[#c62828]' : 'bg-[#e5a000]'
                      }`}
                    >
                      {r.alert_level}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-ink leading-relaxed font-bangla">
                    {bn ? r.explanation_bn : r.explanation_en}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-deep bg-soft p-2.5 rounded-lg font-bangla">
                    <strong>{t.next}:</strong> {bn ? r.recommended_action_bn : r.recommended_action_en}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink/60">
                    <span>
                      <strong>{t.rule}:</strong> {r.rule_id}
                    </span>
                    {r.matched_text.length > 0 && (
                      <span>
                        <strong>{t.matched}:</strong> “{r.matched_text.join('”, “')}”
                      </span>
                    )}
                    {!r.clinically_reviewed && (
                      <span className="text-amber-800 font-medium bg-amber-100 px-1.5 py-0.5 rounded">
                        not clinically reviewed
                      </span>
                    )}
                  </div>
                  {r.required_information && r.required_information.length > 0 && (
                    <p className="mt-1.5 text-xs text-ink/60 font-bangla">
                      <strong>{t.askAbout}:</strong> {r.required_information.join('; ')}
                    </p>
                  )}
                </li>
              )
            })}
          </ul>
        )}

        {/* Needs Information / Ambiguous context alerts */}
        {summary.needs_information.length > 0 && (
          <div className="mt-4 pt-3 border-t border-deep/10 space-y-2">
            <h3 className="text-xs font-bold uppercase text-amber-900 tracking-wider flex items-center gap-1.5">
              <HelpCircle className="h-4 w-4 text-[#e5a000]" /> {t.needInfo}
            </h3>
            {summary.needs_information.map((r) => (
              <div key={r.rule_id} className="rounded-xl border border-[#e5a000]/30 bg-amber-50/80 p-3 text-sm text-amber-950" lang={lang}>
                <p className="font-bold text-amber-900">{bn ? r.name_bn : r.name_en}</p>
                <p className="text-xs mt-1 text-amber-900/90">{bn ? r.explanation_bn : r.explanation_en}</p>
                {r.required_information && r.required_information.length > 0 && (
                  <p className="mt-1.5 text-xs font-semibold text-amber-950">
                    {t.askAbout}: {r.required_information.join('; ')}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 2. Structured Clinical Fields (Information-Dense, Skimmable in 30s) */}
      <div className="grid gap-4 md:grid-cols-2">
        {summary.sections.map((s) => {
          const isNotReported = s.status === 'not_reported'
          const isUncertain = s.status === 'uncertain'

          return (
            <section
              key={s.key}
              className={`print-card rounded-2xl bg-white p-4 shadow-sm border transition-all ${
                isUncertain
                  ? 'border-l-4 border-l-[#e5a000] border-amber-200 bg-amber-50/20'
                  : 'border-deep/10'
              }`}
              data-testid={`section-${s.key}`}
            >
              <div className="flex items-center justify-between gap-2 border-b border-deep/5 pb-1.5 mb-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-deep/80 font-sans" lang={lang}>
                  {bn ? s.title_bn : s.title_en}
                </h3>
                {isUncertain && (
                  <span className="rounded bg-amber-100 text-amber-900 px-2 py-0.5 text-xs font-semibold">
                    Uncertain
                  </span>
                )}
              </div>

              <ul className="space-y-1" lang={lang}>
                {(bn ? s.bn : s.en).map((val, i) => (
                  <li
                    key={i}
                    className={`font-bangla text-base leading-relaxed ${
                      isNotReported ? 'text-ink/40 italic font-normal' : 'text-deep font-medium'
                    }`}
                  >
                    {val}
                  </li>
                ))}
              </ul>
            </section>
          )
        })}
      </div>

      {/* 3. Collapsible Transcript Comparison Panel */}
      <details open className="print-card rounded-2xl bg-white p-5 shadow-sm border border-deep/15 group">
        <summary className="flex cursor-pointer list-none items-center justify-between font-bold text-deep text-sm uppercase tracking-wider focus:outline-none">
          <span className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-brand" /> {t.compare}
          </span>
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>

        <div className="mt-4 space-y-4 pt-3 border-t border-deep/10">
          <div className="grid gap-3 md:grid-cols-3">
            {/* Original Dialect */}
            <div className="rounded-xl border border-deep/10 bg-soft p-3.5">
              <p className="text-xs font-bold uppercase text-ink/60 mb-1">{t.original}</p>
              <p className="font-bangla text-sm text-deep leading-relaxed" lang="bn" data-testid="original-statement">
                {summary.original_statement || '(None)'}
              </p>
            </div>

            {/* Normalized Standard Bangla */}
            <div className="rounded-xl border border-brand/20 bg-brand/5 p-3.5">
              <p className="text-xs font-bold uppercase text-brand mb-1">{t.normalized}</p>
              <p className="font-bangla text-sm text-deep leading-relaxed" lang="bn" data-testid="normalized-statement">
                {summary.normalized_statement || '(None)'}
              </p>
            </div>

            {/* Patient Confirmed Statement */}
            <div className="rounded-xl border border-ok/30 bg-emerald-50/50 p-3.5">
              <p className="text-xs font-bold uppercase text-ok mb-1">{t.confirmed}</p>
              <p className="font-bangla text-sm text-deep leading-relaxed font-semibold" lang="bn" data-testid="confirmed-statement">
                {summary.confirmed_statement || summary.normalized_statement || '(None)'}
              </p>
            </div>
          </div>

          {/* Provenance Details */}
          <div className="text-xs text-ink/70 bg-soft p-3 rounded-xl border border-deep/10">
            <p className="font-bold uppercase tracking-wider text-deep mb-1">{t.provenance}:</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <div>
                <span className="text-ink/50">Speech:</span> {PROV[summary.provenance?.speech_to_text] ?? summary.provenance?.speech_to_text}
              </div>
              <div>
                <span className="text-ink/50">Normalization:</span> {PROV[summary.provenance?.normalization] ?? summary.provenance?.normalization}
              </div>
              <div>
                <span className="text-ink/50">Extraction:</span> {PROV[summary.provenance?.extraction] ?? summary.provenance?.extraction}
              </div>
              <div>
                <span className="text-ink/50">Edited by patient:</span> {PROV[summary.provenance?.patient_edited_text] ?? summary.provenance?.patient_edited_text}
              </div>
            </div>
          </div>
        </div>
      </details>

      {/* 4. Collapsible Extraction Details Panel (Evidence Quotes) */}
      <details className="print-card rounded-2xl bg-white p-5 shadow-sm border border-deep/15 group">
        <summary className="flex cursor-pointer list-none items-center justify-between font-bold text-deep text-sm uppercase tracking-wider focus:outline-none">
          <span className="flex items-center gap-2">
            <Quote className="h-4 w-4 text-brand" /> {t.extractionDetails}
          </span>
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>

        <div className="mt-4 pt-3 border-t border-deep/10 space-y-3">
          <div className="grid gap-2.5 sm:grid-cols-2">
            {summary.sections
              .filter((s) => s.status !== 'not_reported' && s.evidence)
              .map((s) => (
                <div key={s.key} className="rounded-xl border border-deep/10 p-3 bg-soft/50">
                  <p className="text-xs font-bold text-deep uppercase">{bn ? s.title_bn : s.title_en}</p>
                  <blockquote className="mt-1 text-sm font-bangla text-ink/90 border-l-2 border-brand pl-2.5 italic">
                    “{s.evidence}”
                  </blockquote>
                </div>
              ))}
          </div>
        </div>
      </details>

      {/* 5. Patient Spoken Reply (TTS) */}
      <SpokenReply sessionId={sessionId} />

      {/* Legal & Medical Disclaimers */}
      <div className="rounded-xl border border-deep/15 bg-white p-4 text-xs text-ink/80 leading-relaxed font-bangla" lang={lang}>
        <p className="font-semibold text-deep mb-1">
          {bn ? 'দায়মুক্তি ও ক্লিনিক্যাল নির্দেশিকা:' : 'Disclaimer & Clinical Notice:'}
        </p>
        <p>{bn ? summary.disclaimer_bn : summary.disclaimer_en}</p>
      </div>

      {/* Navigation Footer (Hidden in Print) */}
      <div className="no-print flex flex-wrap items-center justify-between gap-3 pt-2">
        <Link
          to="/about"
          className="inline-flex min-h-10 items-center rounded-xl px-4 text-xs font-semibold text-deep underline hover:text-brand"
        >
          Models, Limitations, and Ethical Architecture
        </Link>
        <Button variant="secondary" onClick={endSession}>
          <RefreshCw className="h-4 w-4 mr-1.5" /> Start New Consultation
        </Button>
      </div>

      <div className="no-print">
        <Disclaimer />
      </div>
    </div>
  )
}
