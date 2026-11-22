import { AlertOctagon, Check, Clipboard, HelpCircle, Printer, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import SpokenReply from '../components/SpokenReply'
import { Button, Disclaimer, ModeBadge, StepDots } from '../components/ui'
import { api } from '../services/api'
import { useFlow } from '../state/FlowContext'
import { summaryToText, type Lang } from '../utils/summaryText'

const T = {
  bn: {
    redFlags: 'লাল পতাকা — নিয়মভিত্তিক সতর্কতা',
    noFlags: 'কোনো নির্ধারিত নিয়ম ট্রিগার হয়নি। এর অর্থ এই নয় যে রোগী নিরাপদ।',
    needInfo: 'আরও তথ্য প্রয়োজন',
    compare: 'বক্তব্যের তুলনা',
    original: 'রোগীর মূল বক্তব্য',
    normalized: 'সাধারণ বাংলায় (রোগী-নিশ্চিত)',
    provenance: 'প্রক্রিয়ার উৎস',
    copy: 'সারসংক্ষেপ কপি',
    copied: 'কপি হয়েছে',
    print: 'প্রিন্ট / PDF',
    time: 'সময়',
    rule: 'নিয়ম',
    next: 'পরবর্তী পদক্ষেপ',
    matched: 'মিলেছে',
    askAbout: 'জিজ্ঞাসা করুন',
  },
  en: {
    redFlags: 'Red flags — rule-based alerts',
    noFlags: 'No predefined rule was triggered. This does not mean the patient is safe.',
    needInfo: 'More information needed',
    compare: 'Statement comparison',
    original: 'Original patient statement',
    normalized: 'Normalized standard Bangla (patient-confirmed)',
    provenance: 'Processing provenance',
    copy: 'Copy summary',
    copied: 'Copied',
    print: 'Print / Save PDF',
    time: 'Generated',
    rule: 'Rule',
    next: 'Recommended next action',
    matched: 'Matched',
    askAbout: 'Ask about',
  },
} as const

const PROV: Record<string, string> = {
  demo_prepared_text: 'DEMO prepared text (not speech recognition)',
  speech_model: 'Speech model',
  demo_prepared: 'DEMO prepared',
  llm_with_glossary: 'LLM + glossary',
  glossary_only: 'Glossary only (no LLM)',
  llm: 'LLM',
  'deterministic rules': 'Deterministic rules (no LLM)',
}

export default function Summary() {
  const { summary, sessionId, reset } = useFlow()
  const nav = useNavigate()
  const [lang, setLang] = useState<Lang>('en')
  const [copied, setCopied] = useState(false)

  if (!summary || !sessionId) return <Navigate to="/intake" replace />
  const t = T[lang]
  const bn = lang === 'bn'

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(summaryToText(summary, lang))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      window.prompt('Copy the summary:', summaryToText(summary, lang))
    }
  }
  const newConsult = () => {
    void api.endSession(sessionId)
    reset()
    nav('/intake')
  }

  return (
    <div className="space-y-4">
      <div className="no-print"><StepDots step={3} /></div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-deep" lang={lang}>
            {bn ? 'চিকিৎসকের সারসংক্ষেপ' : 'Doctor summary'}
          </h1>
          <p className="font-medium text-brand" lang={lang} data-testid="ai-label">{bn ? summary.label_bn : summary.label_en}</p>
          <p className="text-sm text-ink/70">
            {t.time}: {new Date(summary.generated_at).toLocaleString(bn ? 'bn-BD' : 'en-GB')} · session only, not stored
          </p>
        </div>
        <div className="no-print flex flex-wrap items-center gap-2">
          <ModeBadge mode={summary.mode} />
          <div className="inline-flex rounded-xl border border-deep/20 bg-white p-1" role="group" aria-label="Language">
            {(['en', 'bn'] as const).map((l) => (
              <button
                key={l}
                aria-pressed={lang === l}
                onClick={() => setLang(l)}
                className={`min-h-9 rounded-lg px-3 text-sm font-semibold ${lang === l ? 'bg-deep text-white' : 'text-deep'}`}
              >
                {l === 'en' ? 'English' : 'বাংলা'}
              </button>
            ))}
          </div>
          <Button variant="secondary" onClick={copy}>
            {copied ? <Check className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />} {copied ? t.copied : t.copy}
          </Button>
          <Button variant="secondary" onClick={() => window.print()}>
            <Printer className="h-4 w-4" /> {t.print}
          </Button>
        </div>
      </div>

      <section
        aria-label={t.redFlags}
        className={`print-card rounded-2xl border-2 p-4 ${summary.red_flags.length ? 'border-danger bg-red-50' : 'border-ok/40 bg-white'}`}
        data-testid="red-flag-panel"
      >
        <h2 className={`flex items-center gap-2 text-lg font-bold ${summary.red_flags.length ? 'text-danger' : 'text-ink'}`} lang={lang}>
          <AlertOctagon className="h-5 w-5" aria-hidden /> {t.redFlags}
        </h2>
        {summary.red_flags.length === 0 ? (
          <p className="mt-1" lang={lang}>{t.noFlags}</p>
        ) : (
          <ul className="mt-2 space-y-3">
            {summary.red_flags.map((r) => (
              <li key={r.rule_id} className="rounded-xl bg-white p-3" lang={lang}>
                <p className="font-bold text-danger">
                  {bn ? r.name_bn : r.name_en} <span className="ml-1 rounded bg-danger px-2 py-0.5 text-xs font-semibold uppercase text-white">{r.alert_level}</span>
                </p>
                <p>{bn ? r.explanation_bn : r.explanation_en}</p>
                <p className="font-semibold">{t.next}: {bn ? r.recommended_action_bn : r.recommended_action_en}</p>
                <p className="mt-1 text-xs text-ink/60">
                  {t.rule} {r.rule_id} · {t.matched}: “{r.matched_text.join('”, “')}”{!r.clinically_reviewed && ' · draft rule, not clinically reviewed'}
                </p>
                {r.required_information.length > 0 && (
                  <p className="text-xs text-ink/60">{t.askAbout}: {r.required_information.join('; ')}</p>
                )}
              </li>
            ))}
          </ul>
        )}
        {summary.needs_information.map((r) => (
          <p key={r.rule_id} className="mt-2 flex items-start gap-2 rounded-xl bg-warn/15 p-3 text-sm" lang={lang}>
            <HelpCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span><strong>{t.needInfo}:</strong> {bn ? r.name_bn : r.name_en} — {r.required_information.join('; ')}</span>
          </p>
        ))}
      </section>

      <div className="grid gap-3 md:grid-cols-2">
        {summary.sections.map((s) => (
          <section
            key={s.key}
            className={`print-card rounded-2xl bg-white p-4 ${s.status === 'uncertain' ? 'border-l-4 border-warn' : ''}`}
            data-testid={`section-${s.key}`}
          >
            <h2 className="text-sm font-bold uppercase tracking-wide text-deep" lang={lang}>{bn ? s.title_bn : s.title_en}</h2>
            <ul className="mt-1 space-y-0.5" lang={lang}>
              {(bn ? s.bn : s.en).map((v, i) => (
                <li key={i} className={s.status === 'not_reported' ? 'text-ink/50' : ''}>{v}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <section className="print-card rounded-2xl bg-white p-4">
        <h2 className="text-sm font-bold uppercase tracking-wide text-deep">{t.compare}</h2>
        <div className="mt-2 grid gap-3 md:grid-cols-2">
          <div>
            <p className="text-xs text-ink/60">{t.original}</p>
            <p className="rounded-xl bg-soft p-3 text-lg" lang="bn" data-testid="original-statement">{summary.original_statement}</p>
          </div>
          <div>
            <p className="text-xs text-ink/60">{t.normalized}</p>
            <p className="rounded-xl bg-soft p-3 text-lg" lang="bn" data-testid="normalized-statement">{summary.normalized_statement}</p>
          </div>
        </div>
        <p className="mt-3 text-xs text-ink/60">
          {t.provenance}: speech → {PROV[summary.provenance.speech_to_text] ?? summary.provenance.speech_to_text}; normalization →{' '}
          {PROV[summary.provenance.normalization] ?? summary.provenance.normalization}; extraction →{' '}
          {PROV[summary.provenance.extraction] ?? summary.provenance.extraction}; red flags → {PROV[summary.provenance.red_flags]}; text edited by patient → {summary.provenance.patient_edited_text}
        </p>
      </section>

      <p className="rounded-xl border border-deep/20 bg-white p-3 text-sm" lang={lang}>{bn ? summary.disclaimer_bn : summary.disclaimer_en}</p>

      <SpokenReply sessionId={sessionId} />

      <div className="no-print flex flex-wrap gap-3">
        <Button variant="secondary" onClick={newConsult}><RefreshCw className="h-4 w-4" /> New consultation (clears this session)</Button>
        <Link to="/about" className="inline-flex min-h-11 items-center rounded-xl px-4 font-semibold text-deep underline">Models, limits and privacy</Link>
      </div>
      <div className="no-print"><Disclaimer /></div>
    </div>
  )
}
