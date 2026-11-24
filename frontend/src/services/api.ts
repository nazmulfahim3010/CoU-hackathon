import type {
  ConfirmationResponse,
  DemoSample,
  DemoScenario,
  GlossaryStats,
  Health,
  NormalizationResponse,
  SafetyResponse,
  ShareCreated,
  SharedSummary,
  SpeechResponse,
  SummaryCard,
  TranscriptionResponse,
} from '../types/api'

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

const TIMEOUT_MS = 120_000
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  try {
    const url = `${BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
    const res = await fetch(url, { ...init, signal: ctrl.signal })
    if (!res.ok) {
      let code = 'HTTP_ERROR'
      let message = `Request failed (${res.status})`
      try {
        const body = await res.json()
        if (body?.error) {
          code = body.error.code
          message = body.error.message
        } else if (body?.detail) {
          code = 'VALIDATION_ERROR'
          message = 'The request was not valid.'
        }
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, code, message)
    }
    return (await res.json()) as T
  } catch (e) {
    if (e instanceof ApiError) throw e
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError(0, 'TIMEOUT', 'The server took too long to respond.')
    }
    throw new ApiError(0, 'NETWORK', 'Could not reach the server. Is the backend running?')
  } finally {
    clearTimeout(timer)
  }
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  createSession: (mode: 'live' | 'demo' = 'live', demoScenarioId?: string) =>
    request<{ session_id: string; state: string; expires_at: number; mode: string }>('/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, demo_scenario_id: demoScenarioId }),
    }),
  health: () => request<Health>('/health'),
  scenarios: () => request<DemoScenario[]>('/demo/scenarios'),
  demoSamples: () => request<DemoSample[]>('/demo/samples'),
  demoLiveAsr: (sampleId: string) =>
    request<{
      sample_id: string
      transcript: string
      source: string
      provider: string
      model: string | null
      mode: string
    }>('/demo/live-asr', json({ sample_id: sampleId })),
  glossaryStats: () => request<GlossaryStats>('/glossary/stats'),
  transcribeAudio: (blob: Blob, sessionId?: string, dialectHint?: string) => {
    const fd = new FormData()
    fd.append('audio', blob, 'recording.webm')
    if (sessionId) fd.append('session_id', sessionId)
    if (dialectHint) fd.append('dialect_hint', dialectHint)
    return request<TranscriptionResponse>('/transcription', { method: 'POST', body: fd })
  },
  transcribeDemo: (scenarioId: string, sessionId?: string) => {
    const fd = new FormData()
    fd.append('demo_scenario_id', scenarioId)
    if (sessionId) fd.append('session_id', sessionId)
    return request<TranscriptionResponse>('/transcription', { method: 'POST', body: fd })
  },
  transcribeTyped: (sessionId: string, text: string, dialectHint?: string) =>
    request<TranscriptionResponse>('/transcription/typed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, text, dialect_hint: dialectHint }),
    }),
  normalize: (sessionId: string) =>
    request<NormalizationResponse>('/normalization', json({ session_id: sessionId })),
  confirm: (
    sessionId: string,
    originalText: string,
    confirmedText: string,
    options?: { edited?: boolean; confirmedBy?: 'patient' | 'helper' },
  ) =>
    request<ConfirmationResponse>(
      '/confirmation',
      json({
        session_id: sessionId,
        original_text: originalText,
        confirmed_text: confirmedText,
        confirmed: true,
        edited: options?.edited,
        confirmed_by: options?.confirmedBy ?? 'patient',
      }),
    ),
  extract: (sessionId: string) => request<unknown>('/clinical/extract', json({ session_id: sessionId })),
  evaluateSafety: (sessionId: string) =>
    request<SafetyResponse>('/safety/evaluate', json({ session_id: sessionId })),
  safety: (sessionId: string) =>
    request<SafetyResponse>('/safety/evaluate', json({ session_id: sessionId })),
  summary: (sessionId: string) => request<SummaryCard>('/summary/generate', json({ session_id: sessionId })),
  speech: (sessionId: string) => request<SpeechResponse>('/speech/generate', json({ session_id: sessionId })),
  spokenText: (sessionId: string) => request<{ text_bn: string }>(`/speech/text/${sessionId}`),
  /** Share the finished summary (and, only if the patient chose, the voice clip) with a health worker. */
  createShare: (sessionId: string, consent: boolean, audio?: Blob | null) => {
    const fd = new FormData()
    fd.append('session_id', sessionId)
    fd.append('consent', consent ? 'true' : 'false')
    if (audio) {
      fd.append('include_audio', 'true')
      fd.append('audio', audio, 'recording.webm')
    } else {
      fd.append('include_audio', 'false')
    }
    return request<ShareCreated>('/share', { method: 'POST', body: fd })
  },
  getShare: (code: string) => request<SharedSummary>(`/share/${encodeURIComponent(code)}`),
  shareAudioUrl: (code: string) => `${BASE_URL}/share/${encodeURIComponent(code)}/audio`,
  revokeShare: (code: string) =>
    fetch(`${BASE_URL}/share/${encodeURIComponent(code)}`, { method: 'DELETE' }).catch(() => undefined),
  endSession: (sessionId: string) => {
    const url = `${BASE_URL}/session/${sessionId}`
    return fetch(url, { method: 'DELETE' }).catch(() => undefined)
  },
}
