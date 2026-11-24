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
    <div className="space-y-6 w-full max-w-7xl mx-auto pb-12">
      {/* Step Indicator (Hidden in Print) */}
      <div className="no-print">
        <StepDots step={3} />
      </div>

      <SummaryCardView
        summary={summary}
        onEndSession={endSession}
        ending={ending}
        sideTop={<SpokenReply sessionId={sessionId} />}
        mainBottom={
          <>
            {/* Hand the same card (and, with consent, the voice clip) to a health worker's phone */}
            <SharePanel sessionId={sessionId} />

            {/* Navigation Footer (Hidden in Print) */}
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
          </>
        }
      />
    </div>
  )
}
