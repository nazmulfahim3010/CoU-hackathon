import { CheckCircle2, Circle, Edit3, Loader2, RotateCcw, XCircle } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Button, ErrorBox, ModeBadge, StepDots } from '../components/ui'
import { ApiError, api } from '../services/api'
import { useFlow } from '../state/FlowContext'

type St = 'wait' | 'run' | 'done' | 'fail'

export function StepList({ steps }: { steps: { label: string; state: St }[] }) {
  return (
    <ul className="space-y-3">
      {steps.map((s) => (
        <li key={s.label} className="flex items-center gap-3 text-lg font-bangla" data-state={s.state}>
          {s.state === 'done' && <CheckCircle2 className="h-6 w-6 text-ok shrink-0" aria-hidden />}
          {s.state === 'run' && <Loader2 className="h-6 w-6 animate-spin text-brand shrink-0" aria-hidden />}
          {s.state === 'fail' && <XCircle className="h-6 w-6 text-danger shrink-0" aria-hidden />}
          {s.state === 'wait' && <Circle className="h-6 w-6 text-ink/30 shrink-0" aria-hidden />}
          <span className={s.state === 'wait' ? 'text-ink/50' : ''}>{s.label}</span>
        </li>
      ))}
    </ul>
  )
}

export default function Transcribe() {
  const flow = useFlow()
  const nav = useNavigate()
  const started = useRef(false)
  const [stage, setStage] = useState<0 | 1 | 2>(0)
  const [error, setError] = useState<ApiError | null>(null)
  const [showTypedFallback, setShowTypedFallback] = useState(false)
  const [typedText, setTypedText] = useState('')
  const [submittingTyped, setSubmittingTyped] = useState(false)

  const run = useCallback(async () => {
    const p = flow.pending
    if (!p) return
    setError(null)
    setShowTypedFallback(false)
    try {
      setStage(0)
      const t =
        p.kind === 'audio'
          ? await api.transcribeAudio(p.blob, flow.sessionId || undefined, p.dialectHint)
          : await api.transcribeDemo(p.scenarioId, flow.sessionId || undefined)
      flow.setSessionId(t.session_id)
      flow.setTranscription(t)
      flow.setMode(t.mode)
      setStage(1)
      const n = await api.normalize(t.session_id)
      flow.setNormalization(n)
      // Keep the recording in browser memory only, so the patient can later CHOOSE to share it with a health worker
      flow.setRecording(p.kind === 'audio' ? p.blob : null)
      flow.setPending(null)
      setStage(2)
      nav('/review', { replace: true })
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, 'UNKNOWN', 'Something went wrong.'))
    }
  }, [flow, nav])

  const submitTyped = async () => {
    if (!typedText.trim()) return
    setSubmittingTyped(true)
    setError(null)
    try {
      // Ensure we have a session
      let sid = flow.sessionId
      if (!sid) {
        const sess = await api.createSession('live')
        sid = sess.session_id
        flow.setSessionId(sid)
      }
      const t = await api.transcribeTyped(sid, typedText.trim(), flow.dialectHint)
      flow.setTranscription(t)
      setStage(1)
      const n = await api.normalize(sid)
      flow.setNormalization(n)
      flow.setPending(null)
      setStage(2)
      nav('/review', { replace: true })
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, 'UNKNOWN', 'Failed to process typed text.'))
    } finally {
      setSubmittingTyped(false)
    }
  }

  useEffect(() => {
    if (started.current || !flow.pending) return
    started.current = true
    void run()
  }, [flow.pending, run])

  if (!flow.pending && !flow.sessionId) return <Navigate to="/intake" replace />

  const failedAt = error ? stage : -1
  const steps = [
    {
      label:
        flow.pending?.kind === 'demo'
          ? 'ডেমো নমুনা লোড হচ্ছে (Loading prepared demo text)'
          : 'আপনার কথা লেখা হচ্ছে... (Converting speech to text)',
      state: (failedAt === 0 ? 'fail' : stage > 0 ? 'done' : 'run') as St,
    },
    {
      label: 'আঞ্চলিক শব্দ প্রমিত রূপান্তর হচ্ছে... (Converting dialect to standard Bangla)',
      state: (failedAt === 1 ? 'fail' : stage > 1 ? 'done' : stage === 1 ? 'run' : 'wait') as St,
    },
    { label: 'যাচাইয়ের জন্য প্রস্তুত হচ্ছে... (Preparing text for confirmation)', state: (stage === 2 ? 'done' : 'wait') as St },
  ]

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <StepDots step={0} />
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-deep font-bangla" lang="bn">
          আপনার কথা প্রক্রিয়া করা হচ্ছে…
        </h1>
        <ModeBadge mode={flow.pending?.kind === 'demo' ? 'demo' : flow.mode} />
      </div>

      <div className="rounded-3xl bg-white p-6 shadow-sm border border-deep/10">
        <StepList steps={steps} />
      </div>

      {error && !showTypedFallback && (
        <div>
          <ErrorBox
            title={
              error.code === 'NO_SPEECH_DETECTED'
                ? 'কোনো কথা শনাক্ত করা যায়নি'
                : error.code === 'ASR_NON_BANGLA'
                  ? 'কথা বোঝা যায়নি (Speech not recognized as Bangla)'
                  : error.code === 'ASR_PROVIDER_REJECTED'
                    ? 'স্পিচ রিকগনিশন সেবা অনুরোধ প্রত্যাখ্যান করেছে (Provider Rejected)'
                    : error.code === 'ASR_PROVIDER_UNAVAILABLE'
                      ? 'স্পিচ রিকগনিশন সেবা এই মুহূর্তে অনুপলব্ধ (Provider Unavailable)'
                      : error.code === 'ASR_TIMEOUT'
                        ? 'স্পিচ রিকগনিশন সময়সীমা পার হয়েছে (Provider Timeout)'
                        : 'Processing failed'
            }
            message={error.message}
          >
            {error.code !== 'NO_SPEECH_DETECTED' && error.code !== 'AUDIO_TOO_SHORT' && (
              <Button
                variant="secondary"
                onClick={() => {
                  started.current = true
                  void run()
                }}
              >
                <RotateCcw className="h-4 w-4" aria-hidden /> আবার চেষ্টা করুন (Retry)
              </Button>
            )}
            <Button
              variant="secondary"
              onClick={() => setShowTypedFallback(true)}
            >
              <Edit3 className="h-4 w-4" aria-hidden /> নিজে টাইপ করুন (Type manually)
            </Button>
            <Link
              to="/intake"
              className="inline-flex min-h-11 items-center rounded-xl bg-brand px-5 font-semibold text-white hover:bg-deep"
            >
              আবার রেকর্ড করুন (Record again)
            </Link>
          </ErrorBox>
        </div>
      )}

      {showTypedFallback && (
        <div className="rounded-2xl border border-deep/20 bg-white p-5 shadow-sm space-y-4 font-bangla">
          <p className="font-semibold text-deep text-lg">সহায়তাকারী বা রোগীর মুখের কথা টাইপ করুন (Manual Entry)</p>
          <p className="text-xs text-ink/70">
            স্পিচ রিকগনিশন কাজ না করলে রোগীর বলা কথাটি সরাসরি এখানে লিখুন। বাংলা অক্ষরে লিখুন (Roman letters will be converted, please check)। এটি "typed_by_user" হিসেবে সংরক্ষিত হবে।
          </p>
          <textarea
            value={typedText}
            onChange={(e) => setTypedText(e.target.value)}
            rows={4}
            placeholder="বাংলা অক্ষরে লিখুন (Roman letters will be converted, please check)..."
            className="w-full rounded-xl border border-deep/20 p-3 text-base text-text focus:outline-none focus:ring-2 focus:ring-brand"
          />
          <div className="flex flex-wrap gap-3">
            <Button
              big
              disabled={submittingTyped || !typedText.trim()}
              onClick={() => void submitTyped()}
            >
              {submittingTyped ? 'প্রক্রিয়াকরণ হচ্ছে...' : 'টাইপকৃত কথা জমা দিন (Submit)'}
            </Button>
            <Button
              variant="ghost"
              onClick={() => setShowTypedFallback(false)}
            >
              বাতিল (Cancel)
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
