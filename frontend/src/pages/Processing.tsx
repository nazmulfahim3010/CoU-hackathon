import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Button, ErrorBox, ModeBadge, StepDots } from '../components/ui'
import { ApiError, api } from '../services/api'
import type { SafetyResponse } from '../types/api'
import { useFlow } from '../state/FlowContext'
import { StepList } from './Transcribe'

export default function Processing() {
  const { sessionId, setSummary, mode } = useFlow()
  const nav = useNavigate()
  const started = useRef(false)
  const [stage, setStage] = useState(0)
  const [error, setError] = useState<ApiError | null>(null)
  const [safety, setSafety] = useState<SafetyResponse | null>(null)

  const run = useCallback(async () => {
    if (!sessionId) return
    setError(null)
    try {
      // Rule-based safety first: it never needs the AI, so an AI outage cannot hide a danger sign.
      setStage(1)
      setSafety(await api.evaluateSafety(sessionId))
      setStage(0)
      await api.extract(sessionId)
      setStage(2)
      setSummary(await api.summary(sessionId))
      setStage(3)
      nav('/summary', { replace: true })
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, 'UNKNOWN', 'Something went wrong.'))
    }
  }, [sessionId, nav, setSummary])

  useEffect(() => {
    if (started.current || !sessionId) return
    started.current = true
    void run()
  }, [sessionId, run])

  if (!sessionId) return <Navigate to="/intake" replace />

  const st = (i: number) => (error && stage === i ? 'fail' : stage > i ? 'done' : stage === i ? 'run' : 'wait') as 'fail' | 'done' | 'run' | 'wait'
  const sessionGone = error?.code === 'SESSION_NOT_FOUND'

  return (
    <div className="mx-auto max-w-2xl">
      <StepDots step={2} />
      <div className="mb-4 flex items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-deep" lang="bn">তথ্য গুছিয়ে নেওয়া হচ্ছে…</h1>
        <ModeBadge mode={mode} />
      </div>
      <div className="rounded-3xl bg-white p-6">
        <StepList
          steps={[
            { label: 'Structuring clinical information from your confirmed text', state: st(0) },
            { label: 'Running rule-based safety checks (no AI involved)', state: st(1) },
            { label: 'Preparing the bilingual doctor summary', state: st(2) },
          ]}
        />
      </div>
      {error && safety && safety.triggered.length > 0 && (
        <div className="mt-4 rounded-2xl border-2 border-red-700 bg-red-50 p-4 text-red-950" role="alert" data-testid="safety-on-failure">
          <p className="font-bold">Safety alert (rule-based, computed without AI)</p>
          <ul className="mt-1 list-disc pl-5 font-bangla" lang="bn">
            {safety.triggered.map((r) => (
              <li key={r.rule_id}>{r.name_bn} / {r.name_en}: {r.recommended_action_bn}</li>
            ))}
          </ul>
        </div>
      )}
      {error && (
        <div className="mt-4">
          <ErrorBox title="Processing failed" message={error.message}>
            {!sessionGone && <Button variant="secondary" onClick={() => void run()}>Try again</Button>}
            {error.code === 'CONFIRMATION_REQUIRED' && <Link to="/confirm" className="font-semibold underline">Back to confirmation</Link>}
            <Link to="/intake" className="inline-flex min-h-11 items-center rounded-xl bg-brand px-5 font-semibold text-white">Start over</Link>
          </ErrorBox>
        </div>
      )}
    </div>
  )
}
