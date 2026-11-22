import type {
  ConfirmationResponse,
  DemoScenario,
  Health,
  NormalizationResponse,
  SafetyResponse,
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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  try {
    const res = await fetch(`/api${path}`, { ...init, signal: ctrl.signal })
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
  health: () => request<Health>('/health'),
  scenarios: () => request<DemoScenario[]>('/demo/scenarios'),
  transcribeAudio: (blob: Blob) => {
    const fd = new FormData()
    fd.append('audio', blob, 'recording.webm')
    return request<TranscriptionResponse>('/transcription', { method: 'POST', body: fd })
  },
  transcribeDemo: (scenarioId: string) => {
    const fd = new FormData()
    fd.append('demo_scenario_id', scenarioId)
    return request<TranscriptionResponse>('/transcription', { method: 'POST', body: fd })
  },
  normalize: (sessionId: string) =>
    request<NormalizationResponse>('/normalization', json({ session_id: sessionId })),
  confirm: (sessionId: string, originalText: string, confirmedText: string) =>
    request<ConfirmationResponse>(
      '/confirmation',
      json({ session_id: sessionId, original_text: originalText, confirmed_text: confirmedText, confirmed: true }),
    ),
  extract: (sessionId: string) => request<unknown>('/clinical/extract', json({ session_id: sessionId })),
  evaluateSafety: (sessionId: string) =>
    request<SafetyResponse>('/safety/evaluate', json({ session_id: sessionId })),
  summary: (sessionId: string) => request<SummaryCard>('/summary/generate', json({ session_id: sessionId })),
  speech: (sessionId: string) => request<SpeechResponse>('/speech/generate', json({ session_id: sessionId })),
  spokenText: (sessionId: string) => request<{ text_bn: string }>(`/speech/text/${sessionId}`),
  endSession: (sessionId: string) => fetch(`/api/session/${sessionId}`, { method: 'DELETE' }).catch(() => undefined),
}
