import { Pencil } from 'lucide-react'
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
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!sessionId || !normalization || !transcription) return <Navigate to="/intake" replace />

  const edited = original !== normalization.original || standard !== normalization.normalized
  const canConfirm = standard.trim().length > 0 && original.trim().length > 0 && !busy

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

  return (
    <div className="mx-auto max-w-4xl">
      <StepDots step={1} />
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-deep" lang="bn">আপনার কথা যাচাই করুন</h1>
        <ModeBadge mode={mode} />
      </div>
      <p className="mb-5 rounded-2xl bg-white p-4 text-xl" lang="bn" data-testid="instruction">
        আপনার কথাগুলো আমরা বুঝে লিখেছি। অনুগ্রহ করে ভালোভাবে পড়ে দেখুন। কোনো ভুল থাকলে সংশোধন করুন।
      </p>

      {transcription.source === 'demo_prepared_text' && (
        <p className="mb-3 rounded-xl bg-warn/15 p-3 text-sm text-amber-900">{transcription.disclaimer}</p>
      )}
      {normalization.warnings.map((w) => (
        <p key={w} className="mb-3 rounded-xl bg-warn/15 p-3 text-sm text-amber-900">{w}</p>
      ))}

      <div className="grid gap-4 md:grid-cols-2">
        <label className="block rounded-2xl bg-white p-4">
          <span className="flex items-center gap-2 font-semibold"><Pencil className="h-4 w-4" aria-hidden /> আপনি যা বলেছেন (মূল কথা)</span>
          <span className="text-sm text-ink/60">Original transcript (editable)</span>
          <textarea
            className="mt-2 min-h-40 w-full rounded-xl border border-deep/20 p-3 text-xl leading-9"
            lang="bn"
            value={original}
            onChange={(e) => setOriginal(e.target.value)}
            aria-label="Original transcript"
          />
        </label>
        <label className="block rounded-2xl bg-white p-4 ring-2 ring-brand/30">
          <span className="flex items-center gap-2 font-semibold"><Pencil className="h-4 w-4" aria-hidden /> সাধারণ বাংলায়</span>
          <span className="text-sm text-ink/60">Standard Bangla (editable) — this is what will be used</span>
          <textarea
            className="mt-2 min-h-40 w-full rounded-xl border border-deep/20 p-3 text-xl leading-9"
            lang="bn"
            value={standard}
            onChange={(e) => setStandard(e.target.value)}
            aria-label="Standard Bangla transcript"
          />
        </label>
      </div>

      {normalization.glossary_matches.length > 0 && (
        <details className="mt-4 rounded-2xl bg-white p-4" open={unverified.length > 0}>
          <summary className="cursor-pointer font-semibold">
            Dialect words changed ({normalization.glossary_matches.length})
            {unverified.length > 0 && <span className="ml-2 rounded-full bg-warn/25 px-2 text-sm text-amber-900">unverified glossary — please check</span>}
          </summary>
          <ul className="mt-3 flex flex-wrap gap-2">
            {normalization.glossary_matches.map((m, i) => (
              <li key={i} className="rounded-lg border border-warn/50 bg-warn/10 px-3 py-1" lang="bn" title={`${m.english} (${m.dialect}, ${m.verification})`}>
                {m.regional} → <strong>{m.standard}</strong>
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="mt-3 text-sm text-ink/70">
        Source: {normalization.source.replace(/_/g, ' ')} ({normalization.provider}). {normalization.disclaimer}
      </p>

      {error && <div className="mt-4"><ErrorBox title="Could not confirm" message={error} /></div>}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button big onClick={confirm} disabled={!canConfirm}>
          {busy ? <Spinner label="…" /> : <span lang="bn">ঠিক আছে, নিশ্চিত করছি</span>}
        </Button>
        <Link to="/intake" className="inline-flex min-h-16 items-center rounded-xl border border-deep/30 bg-white px-6 text-lg font-semibold text-deep" onClick={() => api.endSession(sessionId)}>
          <span lang="bn">আবার রেকর্ড করুন</span>
        </Link>
        {edited && <span className="text-sm text-ink/70" lang="bn">আপনি লেখা সংশোধন করেছেন।</span>}
      </div>
      <p className="mt-3 text-sm text-ink/70">Nothing is analysed further until you confirm.</p>
    </div>
  )
}
