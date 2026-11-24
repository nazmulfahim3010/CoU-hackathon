import { RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import SharePanel from '../components/SharePanel'
import SpokenReply from '../components/SpokenReply'
import SummaryCardView from '../components/SummaryCardView'
import { Button, Disclaimer, StepDots } from '../components/ui'
import { api } from '../services/api'
import { useFlow } from '../state/FlowContext'

export default function Summary() {
  const { summary, sessionId, reset, shareCode } = useFlow()
  const nav = useNavigate()
  const [ending, setEnding] = useState(false)

  if (!summary || !sessionId) return <Navigate to="/intake" replace />

  const endSession = async () => {
    if (!window.confirm('Are you sure you want to end this consultation? All patient data (and any shared link) will be deleted from memory.')) return
    setEnding(true)
    try {
      if (shareCode) await api.revokeShare(shareCode)
      await api.endSession(sessionId)
    } catch {
      // Proceed even on a network error
    } finally {
      reset()
      nav('/intake')
    }
  }

  return (
    <div className="space-y-5 max-w-5xl mx-auto pb-10">
      <div className="no-print">
        <StepDots step={3} />
      </div>

      <SummaryCardView summary={summary} onEndSession={endSession} ending={ending} />

      {/* Challenge 1: hand the same card (and, with consent, the voice clip) to a health worker's phone */}
      <SharePanel sessionId={sessionId} />

      {/* Patient spoken reply (TTS) */}
      <SpokenReply sessionId={sessionId} />

      {/* Legal & medical disclaimers */}
      <div className="rounded-xl border border-deep/15 bg-white p-4 text-xs text-ink/80 leading-relaxed font-bangla">
        <p className="font-semibold text-deep mb-1">Disclaimer &amp; Clinical Notice:</p>
        <p>{summary.disclaimer_en}</p>
        <p className="mt-1" lang="bn">{summary.disclaimer_bn}</p>
      </div>

      <div className="no-print flex flex-wrap items-center justify-between gap-3 pt-2">
        <Link
          to="/about"
          className="inline-flex min-h-10 items-center rounded-xl px-4 text-xs font-semibold text-deep underline hover:text-brand"
        >
          Models, Limitations, and Ethical Architecture
        </Link>
        <Button variant="secondary" onClick={endSession} disabled={ending}>
          <RefreshCw className="h-4 w-4 mr-1.5" /> Start New Consultation
        </Button>
      </div>

      <div className="no-print">
        <Disclaimer />
      </div>
    </div>
  )
}
