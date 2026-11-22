import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Mode, NormalizationResponse, SummaryCard, TranscriptionResponse } from '../types/api'

export type Pending = { kind: 'audio'; blob: Blob } | { kind: 'demo'; scenarioId: string } | null

interface Flow {
  mode: Mode
  setMode: (m: Mode) => void
  pending: Pending
  setPending: (p: Pending) => void
  sessionId: string | null
  setSessionId: (id: string | null) => void
  transcription: TranscriptionResponse | null
  setTranscription: (t: TranscriptionResponse | null) => void
  normalization: NormalizationResponse | null
  setNormalization: (n: NormalizationResponse | null) => void
  summary: SummaryCard | null
  setSummary: (s: SummaryCard | null) => void
  reset: () => void
}

const Ctx = createContext<Flow | null>(null)

/** All patient data lives in React memory only (no localStorage, no cookies). */
export interface FlowInitial {
  mode?: Mode
  pending?: Pending
  sessionId?: string | null
  transcription?: TranscriptionResponse | null
  normalization?: NormalizationResponse | null
  summary?: SummaryCard | null
}

export function FlowProvider({ children, initial = {} }: { children: ReactNode; initial?: FlowInitial }) {
  const [mode, setMode] = useState<Mode>(initial.mode ?? 'live')
  const [pending, setPending] = useState<Pending>(initial.pending ?? null)
  const [sessionId, setSessionId] = useState<string | null>(initial.sessionId ?? null)
  const [transcription, setTranscription] = useState<TranscriptionResponse | null>(initial.transcription ?? null)
  const [normalization, setNormalization] = useState<NormalizationResponse | null>(initial.normalization ?? null)
  const [summary, setSummary] = useState<SummaryCard | null>(initial.summary ?? null)

  const reset = useCallback(() => {
    setPending(null)
    setSessionId(null)
    setTranscription(null)
    setNormalization(null)
    setSummary(null)
  }, [])

  const value = useMemo(
    () => ({ mode, setMode, pending, setPending, sessionId, setSessionId, transcription, setTranscription,
      normalization, setNormalization, summary, setSummary, reset }),
    [mode, pending, sessionId, transcription, normalization, summary, reset],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useFlow(): Flow {
  const v = useContext(Ctx)
  if (!v) throw new Error('useFlow must be used inside FlowProvider')
  return v
}
