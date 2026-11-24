import { Clock, Headphones, ShieldCheck } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { fmtClock } from '../components/SharePanel'
import SummaryCardView from '../components/SummaryCardView'
import { Button, Disclaimer, ErrorBox, Spinner } from '../components/ui'
import { ApiError, api } from '../services/api'
import type { SharedSummary } from '../types/api'

/** `/s` — a health worker types the code they were given. */
export function ShareEntry() {
  const nav = useNavigate()
  const [code, setCode] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const clean = code.replace(/[^a-zA-Z0-9]/g, '')
    if (clean) nav(`/s/${clean}`)
  }
  return (
    <div className="mx-auto max-w-md space-y-4">
      <h1 className="text-2xl font-bold text-deep">Open a shared summary</h1>
      <p className="text-sm text-ink/80">
        Type the code the patient or helper gave you. <span lang="bn">যে কোডটি পেয়েছেন তা লিখুন।</span>
      </p>
      <form onSubmit={submit} className="space-y-3">
        <label className="block">
          <span className="text-sm font-semibold">Share code</span>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="mt-1 w-full rounded-xl border border-deep/30 bg-white px-4 py-3 font-mono text-2xl uppercase tracking-widest"
            placeholder="ABCD-EFGH-JKMN"
            autoCapitalize="characters"
            autoComplete="off"
            aria-label="Share code"
          />
        </label>
        <Button big type="submit" disabled={!code.trim()}>
          Open summary
        </Button>
      </form>
    </div>
  )
}

/** `/s/:code` — the health worker's read-only view of the SAME summary card the patient sees. */
export default function ShareView() {
  const { code = '' } = useParams()
  const [data, setData] = useState<SharedSummary | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [left, setLeft] = useState(0)

  useEffect(() => {
    let alive = true
    setData(null)
    setError(null)
    api
      .getShare(code)
      .then((d) => {
        if (!alive) return
        setData(d)
        setLeft(d.seconds_left)
      })
      .catch((e: unknown) => alive && setError(e instanceof ApiError ? e : new ApiError(0, 'UNKNOWN', 'Something went wrong.')))
    return () => {
      alive = false
    }
  }, [code])

  useEffect(() => {
    if (!data) return
    const id = setInterval(() => setLeft((l) => l - 1), 1000)
    return () => clearInterval(id)
  }, [data])

  if (error) {
    const gone = error.code === 'SHARE_NOT_FOUND'
    return (
      <div className="mx-auto max-w-xl space-y-4" data-testid="share-error">
        <ErrorBox
          title={gone ? 'This link is invalid or has expired' : 'Could not open the summary'}
          message={
            gone
              ? 'Shared summaries are deleted automatically after a short time. Ask the patient or helper to share it again.'
              : error.message
          }
        >
          <Link to="/s" className="font-semibold underline">Enter a different code</Link>
        </ErrorBox>
      </div>
    )
  }
  if (!data) {
    return (
      <p className="py-10 text-center">
        <Spinner label="Opening shared summary…" />
      </p>
    )
  }
  if (left <= 0) {
    return (
      <div className="mx-auto max-w-xl" data-testid="share-expired">
        <ErrorBox title="This shared summary has expired" message="It has been removed from memory. Ask the patient or helper to share it again.">
          <Link to="/s" className="font-semibold underline">Enter a different code</Link>
        </ErrorBox>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5 pb-10" data-testid="share-view">
      <div className="no-print flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-brand/30 bg-brand/5 p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-deep">
          <ShieldCheck className="h-5 w-5 text-brand" aria-hidden />
          Read-only view shared by the patient / helper with consent
        </p>
        <p className="flex items-center gap-1.5 text-sm font-semibold text-ok" data-testid="share-view-countdown">
          <Clock className="h-4 w-4" aria-hidden /> Expires in {fmtClock(left)}
        </p>
      </div>

      {data.has_audio && (
        <section className="no-print rounded-2xl border border-deep/15 bg-white p-4" aria-label="Patient voice clip">
          <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-deep">
            <Headphones className="h-4 w-4 text-brand" aria-hidden /> Patient&apos;s voice clip (shared with consent)
          </h2>
          <audio controls preload="metadata" className="mt-2 w-full" src={api.shareAudioUrl(data.code)} data-testid="share-audio" />
          <p className="mt-1 text-xs text-ink/60">
            This is the patient&apos;s own recording in their dialect. The text below is an AI-assisted transcription that
            the patient confirmed. Always check it against what you hear.
          </p>
        </section>
      )}

      <SummaryCardView summary={data.summary} />

      <p className="rounded-xl border border-deep/15 bg-white p-3 text-xs text-ink/80">{data.notice}</p>
      <div className="no-print">
        <Disclaimer />
      </div>
    </div>
  )
}
