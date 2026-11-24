import { AlertTriangle, CheckCircle2, HelpCircle, Info, Mic, Pencil, RotateCcw, UserCheck } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Button, ErrorBox, ModeBadge, Spinner, StepDots } from '../components/ui'
import { ApiError, api } from '../services/api'
import { useFlow } from '../state/FlowContext'

export default function Confirm() {
  const { sessionId, transcription, normalization, mode } = useFlow()
  const nav = useNavigate()
  const [original, setOriginal] = useState(normalization?.original ?? '')
  const [standard, setStandard] = useState(normalization?.normalized ?? '')
  const [reviewed, setReviewed] = useState(false)
  const [confirmedBy, setConfirmedBy] = useState<'patient' | 'helper'>('patient')
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null)
  const [acknowledgedWarning, setAcknowledgedWarning] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!sessionId || !normalization || !transcription) return <Navigate to="/intake" replace />

  const isRomanConverted = Boolean(
    normalization?.script_type === 'romanized' ||
      normalization?.script_type === 'mixed' ||
      normalization?.transliterated_text ||
      normalization?.warnings?.some((w) => w.toLowerCase().includes('roman letters'))
  )

  const isStrongWarning = Boolean(
    isRomanConverted ||
      normalization?.warnings?.some((w) => {
        const lower = w.toLowerCase()
        return (
          lower.includes('invalid response') ||
          lower.includes('no glossary term') ||
          lower.includes('meaning-preservation') ||
          lower.includes('roman letters') ||
          lower.includes('unverified')
        )
      })
  )

  const edited = original !== normalization.original || standard !== normalization.normalized
  const canConfirm =
    reviewed &&
    standard.trim().length > 0 &&
    original.trim().length > 0 &&
    (!isStrongWarning || acknowledgedWarning) &&
    !busy

  const confirm = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.confirm(sessionId, original, standard)
      nav('/processing')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong.')
      setBusy(false)
    }
  }

  const unverified = normalization.glossary_matches.filter((m) => m.verification !== 'verified')

  const sourceDisplayMap: Record<string, { label: string; badge: string }> = {
    speech_recognition: { label: 'Speech recognition (কথা বলা থেকে লেখা)', badge: 'bg-emerald-100 text-emerald-900 border-emerald-300' },
    speech_model: { label: 'Speech recognition (কথা বলা থেকে লেখা)', badge: 'bg-emerald-100 text-emerald-900 border-emerald-300' },
    demo_prepared_text: { label: 'Demo sample (ডেমো নমুনা)', badge: 'bg-blue-100 text-blue-900 border-blue-300' },
    demo_sample: { label: 'Demo sample (ডেমো নমুনা)', badge: 'bg-blue-100 text-blue-900 border-blue-300' },
    cached_demo_output: { label: 'cached demo output (নমুনা ডেটা)', badge: 'bg-amber-100 text-amber-900 border-amber-300' },
    typed_by_user: { label: 'Typed by helper (হাতে টাইপ করা)', badge: 'bg-purple-100 text-purple-900 border-purple-300' },
  }
  const sourceDisplay = sourceDisplayMap[transcription.source] ?? {
    label: 'Speech recognition (কথা বলা থেকে লেখা)',
    badge: 'bg-emerald-100 text-emerald-900 border-emerald-300',
  }

  return (
    <div className="w-full max-w-7xl mx-auto space-y-6 pb-28 lg:pb-36">
      <StepDots step={1} />

      {/* Header & Badges */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-deep font-bangla" lang="bn">
            আপনার কথা যাচাই ও নিশ্চিতকরণ
          </h1>
          <p className="text-sm text-ink/70">Review and verify the patient note before clinical analysis.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${sourceDisplay.badge}`}>
            <Mic className="h-3.5 w-3.5" aria-hidden />
            {sourceDisplay.label}
          </span>
          <ModeBadge mode={mode} />
        </div>
      </div>

      {/* Prominent Patient Instruction */}
      <div className="rounded-2xl border-2 border-brand/30 bg-white p-5 shadow-sm" data-testid="instruction">
        <p className="text-xl font-medium leading-relaxed text-deep font-bangla" lang="bn">
          আপনার কথাগুলো আমরা বুঝে লিখেছি। অনুগ্রহ করে ভালোভাবে পড়ে দেখুন। কোনো ভুল থাকলে সংশোধন করুন।
        </p>
      </div>

      {/* Strong Warning when LLM invalid response or no glossary terms matched */}
      {isStrongWarning && (
        <div
          data-testid="strong-warning"
          className="rounded-2xl border-2 border-red-500 bg-red-50/95 p-5 text-red-950 shadow-sm space-y-3"
          role="alert"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-6 w-6 shrink-0 text-red-600 mt-0.5" aria-hidden />
            <div>
              <h2 className="text-lg font-bold text-red-900 font-bangla" lang="bn">
                জরুরি সতর্কবার্তা: স্বয়ংক্রিয় রূপান্তর অসম্পূর্ণ বা যাচাইবিহীন (Action Required)
              </h2>
              <p className="mt-1 text-sm text-red-900/90 font-bangla" lang="bn">
                ভাষাগত এআই বা শব্দকোষ থেকে এই কথার কোনো প্রমিত রূপান্তর নিশ্চিত করা যায়নি। ডাক্তারের কাছে পাঠানোর আগে অনুগ্রহ করে লেখাটি নিজ হাতে সংশোধন করুন অথবা নিশ্চিত করতে নিচে টিক চিহ্ন দিন।
              </p>
            </div>
          </div>

          <ul className="list-inside list-disc pl-2 space-y-1 text-xs text-red-800 font-medium">
            {normalization.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>

          <label className="flex items-start gap-2.5 rounded-xl border border-red-300 bg-white p-3 cursor-pointer select-none">
            <input
              type="checkbox"
              id="ack-warning-checkbox"
              data-testid="ack-warning-checkbox"
              checked={acknowledgedWarning}
              onChange={(e) => setAcknowledgedWarning(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-red-400 text-red-600 focus:ring-red-500"
            />
            <span className="text-sm font-semibold text-red-950 font-bangla" lang="bn">
              আমি সতর্কবার্তা পড়েছি এবং উল্লেখিত তথ্য সঠিক বলে নিশ্চিত করছি (I acknowledge and verified the warnings)
            </span>
          </label>
        </div>
      )}

      {/* Prominent Normalization Warnings (standard notice when not high warning) */}
      {!isStrongWarning && normalization.warnings.length > 0 && (
        <div className="rounded-xl border border-warn/40 bg-amber-50 p-4 text-amber-950" role="alert">
          <div className="flex items-start gap-2.5 font-semibold text-amber-900">
            <AlertTriangle className="h-5 w-5 shrink-0 text-warn" aria-hidden />
            <span>সতর্কবার্তা / Normalization Notice:</span>
          </div>
          <ul className="mt-2 list-inside list-disc space-y-1 text-sm">
            {normalization.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Side-by-Side (Stacked on Mobile) Comparison */}
      <div className="grid gap-6 md:grid-cols-2 items-stretch">
        {/* Original Dialect / Typed Transcript */}
        <div className="flex flex-col rounded-2xl border border-deep/15 bg-white p-5 lg:p-6 shadow-sm">
          <div className="mb-2 flex items-center justify-between">
            <div>
              <span className="flex items-center gap-2 text-lg font-bold text-deep font-bangla" lang="bn">
                <Pencil className="h-4 w-4 text-ink/60" aria-hidden />
                আপনার কথা (মূল)
              </span>
              <span className="text-xs text-ink/60">
                {isRomanConverted ? 'Original typed text (রোমান হরফে লেখা)' : 'Original transcript as spoken'}
              </span>
            </div>
            <span className="rounded bg-soft px-2 py-0.5 text-xs text-ink/60">Editable</span>
          </div>
          <textarea
            className="mt-2 min-h-52 lg:min-h-64 w-full flex-1 rounded-xl border border-deep/20 p-4 font-bangla text-xl leading-loose text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 resize-y"
            lang="bn"
            value={original}
            onChange={(e) => setOriginal(e.target.value)}
            aria-label="Original transcript"
          />
          {normalization.transliterated_text && (
            <div className="mt-3 rounded-lg bg-brand/5 border border-brand/20 p-2.5 text-xs text-deep">
              <span className="font-semibold font-bangla" lang="bn">বাংলা লিপিতে রূপান্তর (Transliterated): </span>
              <span className="font-bangla font-medium text-brand" lang="bn">{normalization.transliterated_text}</span>
            </div>
          )}
        </div>

        {/* Standard Bangla Transcript */}
        <div className="flex flex-col rounded-2xl border-2 border-brand/40 bg-white p-5 lg:p-6 shadow-sm ring-1 ring-brand/20">
          <div className="mb-2 flex items-center justify-between">
            <div>
              <span className="flex items-center gap-2 text-lg font-bold text-deep font-bangla" lang="bn">
                <Pencil className="h-4 w-4 text-brand" aria-hidden />
                প্রমিত বাংলা (সংশোধনযোগ্য)
              </span>
              <span className="text-xs text-brand/80 font-medium">Standard Bangla — used for clinical extraction</span>
            </div>
            <span className="rounded bg-brand/10 px-2 py-0.5 text-xs font-semibold text-brand">Clinical Note</span>
          </div>
          <textarea
            className="mt-2 min-h-52 lg:min-h-64 w-full flex-1 rounded-xl border border-brand/40 p-4 font-bangla text-xl leading-loose text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30 resize-y"
            lang="bn"
            value={standard}
            onChange={(e) => setStandard(e.target.value)}
            aria-label="Standard Bangla transcript"
          />
        </div>
      </div>

      {/* Interactive Glossary Words & Uncertain Segments */}
      {normalization.glossary_matches.length > 0 && (
        <div className="rounded-2xl border border-deep/15 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 font-bold text-deep">
              <Info className="h-4 w-4 text-brand" aria-hidden />
              আঞ্চলিক শব্দের অর্থ ও রূপান্তর (Glossary Changes: {normalization.glossary_matches.length})
            </h2>
            {unverified.length > 0 && (
              <span className="rounded-full bg-warn/25 px-2.5 py-0.5 text-xs font-semibold text-amber-900">
                পরীক্ষাধীন / unverified glossary
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-ink/70">
            নিচের যে কোনো শব্দে ট্যাপ করে তার সাধারণ অর্থ ও তথ্য জানুন (Tap to inspect dialect meaning):
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {normalization.glossary_matches.map((m, i) => {
              const isOpen = activeTooltip === `${m.regional}-${i}`
              return (
                <div key={i} className="relative">
                  <button
                    type="button"
                    onClick={() => setActiveTooltip(isOpen ? null : `${m.regional}-${i}`)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-brand/30 bg-brand/5 px-3 py-1.5 font-bangla text-base transition-colors hover:bg-brand/15 focus:outline-none focus:ring-2 focus:ring-brand/30"
                  >
                    <span className="text-ink">{m.regional}</span>
                    <span className="text-ink/40">→</span>
                    <strong className="text-brand">{m.standard}</strong>
                    <HelpCircle className="h-3 w-3 text-ink/40" />
                  </button>
                  {isOpen && (
                    <div className="absolute left-0 top-full z-10 mt-1 w-64 rounded-xl border border-deep/20 bg-deep p-3 text-xs text-white shadow-xl">
                      <p className="font-semibold text-emerald-300 font-bangla">{m.regional} → {m.standard}</p>
                      <p className="mt-0.5 text-white/80">{m.english}</p>
                      <div className="mt-2 flex items-center justify-between border-t border-white/15 pt-1.5 text-[11px] text-white/60">
                        <span>ডায়ালেক্ট: {m.dialect}</span>
                        <span>ধরণ: {m.category}</span>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {error && <ErrorBox title="Could not confirm" message={error} />}

      <p className="text-xs text-ink/60 lg:pb-2">
        Kotha Safety Gate: No symptoms are extracted and no clinical summaries are created until you explicitly confirm the standard Bangla text.
      </p>

      {/* Confirmation Controls: Sticky Bottom Bar on Desktop (lg+), Natural Inline Card on Mobile (<lg) */}
      <div className="lg:fixed lg:bottom-0 lg:left-0 lg:right-0 lg:z-30 lg:bg-white/95 lg:backdrop-blur-md lg:border-t lg:border-deep/15 lg:py-4 lg:shadow-xl transition-all">
        <div className="w-full max-w-7xl mx-auto lg:px-8">
          <div className="rounded-2xl border border-deep/15 bg-white p-5 shadow-sm space-y-4 lg:space-y-0 lg:border-0 lg:p-0 lg:bg-transparent lg:shadow-none lg:flex lg:items-center lg:justify-between lg:gap-6">
            
            {/* Review Checkbox & Confirmed-By Toggle */}
            <div className="space-y-3 lg:space-y-1.5 lg:max-w-2xl">
              <label className="flex items-start gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  id="reviewed-checkbox"
                  checked={reviewed}
                  onChange={(e) => setReviewed(e.target.checked)}
                  className="mt-1 h-5 w-5 rounded border-deep/30 text-brand focus:ring-brand shrink-0"
                  aria-label="আমি পড়েছি এবং এটি সঠিক"
                />
                <div>
                  <span className="text-lg font-bold text-deep font-bangla leading-snug" lang="bn">
                    আমি পড়েছি এবং এটি সঠিক
                  </span>
                  <p className="text-xs text-ink/70">
                    I have read the transcript and verify that it accurately reflects the symptoms and duration.
                  </p>
                </div>
              </label>

              {/* Confirmed-by toggle */}
              <div className="flex flex-wrap items-center gap-3 border-t border-deep/10 pt-2 lg:border-t-0 lg:pt-0 text-sm">
                <span className="flex items-center gap-1.5 font-semibold text-deep">
                  <UserCheck className="h-4 w-4 text-brand shrink-0" aria-hidden />
                  নিশ্চিতকারী (Confirmed by):
                </span>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="radio"
                    name="confirmed_by"
                    value="patient"
                    checked={confirmedBy === 'patient'}
                    onChange={() => setConfirmedBy('patient')}
                    className="text-brand focus:ring-brand"
                  />
                  <span className="font-bangla" lang="bn">রোগী নিজে (Patient)</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="radio"
                    name="confirmed_by"
                    value="helper"
                    checked={confirmedBy === 'helper'}
                    onChange={() => setConfirmedBy('helper')}
                    className="text-brand focus:ring-brand"
                  />
                  <span className="font-bangla" lang="bn">স্বাস্থ্যকর্মী / সহকারী (Helper)</span>
                </label>
                {edited && (
                  <span className="text-xs font-semibold text-brand font-bangla pl-2" lang="bn">
                    ✓ আপনি লেখা সংশোধন করেছেন (Edited)
                  </span>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-3 shrink-0">
              <Button big onClick={confirm} disabled={!canConfirm} className="min-h-14 lg:min-h-16">
                {busy ? <Spinner label="নিশ্চিত হচ্ছে…" /> : (
                  <span className="flex items-center gap-2 font-bangla text-lg" lang="bn">
                    <CheckCircle2 className="h-5 w-5 shrink-0" aria-hidden />
                    ঠিক আছে, নিশ্চিত করছি
                  </span>
                )}
              </Button>

              <Link
                to="/intake"
                className="inline-flex min-h-14 lg:min-h-16 items-center gap-2 rounded-xl border border-deep/30 bg-white px-5 font-bangla text-base lg:text-lg font-semibold text-deep transition-colors hover:bg-soft"
                onClick={() => api.endSession(sessionId)}
              >
                <RotateCcw className="h-5 w-5 shrink-0" aria-hidden />
                <span lang="bn">আবার রেকর্ড করুন</span>
              </Link>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
