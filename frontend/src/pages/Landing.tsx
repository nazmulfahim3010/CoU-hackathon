import {
  ArrowRight,
  CheckCircle2,
  Ear,
  FileCheck2,
  FileText,
  Languages,
  Lock,
  Mic,
  ShieldAlert,
  Siren,
  Sparkles,
  Stethoscope,
  UserCheck,
  Volume2,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Disclaimer } from '../components/ui'
import { api } from '../services/api'
import type { GlossaryStats } from '../types/api'

const STEPS = [
  {
    icon: Mic,
    t_en: 'Record',
    t_bn: 'রেকর্ড',
    d: 'Patient describes health concerns in their natural regional dialect (30–90s).',
  },
  {
    icon: Ear,
    t_en: 'Transcribe',
    t_bn: 'লিপ্যন্তর',
    d: 'Bangla acoustic speech model converts the dialect voice recording into text.',
  },
  {
    icon: Languages,
    t_en: 'Normalize',
    t_bn: 'প্রমিত রূপান্তর',
    d: 'Curated regional glossary + LLM maps dialect terms into standard colloquial Bangla.',
  },
  {
    icon: UserCheck,
    t_en: 'Confirm',
    t_bn: 'যাচাই ও অনুমোদন',
    d: 'Patient or helper inspects, corrects, and explicitly confirms the text. Nothing proceeds before this.',
  },
  {
    icon: FileText,
    t_en: 'Extract',
    t_bn: 'তথ্য নিষ্কাশন',
    d: 'Clinical fields are extracted strictly from confirmed statements without inventing facts.',
  },
  {
    icon: Siren,
    t_en: 'Safety check',
    t_bn: 'জরুরি সতর্কতা',
    d: 'Deterministic keyword rules check for red flags with negation detection. Zero LLM involvement.',
  },
  {
    icon: FileCheck2,
    t_en: 'Doctor summary',
    t_bn: 'ডাক্তারের সারসংক্ষেপ',
    d: 'Bilingual (Bangla + English) structured intake note generated deterministically for the clinician.',
  },
  {
    icon: Volume2,
    t_en: 'Spoken reply',
    t_bn: 'শ্রুতিযোগ্য প্রত্যুত্তর',
    d: 'Deterministic Bangla spoken guidance reassures the patient and explains what to do next.',
  },
]

interface DialectCardData {
  key: string
  name_en: string
  name_bn: string
  sample_phrase: string
  standard_bn: string
  english_meaning: string
  default_vocab: number
  verified_status: string
}

const DIALECT_CARDS: DialectCardData[] = [
  {
    key: 'sylheti',
    name_en: 'Sylheti',
    name_bn: 'সিলেটি',
    sample_phrase: 'গত রাইত থাকি আমার বুক বেদনা করের',
    standard_bn: 'গত রাত থেকে আমার বুকে ব্যথা করছে',
    english_meaning: 'Chest pain since last night',
    default_vocab: 120,
    verified_status: 'Team-verified glossary',
  },
  {
    key: 'standard_bangla',
    name_en: 'Standard Bangla',
    name_bn: 'প্রমিত বাংলা',
    sample_phrase: 'আজ তিন দিন ধরে মাথায় ব্যথা ও অল্প জ্বর আছে',
    standard_bn: 'আজ তিন দিন ধরে মাথায় ব্যথা ও অল্প জ্বর আছে',
    english_meaning: 'Headache and mild fever for the past three days',
    default_vocab: 8,
    verified_status: 'Baseline standard',
  },
]

