import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Mode, NormalizationResponse, SummaryCard, TranscriptionResponse } from '../types/api'

export type AgeGroup = 'not_stated' | 'infant' | 'child' | 'adult' | 'older_adult'
export type DialectHint = 'not_sure' | 'sylheti' | 'standard'

export type Pending =
  | { kind: 'audio'; blob: Blob; ageGroup?: AgeGroup; dialectHint?: DialectHint }
  | { kind: 'demo'; scenarioId: string }
  | null

interface Flow {
  mode: Mode
  setMode: (m: Mode) => void
  pending: Pending
  setPending: (p: Pending) => void
  ageGroup: AgeGroup
  setAgeGroup: (a: AgeGroup) => void
  dialectHint: DialectHint
  setDialectHint: (d: DialectHint) => void
  sessionId: string | null
  setSessionId: (id: string | null) => void
  transcription: TranscriptionResponse | null
  setTranscription: (t: TranscriptionResponse | null) => void
  normalization: NormalizationResponse | null
  setNormalization: (n: NormalizationResponse | null) => void
  summary: SummaryCard | null
  setSummary: (s: SummaryCard | null) => void
  /** The patient's recording, kept ONLY in browser memory so they can choose to share it. Never persisted. */
  recording: Blob | null
  setRecording: (b: Blob | null) => void
  /** Active share code (so ending the consultation can revoke it). */
  shareCode: string | null
  setShareCode: (c: string | null) => void
  reset: () => void
}

const Ctx = createContext<Flow | null>(null)

/** All patient data lives in React memory only (no localStorage, no cookies). */
export interface FlowInitial {
  mode?: Mode
  pending?: Pending
  ageGroup?: AgeGroup
  dialectHint?: DialectHint
  sessionId?: string | null
  transcription?: TranscriptionResponse | null
  normalization?: NormalizationResponse | null
  summary?: SummaryCard | null
  recording?: Blob | null
}

export function FlowProvider({ children, initial = {} }: { children: ReactNode; initial?: FlowInitial }) {
  const [mode, setMode] = useState<Mode>(initial.mode ?? 'live')
  const [pending, setPending] = useState<Pending>(initial.pending ?? null)
  const [ageGroup, setAgeGroup] = useState<AgeGroup>(initial.ageGroup ?? 'not_stated')
  const [dialectHint, setDialectHint] = useState<DialectHint>(initial.dialectHint ?? 'not_sure')
  const [sessionId, setSessionId] = useState<string | null>(initial.sessionId ?? null)
  const [transcription, setTranscription] = useState<TranscriptionResponse | null>(initial.transcription ?? null)
  const [normalization, setNormalization] = useState<NormalizationResponse | null>(initial.normalization ?? null)
  const [summary, setSummary] = useState<SummaryCard | null>(initial.summary ?? null)
  const [recording, setRecording] = useState<Blob | null>(initial.recording ?? null)
  const [shareCode, setShareCode] = useState<string | null>(null)

  const reset = useCallback(() => {
    setPending(null)
    setSessionId(null)
    setTranscription(null)
    setNormalization(null)
    setSummary(null)
    setRecording(null)
    setShareCode(null)
    setAgeGroup('not_stated')
    setDialectHint('not_sure')
  }, [])

  const value = useMemo(
    () => ({
      mode,
      setMode,
      pending,
      setPending,
      ageGroup,
      setAgeGroup,
      dialectHint,
      setDialectHint,
      sessionId,
      setSessionId,
      transcription,
      setTranscription,
      normalization,
      setNormalization,
      summary,
      setSummary,
      recording,
      setRecording,
      shareCode,
      setShareCode,
      reset,
    }),
    [mode, pending, ageGroup, dialectHint, sessionId, transcription, normalization, summary, recording, shareCode, reset],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useFlow(): Flow {
  const v = useContext(Ctx)
  if (!v) throw new Error('useFlow must be used inside FlowProvider')
  return v
}
