import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react'
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
        <li key={s.label} className="flex items-center gap-3 text-lg" data-state={s.state}>
          {s.state === 'done' && <CheckCircle2 className="h-6 w-6 text-ok" aria-hidden />}
          {s.state === 'run' && <Loader2 className="h-6 w-6 animate-spin text-brand" aria-hidden />}
          {s.state === 'fail' && <XCircle className="h-6 w-6 text-danger" aria-hidden />}
          {s.state === 'wait' && <Circle className="h-6 w-6 text-ink/30" aria-hidden />}
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

  const run = useCallback(async () => {
    const p = flow.pending
    if (!p) return
    setError(null)
    try {
      setStage(0)
      const t = p.kind === 'audio' ? await api.transcribeAudio(p.blob) : await api.transcribeDemo(p.scenarioId)
      flow.setSessionId(t.session_id)
      flow.setTranscription(t)
      flow.setMode(t.mode)
      setStage(1)
      const n = await api.normalize(t.session_id)
      flow.setNormalization(n)
      // The raw recording is no longer needed once transcribed.
      flow.setPending(null)
      setStage(2)
      nav('/confirm', { replace: true })
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, 'UNKNOWN', 'Something went wrong.'))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flow.pending])

  useEffect(() => {
    if (started.current || !flow.pending) return
    started.current = true
    void run()
  }, [flow.pending, run])

  if (!flow.pending && !flow.sessionId) return <Navigate to="/intake" replace />

  const failedAt = error ? stage : -1
  const steps = [
    { label: flow.pending?.kind === 'demo' ? 'Loading prepared sample text (not speech recognition)' : 'Converting speech to text', state: (failedAt === 0 ? 'fail' : stage > 0 ? 'done' : 'run') as St },
    { label: 'Converting dialect words to standard Bangla', state: (failedAt === 1 ? 'fail' : stage > 1 ? 'done' : stage === 1 ? 'run' : 'wait') as St },
    { label: 'Preparing your text for review', state: (stage === 2 ? 'done' : 'wait') as St },
  ]

  return (
    <div className="mx-auto max-w-2xl">
      <StepDots step={0} />
      <div className="mb-4 flex items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-deep" lang="bn">আপনার কথা প্রক্রিয়া করা হচ্ছে…</h1>
        <ModeBadge mode={flow.pending?.kind === 'demo' ? 'demo' : flow.mode} />
      </div>
      <div className="rounded-3xl bg-white p-6">
        <StepList steps={steps} />
      </div>
      {error && (
        <div className="mt-4">
          <ErrorBox
            title={error.code === 'NO_SPEECH_DETECTED' ? 'কোনো কথা শোনা যায়নি' : 'Processing failed'}
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
                Try again
              </Button>
            )}
            <Link to="/intake" className="inline-flex min-h-11 items-center rounded-xl bg-brand px-5 font-semibold text-white">
              আবার রেকর্ড করুন / Record again
            </Link>
          </ErrorBox>
        </div>
      )}
    </div>
  )
}