export default function Landing() {
  const [stats, setStats] = useState<GlossaryStats | null>(null)

  useEffect(() => {
    api.glossaryStats().then(setStats).catch(() => setStats(null))
  }, [])

  return (
    <div className="space-y-16 sm:space-y-20 pb-12">
      {/* Hero Section */}
      <section className="grid items-center gap-8 lg:gap-12 pt-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-brand/10 px-3.5 py-1 text-xs sm:text-sm font-semibold text-deep">
            <Sparkles className="h-4 w-4 text-brand shrink-0" aria-hidden />
            <span>Healthcare Accessibility · Hackathon Prototype</span>
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight text-deep sm:text-4xl md:text-5xl leading-tight">
            Every Voice Deserves to Be Understood.
          </h1>

          <p className="mt-2 text-lg sm:text-xl font-bold text-brand font-bangla" lang="bn">
            আপনার কণ্ঠ। আপনার ভাষা। উন্নত স্বাস্থ্যসেবা।
          </p>

          <p className="mt-1 text-base sm:text-lg text-ink/80">
            Your Voice. Your Language. Better Understanding.
          </p>

          <p className="mt-4 text-base sm:text-lg text-ink/90 leading-relaxed max-w-2xl">
            Kotha helps rural and regional patients speak in their natural Bangla dialect, ensures they verify every word, and provides doctors with an immediate, bilingual clinical summary with deterministic safety alerts.
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              to="/intake"
              className="inline-flex min-h-14 items-center gap-2 rounded-xl bg-brand px-6 sm:px-8 text-base sm:text-lg font-bold text-white shadow-md hover:bg-deep transition-all"
            >
              <span lang="bn">Start Voice Consultation / পরামর্শ শুরু করুন</span>
              <ArrowRight className="h-5 w-5" aria-hidden />
            </Link>
            <a
              href="#how-it-works"
              className="inline-flex min-h-14 items-center rounded-xl border border-deep/20 bg-white px-6 text-base font-semibold text-deep hover:bg-soft transition-colors shadow-sm"
            >
              How it works
            </a>
          </div>
        </div>

        {/* Illustrative Live Comparison Visual */}
        <div className="lg:col-span-5 rounded-3xl bg-gradient-to-br from-deep via-deep to-brand p-6 sm:p-7 text-white shadow-xl">
          <div className="space-y-4">
            <div className="rounded-2xl bg-white/10 p-4 backdrop-blur-sm border border-white/10">
              <p className="text-xs font-semibold uppercase tracking-wider text-emerald-300">
                1. Patient speaks in dialect (রোগী বলেন)
              </p>
              <p className="mt-1 text-lg sm:text-xl font-bangla text-white" lang="bn">
                “…গত রাইত থাকি আমার বুক বেদনা করের”
              </p>
              <span className="text-xs text-white/70">Sylheti example sentence from the team-verified glossary</span>
            </div>

            <div className="rounded-2xl bg-white/10 p-4 backdrop-blur-sm border border-white/10">
              <p className="text-xs font-semibold uppercase tracking-wider text-amber-300">
                2. Patient-confirmed Standard Bangla (রোগী কর্তৃক নিশ্চিত)
              </p>
              <p className="mt-1 text-lg sm:text-xl font-bangla text-white" lang="bn">
                “…গত রাত থেকে আমার বুকে ব্যথা করছে”
              </p>
              <span className="text-xs text-white/70">Normalized & confirmed by patient before clinical extraction</span>
            </div>

            <div className="rounded-2xl bg-white/15 p-4 backdrop-blur-sm border border-white/20">
              <p className="text-xs font-semibold uppercase tracking-wider text-red-300">
                3. Doctor sees in 30 seconds (ডাক্তার দেখেন)
              </p>
              <p className="mt-1 font-semibold text-white">
                Chest pain · Deterministic Urgent Alert (CHEST_PAIN)
              </p>
              <span className="text-xs text-white/70">Bilingual note + transparent keyword rules (no hallucinated diagnosis)</span>
            </div>
          </div>
          <p className="mt-4 text-center text-xs text-white/60">
            Illustrative sample: the Sylheti sentence is from the verified glossary; the standard rendering is illustrative.
          </p>
        </div>
      </section>

      {/* The Dialect Problem Section */}
      <section className="space-y-6">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold text-deep">
            The Healthcare Dialect Gap in Bangladesh
          </h2>
          <p className="mt-2 text-base sm:text-lg text-ink/80 max-w-3xl">
            Key insights highlighting why voice dialect support is crucial for equitable healthcare delivery:
          </p>
        </div>

        <div className="grid gap-5 md:grid-cols-3">
          <div className="rounded-2xl border border-deep/10 bg-white p-6 shadow-sm space-y-2">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10 font-bold text-brand">
              1
            </span>
            <h3 className="text-lg font-bold text-deep">170M+ Regional Diversity</h3>
            <p className="text-sm text-ink/80 leading-relaxed">
              While Standard Colloquial Bangla is taught in schools, millions across Sylhet and other rural districts communicate illness using regional vocabulary that differs markedly from textbooks.
            </p>
          </div>

          <div className="rounded-2xl border border-deep/10 bg-white p-6 shadow-sm space-y-2">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10 font-bold text-brand">
              2
            </span>
            <h3 className="text-lg font-bold text-deep">Clinical Communication Gap</h3>
            <p className="text-sm text-ink/80 leading-relaxed">
              Physicians trained in standard Bangla and English medical terms frequently misread regional symptom words, pain intensity, and time expressions—leading to prolonged consultations and missed red flags.
            </p>
          </div>

          <div className="rounded-2xl border border-deep/10 bg-white p-6 shadow-sm space-y-2">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10 font-bold text-brand">
              3
            </span>
            <h3 className="text-lg font-bold text-deep">The Voice Digital Divide</h3>
            <p className="text-sm text-ink/80 leading-relaxed">
              Off-the-shelf speech recognition models are trained on standard broadcast Bangla and fail on regional phonetics. Rural patients cannot access modern digital intake tools without dialect-aware adaptation.
            </p>
          </div>
        </div>
      </section>

      {/* 8-Step Visual Pipeline Flow */}
      <section id="how-it-works" className="space-y-6 scroll-mt-20">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold text-deep">
            How Kotha Works — 8-Step Safe Pipeline
          </h2>
          <p className="mt-2 text-base text-ink/80 max-w-3xl">
            A deterministic, patient-in-the-loop workflow designed to eliminate AI hallucinations and ensure clinician trust.
          </p>
        </div>

        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          {STEPS.map((s, i) => (
            <li
              key={s.t_en}
              className="flex flex-col rounded-2xl border border-deep/10 bg-white p-4 lg:p-5 shadow-sm hover:border-brand/40 transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-soft text-brand shrink-0">
                  <s.icon className="h-5 w-5" aria-hidden />
                </span>
                <span className="text-xs font-bold text-ink/40">Step {i + 1}</span>
              </div>
              <p className="mt-3 font-bold text-deep text-sm lg:text-base">
                {s.t_en} <span className="font-bangla font-normal text-xs lg:text-sm text-brand block sm:inline">({s.t_bn})</span>
              </p>
              <p className="mt-1 text-xs text-ink/75 leading-relaxed flex-1">
                {s.d}
              </p>
            </li>
          ))}
        </ol>
      </section>

      {/* Supported Dialects Section */}
      <section id="dialects" className="space-y-6 scroll-mt-20">
        <div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold text-deep">
                Supported Dialects — Transparent & Honest
              </h2>
              <p className="mt-1 text-base text-ink/80 max-w-3xl">
                We believe in medical honesty. Kotha currently focuses on <strong>Sylheti</strong>. The glossary is team-verified (reviewed by named team members), but it is a text-level review and Kotha has <strong>not</strong> yet been tested on real speech.
              </p>
            </div>
            {stats && (
              <div className="rounded-xl border border-brand/20 bg-brand/5 px-3 py-1.5 text-xs font-semibold text-deep">
                Total curated terms: {stats.total} · Verified: {stats.verified} · Draft: {stats.unverified}
              </div>
            )}
          </div>
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3">
          {DIALECT_CARDS.map((card) => {
            const vocabCount =
              stats?.by_dialect?.[card.key]?.total ?? card.default_vocab
            return (
              <div
                key={card.key}
                className="flex flex-col rounded-2xl border border-deep/15 bg-white p-5 shadow-sm space-y-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-bold text-deep text-base">{card.name_en}</h3>
                    <p className="text-sm font-bangla text-brand" lang="bn">{card.name_bn}</p>
                  </div>
                  <span className="rounded-md border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-900">
                    {card.verified_status}
                  </span>
                </div>

                <div className="rounded-xl bg-soft p-3 text-xs space-y-1.5 flex-1">
                  <p className="font-semibold text-ink/60 uppercase tracking-wide">Example sentence (verified glossary)</p>
                  <p className="font-bangla text-sm text-deep" lang="bn">"{card.sample_phrase}"</p>
                  <p className="text-ink/70"><strong>Std:</strong> <span lang="bn">{card.standard_bn}</span></p>
                  <p className="text-ink/60 italic">"{card.english_meaning}"</p>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-deep/5 text-xs text-ink/70">
                  <span>Vocabulary count:</span>
                  <span className="font-bold text-deep">{vocabCount} terms</span>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* Patient & Doctor Benefits */}
      <section className="grid gap-6 lg:grid-cols-2 lg:gap-8">
        <div className="rounded-3xl border border-deep/10 bg-white p-6 sm:p-8 shadow-sm space-y-4">
          <div className="flex items-center gap-3">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand/10 text-brand">
              <Mic className="h-6 w-6" aria-hidden />
            </span>
            <div>
              <h3 className="text-xl font-bold text-deep">For Rural & Regional Patients</h3>
              <p className="text-xs text-ink/60">Dignity, accessibility, and voice empowerment</p>
            </div>
          </div>
          <ul className="space-y-2.5 text-sm text-ink/80">
            <li className="flex items-start gap-2.5">
              <CheckCircle2 className="h-4 w-4 text-ok shrink-0 mt-0.5" />
              <span><strong>Speak naturally:</strong> No need to struggle typing in standard medical terms or navigate complex smartphone forms.</span>
            </li>
            <li className="flex items-start gap-2.5">
              <CheckCircle2 className="h-4 w-4 text-ok shrink-0 mt-0.5" />
              <span><strong>Confirmation control:</strong> Patients and community helpers inspect and edit the standard Bangla text before the doctor sees anything.</span>
            </li>
            <li className="flex items-start gap-2.5">
              <CheckCircle2 className="h-4 w-4 text-ok shrink-0 mt-0.5" />
              <span><strong>Spoken audio reply:</strong> Receive a clear, gentle audio message in spoken Bangla explaining triage guidance and what to expect.</span>
            </li>
          </ul>
        </div>

        <div className="rounded-3xl border border-deep/10 bg-white p-6 sm:p-8 shadow-sm space-y-4">
          <div className="flex items-center gap-3">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand/10 text-brand">
              <Stethoscope className="h-6 w-6" aria-hidden />
            </span>
            <div>
              <h3 className="text-xl font-bold text-deep">For Doctors & Health Workers</h3>
              <p className="text-xs text-ink/60">Speed, safety, and evidence-grounded intake</p>
            </div>
          </div>
          <ul className="space-y-2.5 text-sm text-ink/80">
            <li className="flex items-start gap-2.5">
              <CheckCircle2 className="h-4 w-4 text-ok shrink-0 mt-0.5" />
              <span><strong>30-second read:</strong> Concise bilingual intake card with chief complaint, duration, symptoms, and current medications.</span>
            </li>
            <li className="flex items-start gap-2.5">
              <CheckCircle2 className="h-4 w-4 text-ok shrink-0 mt-0.5" />
              <span><strong>Deterministic Red Flags:</strong> Immediate alerts for chest pain, respiratory distress, infant fever, and stroke symptoms—calculated without LLM hallucination.</span>
            </li>
            <li className="flex items-start gap-2.5">
              <CheckCircle2 className="h-4 w-4 text-ok shrink-0 mt-0.5" />
              <span><strong>Explicit Uncertainty:</strong> Unmentioned or vague items are highlighted as "Ask about..." rather than silently omitted or fabricated.</span>
            </li>
          </ul>
        </div>
      </section>

      {/* Privacy & Zero-Retention Architecture */}
      <section id="privacy" className="rounded-3xl border border-deep/10 bg-white p-6 sm:p-8 shadow-sm space-y-4 scroll-mt-20">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-deep/10 text-deep">
            <Lock className="h-5 w-5" aria-hidden />
          </span>
          <h2 className="text-xl sm:text-2xl font-bold text-deep">
            Zero-Retention Privacy Architecture
          </h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-3 text-sm text-ink/80">
          <div className="rounded-xl bg-soft p-4 space-y-1 border border-deep/5">
            <p className="font-bold text-deep">No Database or Disk Storage</p>
            <p className="text-xs text-ink/70">Audio and transcripts reside strictly in server memory during the active session and are wiped immediately upon expiry (30m TTL) or manual consultation completion.</p>
          </div>
          <div className="rounded-xl bg-soft p-4 space-y-1 border border-deep/5">
            <p className="font-bold text-deep">Redacted Logging Only</p>
            <p className="text-xs text-ink/70">System logs never contain patient audio, transcripts, names, or API keys. Only high-level event telemetry (e.g., duration, provider) is logged.</p>
          </div>
          <div className="rounded-xl bg-soft p-4 space-y-1 border border-deep/5">
            <p className="font-bold text-deep">Browser-First Audio</p>
            <p className="text-xs text-ink/70">Recordings are held locally in browser RAM until submission. If discarded by the patient, audio never leaves the user's device.</p>
          </div>
        </div>
      </section>

      {/* Medical Disclaimer Section */}
      <section className="rounded-3xl border-l-4 border-deep bg-white p-6 sm:p-7 shadow-sm space-y-2">
        <div className="flex items-center gap-2 text-deep">
          <ShieldAlert className="h-5 w-5 shrink-0" aria-hidden />
          <h2 className="text-lg font-bold">Mandatory Clinical Disclaimer</h2>
        </div>
        <Disclaimer className="mt-2 text-sm sm:text-base" />
      </section>
    </div>
  )
}
