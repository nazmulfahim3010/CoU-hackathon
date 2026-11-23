import { act, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import About from '../pages/About'
import Confirm from '../pages/Confirm'
import Intake from '../pages/Intake'
import Landing from '../pages/Landing'
import Processing from '../pages/Processing'
import Summary from '../pages/Summary'
import Transcribe from '../pages/Transcribe'
import { useRecorder } from '../hooks/useRecorder'
import { ApiError, api } from '../services/api'
import type { FlowInitial } from '../state/FlowContext'
import { normalization, renderAt, summary, transcription } from './fixtures'

vi.mock('../services/api', async (orig) => {
  const actual = await orig<typeof import('../services/api')>()
  return {
    ...actual,
    api: {
      health: vi.fn().mockResolvedValue({ status: 'ok', live_mode_ready: false, providers: { speech: { configured: false }, llm: { configured: false }, tts: { configured: true } } }),
      scenarios: vi.fn().mockResolvedValue([]),
      demoSamples: vi.fn().mockResolvedValue([
        {
          id: 'A_ordinary',
          scenario: 'A_ordinary',
          audio_file: 'sample_sylheti_01.wav',
          audio_url: '/api/demo/audio/sample_sylheti_01.wav',
          title: 'Scenario A — Ordinary symptoms',
          purpose: 'Headache and mild fever',
          dialect: 'sylheti',
          speaker: 'Synthetic speech',
          original_transcript: 'আইজ তিন দিন ধরি মোর মাতাত ব্যতা',
          standard_bangla: 'আজ তিন দিন ধরে আমার মাথায় ব্যথা',
          verified_by: 'sample / unverified',
        },
      ]),
      demoLiveAsr: vi.fn().mockResolvedValue({
        sample_id: 'A_ordinary',
        transcript: 'আজ তিন দিন ধরে আমার মাথায় ব্যথা',
        source: 'speech_recognition',
        provider: 'whisper',
        model: 'openai/whisper-large-v3',
        mode: 'live',
      }),
      glossaryStats: vi.fn().mockResolvedValue({
        total: 35,
        verified: 0,
        unverified: 35,
        by_dialect: {
          sylheti: { total: 12, verified: 0, unverified: 12 },
        },
        by_category: {},
      }),
      transcribeAudio: vi.fn(),
      transcribeDemo: vi.fn(),
      normalize: vi.fn(),
      confirm: vi.fn(),
      extract: vi.fn().mockResolvedValue({ session_id: 's1', source: 'llm', provider: 'test', note: '' }),
      evaluateSafety: vi.fn().mockResolvedValue({ triggered: [], needs_information: [], negated: [], notice_en: '', notice_bn: '' }),
      summary: vi.fn().mockResolvedValue({
        session_id: 's1',
        generated_at: new Date().toISOString(),
        mode: 'demo',
        sections: [],
        red_flags: [],
        needs_information: [],
        original_statement: '',
        normalized_statement: '',
        confirmed_statement: '',
        provenance: {},
        label_en: 'AI-assisted patient intake summary — clinician verification required.',
        label_bn: 'এআই-সহায়তায় তৈরি রোগীর প্রাথমিক তথ্যের সারসংক্ষেপ — চিকিৎসকের যাচাই আবশ্যক।',
        disclaimer_en: 'Kotha is not a diagnostic tool.',
        disclaimer_bn: 'কথা কোনো রোগ নির্ণয়ের সরঞ্জাম নয়।',
      }),
      endSession: vi.fn(),
      speech: vi.fn(),
      spokenText: vi.fn(),
    },
  }
})

class FakeRecorder {
  static isTypeSupported = () => true
  state = 'inactive'
  mimeType = 'audio/webm'
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  onerror: (() => void) | null = null
  start() { this.state = 'recording' }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['x'.repeat(2000)]) })
    this.onstop?.()
  }
}

function mockMic(impl: () => Promise<unknown>) {
  Object.defineProperty(navigator, 'mediaDevices', { value: { getUserMedia: impl }, configurable: true })
  vi.stubGlobal('MediaRecorder', FakeRecorder)
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
}

beforeEach(() => vi.clearAllMocks())

describe('useRecorder', () => {
  it('reports permission denial without crashing', async () => {
    mockMic(() => Promise.reject(new DOMException('no', 'NotAllowedError')))
    const { result } = renderHook(() => useRecorder())
    await act(() => result.current.start())
    expect(result.current.status).toBe('error')
    expect(result.current.error).toBe('denied')
  })

  it('reports a missing microphone', async () => {
    mockMic(() => Promise.reject(new DOMException('none', 'NotFoundError')))
    const { result } = renderHook(() => useRecorder())
    await act(() => result.current.start())
    expect(result.current.error).toBe('no-device')
  })

  it('reports unsupported browsers', async () => {
    Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true })
    const { result } = renderHook(() => useRecorder())
    await act(() => result.current.start())
    expect(result.current.error).toBe('unsupported')
  })

  it('records, previews, and discards', async () => {
    const track = { stop: vi.fn() }
    mockMic(() => Promise.resolve({ getTracks: () => [track] }))
    const { result } = renderHook(() => useRecorder())
    await act(() => result.current.start())
    expect(result.current.status).toBe('recording')
    act(() => result.current.stop())
    expect(result.current.status).toBe('recorded')
    expect(result.current.blob).toBeInstanceOf(Blob)
    expect(track.stop).toHaveBeenCalled() // microphone released
    act(() => result.current.discard())
    expect(result.current.status).toBe('idle')
    expect(result.current.blob).toBeNull()
  })

  it('automatically stops recording at 90 seconds using fake timers', async () => {
    vi.useFakeTimers()
    try {
      const track = { stop: vi.fn() }
      mockMic(() => Promise.resolve({ getTracks: () => [track] }))
      const { result } = renderHook(() => useRecorder(90))
      await act(async () => {
        await result.current.start()
      })
      expect(result.current.status).toBe('recording')
      act(() => {
        vi.advanceTimersByTime(91000)
      })
      expect(result.current.status).toBe('recorded')
      expect(result.current.seconds).toBe(90)
    } finally {
      vi.useRealTimers()
    }
  })

  it('handles insecure context error', async () => {
    const orig = window.isSecureContext
    Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true })
    const { result } = renderHook(() => useRecorder())
    await act(() => result.current.start())
    expect(result.current.status).toBe('error')
    expect(result.current.error).toBe('insecure-context')
    Object.defineProperty(window, 'isSecureContext', { value: orig, configurable: true })
  })
})

describe('Intake page', () => {
  it('shows a clear Bangla message when the microphone is denied', async () => {
    mockMic(() => Promise.reject(new DOMException('no', 'NotAllowedError')))
    renderAt('/intake', <Intake />)
    await userEvent.click(await screen.findByRole('button', { name: /রেকর্ড শুরু করুন/ }))
    const alerts = await screen.findAllByRole('alert')
    expect(alerts.some((a) => a.textContent?.includes('মাইক্রোফোনের অনুমতি দেওয়া হয়নি'))).toBe(true)
  })

  it('shows recording controls and the 90 second limit', async () => {
    mockMic(() => Promise.resolve({ getTracks: () => [{ stop: vi.fn() }] }))
    renderAt('/intake', <Intake />)
    await userEvent.click(await screen.findByRole('button', { name: /রেকর্ড শুরু করুন/ }))
    expect(await screen.findByRole('button', { name: /থামান/ })).toBeInTheDocument()
    expect(screen.getByTestId('timer')).toHaveTextContent('/ 01:30')
    await userEvent.click(screen.getByRole('button', { name: /থামান/ }))
    expect(await screen.findByRole('button', { name: /জমা দিন/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /আবার রেকর্ড/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /বাতিল/ })).toBeInTheDocument()
  })

  it('warns when live providers are not configured and labels the mode', async () => {
    mockMic(() => Promise.resolve({}))
    renderAt('/intake', <Intake />)
    expect(await screen.findByText(/not fully configured/)).toBeInTheDocument()
    expect(screen.getByTestId('mode-badge')).toHaveTextContent('LIVE')
  })

  it('warns when ffmpeg is unavailable in live mode and allows switching to demo', async () => {
    vi.mocked(api.health).mockResolvedValueOnce({
      status: 'ok',
      ffmpeg: { available: false },
      live_mode_ready: false,
      providers: {
        speech: { configured: true, provider: 'local', model: '' },
        llm: { configured: true, provider: 'openai' },
        tts: { configured: true, provider: 'gtts' },
      },
    })
    mockMic(() => Promise.resolve({}))
    renderAt('/intake', <Intake />)
    expect(await screen.findByText(/ffmpeg is not installed on this server/i)).toBeInTheDocument()
    const switchBtn = screen.getByRole('button', { name: /Switch to Demo samples/i })
    expect(switchBtn).toBeInTheDocument()
    await userEvent.click(switchBtn)
    expect(screen.queryByText(/ffmpeg is not installed on this server/i)).not.toBeInTheDocument()
    expect(screen.getByTestId('mode-badge')).toHaveTextContent('DEMO')
  })

  it('renders optional age group and dialect selector options', async () => {
    mockMic(() => Promise.resolve({}))
    renderAt('/intake', <Intake />)
    expect(await screen.findByLabelText(/Optional Age Group/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Dialect/i)).toBeInTheDocument()
    expect(screen.getByText(/সিলেটি \(Sylheti\) — পরীক্ষাধীন/i)).toBeInTheDocument()
  })
})

describe('Confirm page', () => {
  const seed: FlowInitial = { sessionId: 's1', normalization, transcription }

  it('shows both transcripts, the Bangla instruction, and is editable', async () => {
    renderAt('/confirm', <Confirm />, seed)
    expect(screen.getByTestId('instruction')).toHaveTextContent('আপনার কথাগুলো আমরা বুঝে লিখেছি')
    expect(screen.getByLabelText('Original transcript')).toHaveValue('মোর মাতাত ব্যতা')
    const std = screen.getByLabelText('Standard Bangla transcript')
    await userEvent.clear(std)
    await userEvent.type(std, 'আমার মাথা ব্যথা')
    expect(std).toHaveValue('আমার মাথা ব্যথা')
    expect(screen.getByText(/unverified glossary/)).toBeInTheDocument()
  })

  it('sends the EDITED text on confirm', async () => {
    vi.mocked(api.confirm).mockResolvedValue({ session_id: 's1', stage: 'confirmed', edited_by_patient: true })
    renderAt('/confirm', <Confirm />, seed)
    const std = screen.getByLabelText('Standard Bangla transcript')
    await userEvent.clear(std)
    await userEvent.type(std, 'সংশোধিত')
    await userEvent.click(screen.getByRole('button', { name: /নিশ্চিত করছি/ }))
    await waitFor(() => expect(api.confirm).toHaveBeenCalledWith('s1', 'মোর মাতাত ব্যতা', 'সংশোধিত'))
    expect(await screen.findByTestId('elsewhere')).toBeInTheDocument() // navigated onward
  })

  it('cannot confirm empty text', async () => {
    renderAt('/confirm', <Confirm />, seed)
    await userEvent.clear(screen.getByLabelText('Standard Bangla transcript'))
    expect(screen.getByRole('button', { name: /নিশ্চিত করছি/ })).toBeDisabled()
  })

  it('checkbox toggles confirm button enabled state', async () => {
    renderAt('/confirm', <Confirm />, seed)
    const checkbox = screen.getByLabelText(/আমি পড়েছি এবং এটি সঠিক/i)
    expect(checkbox).toBeChecked()
    expect(screen.getByRole('button', { name: /নিশ্চিত করছি/ })).toBeEnabled()

    await userEvent.click(checkbox)
    expect(checkbox).not.toBeChecked()
    expect(screen.getByRole('button', { name: /নিশ্চিত করছি/ })).toBeDisabled()

    await userEvent.click(checkbox)
    expect(checkbox).toBeChecked()
    expect(screen.getByRole('button', { name: /নিশ্চিত করছি/ })).toBeEnabled()
  })

  it('record again links back to intake', () => {
    renderAt('/confirm', <Confirm />, seed)
    const link = screen.getByRole('link', { name: /আবার রেকর্ড করুন/i })
    expect(link).toHaveAttribute('href', '/intake')
  })

  it('shows API failure and stays on the page', async () => {
    vi.mocked(api.confirm).mockRejectedValue(new ApiError(404, 'SESSION_NOT_FOUND', 'Session not found or expired.'))
    renderAt('/confirm', <Confirm />, seed)
    await userEvent.click(screen.getByRole('button', { name: /নিশ্চিত করছি/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Session not found or expired.')
    expect(screen.queryByTestId('elsewhere')).toBeNull()
  })

  it('redirects away without a session', () => {
    renderAt('/confirm', <Confirm />)
    expect(screen.getByTestId('elsewhere')).toBeInTheDocument()
  })
})

describe('Transcribe page', () => {
  it('shows loading steps, then an error with retry on failure', async () => {
    vi.mocked(api.transcribeDemo).mockRejectedValue(new ApiError(503, 'PROVIDER_NOT_CONFIGURED', 'No speech provider configured.'))
    renderAt('/transcribe', <Transcribe />, { pending: { kind: 'demo', scenarioId: 'A_ordinary' } })
    expect(await screen.findByRole('alert')).toHaveTextContent('No speech provider configured.')
    expect(screen.getByRole('button', { name: /try again|আবার চেষ্টা করুন/i })).toBeInTheDocument()
  })

  it('moves to confirmation when transcription and normalization succeed', async () => {
    vi.mocked(api.transcribeDemo).mockResolvedValue(transcription)
    vi.mocked(api.normalize).mockResolvedValue(normalization)
    renderAt('/transcribe', <Transcribe />, { pending: { kind: 'demo', scenarioId: 'A_ordinary' } })
    expect(await screen.findByTestId('elsewhere')).toBeInTheDocument()
    expect(api.normalize).toHaveBeenCalledWith('s1')
  })
})

describe('Summary page', () => {
  const seed = (flags: boolean): FlowInitial => ({ sessionId: 's1', summary: summary(flags) })

  it('renders the red-flag panel, label, and sections', () => {
    renderAt('/summary', <Summary />, seed(true))
    expect(screen.getByTestId('ai-label')).toHaveTextContent('clinician verification required')
    const panel = screen.getByTestId('red-flag-panel')
    expect(panel).toHaveTextContent('Chest pain')
    expect(panel).toHaveTextContent('CHEST_PAIN')
    expect(panel).toHaveTextContent('not clinically reviewed')
    expect(screen.getByTestId('section-severity')).toHaveTextContent('Not reported')
    expect(screen.getByTestId('original-statement')).toHaveTextContent('বুগত ব্যতা')
    expect(screen.getByTestId('mode-badge')).toHaveTextContent('DEMO')
  })

  it('toggles between English and Bangla', async () => {
    renderAt('/summary', <Summary />, seed(true))
    await userEvent.click(screen.getByRole('button', { name: 'বাংলা' }))
    expect(screen.getByTestId('section-chief_complaint')).toHaveTextContent('প্রধান সমস্যা')
    expect(screen.getByTestId('red-flag-panel')).toHaveTextContent('এখনই জরুরি চিকিৎসা নিন')
  })

  it('never says the patient is safe when no rule triggers', () => {
    renderAt('/summary', <Summary />, seed(false))
    expect(screen.getByTestId('red-flag-panel')).toHaveTextContent('does not mean the patient is safe')
  })

  it('copies the summary to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    renderAt('/summary', <Summary />, seed(true))
    await userEvent.click(screen.getByRole('button', { name: /Copy summary/ }))
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('RED FLAGS'))
  })

  it('shows spoken text and an honest error when TTS fails', async () => {
    vi.mocked(api.speech).mockRejectedValue(new ApiError(503, 'TTS_FAILED', 'Bangla speech could not be generated right now.'))
    vi.mocked(api.spokenText).mockResolvedValue({ text_bn: 'আপনার কথা লিখে রাখা হয়েছে।' })
    renderAt('/summary', <Summary />, seed(true))
    await userEvent.click(screen.getByRole('button', { name: /উত্তর শুনুন/ }))
    expect(await screen.findByTestId('spoken-text')).toHaveTextContent('লিখে রাখা হয়েছে')
    expect(screen.getByText(/Audio unavailable/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Play/ })).toBeNull()
  })
})

describe('api service', () => {
  it('maps backend error bodies and network failures', async () => {
    const { api: real } = await vi.importActual<typeof import('../services/api')>('../services/api')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => ({ error: { code: 'CONFIRMATION_REQUIRED', message: 'confirm first' } }) }))
    await expect(real.extract('s')).rejects.toMatchObject({ code: 'CONFIRMATION_REQUIRED', status: 409 })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))
    await expect(real.health()).rejects.toMatchObject({ code: 'NETWORK' })
  })
})

describe('Demo Mode in Intake', () => {
  it('renders demo sample cards with audio player and live ASR option', async () => {
    renderAt('/intake', <Intake />, { mode: 'demo' })
    expect(await screen.findByText('Scenario A — Ordinary symptoms')).toBeInTheDocument()
    expect(screen.getByText(/Sample \/ Unverified Dialect Transcript/i)).toBeInTheDocument()
    expect(screen.getByText(/Run live ASR on this sample/)).toBeInTheDocument()
    expect(screen.getByText(/Use this sample/)).toBeInTheDocument()

    // Test clicking Run live ASR
    await userEvent.click(screen.getByRole('button', { name: /Run live ASR on this sample/ }))
    expect(await screen.findByText('Live Speech Recognition Result')).toBeInTheDocument()
    expect(screen.getByText(/openai\/whisper-large-v3/)).toBeInTheDocument()
  })
})

describe('Processing page', () => {
  it('runs extraction, safety check, and navigates to summary', async () => {
    renderAt('/processing', <Processing />, { sessionId: 's1', mode: 'demo' })
    expect(screen.getByText(/তথ্য গুছিয়ে নেওয়া হচ্ছে/)).toBeInTheDocument()
    await waitFor(() => {
      expect(api.extract).toHaveBeenCalledWith('s1')
      expect(api.evaluateSafety).toHaveBeenCalledWith('s1')
      expect(api.summary).toHaveBeenCalledWith('s1')
    })
    expect(await screen.findByTestId('elsewhere')).toBeInTheDocument()
  })

  it('redirects to intake if no session ID is present', () => {
    renderAt('/processing', <Processing />, { sessionId: null })
    expect(screen.getByTestId('elsewhere')).toBeInTheDocument()
  })
})

describe('Landing page', () => {
  it('renders hero title, 8-step pipeline, and dialect cards', async () => {
    renderAt('/', <Landing />)
    expect(screen.getByText(/Every Voice Deserves to Be Understood/)).toBeInTheDocument()
    expect(screen.getByText(/আপনার কণ্ঠ। আপনার ভাষা। উন্নত স্বাস্থ্যসেবা।/)).toBeInTheDocument()
    expect(screen.getByText(/How Kotha Works — 8-Step Safe Pipeline/)).toBeInTheDocument()
    expect(screen.getAllByText(/Record/)[0]).toBeInTheDocument()
    expect(screen.getByText(/Spoken reply/)).toBeInTheDocument()
    expect(screen.getByText(/Supported Dialects — Transparent & Honest/)).toBeInTheDocument()
    expect(screen.getByText('Sylheti')).toBeInTheDocument()
    expect(screen.getByText('Chittagonian')).toBeInTheDocument()
  })
})

describe('About page', () => {
  it('renders the healthcare dialect barrier, AI boundaries table, and credits', () => {
    renderAt('/about', <About />)
    expect(screen.getByText(/About Kotha \(কথা\)/)).toBeInTheDocument()
    expect(screen.getByText(/The Dialect Barrier in Bangladesh Healthcare/)).toBeInTheDocument()
    expect(screen.getByText(/Safety Architecture: What Is AI and What Is Not/)).toBeInTheDocument()
    expect(screen.getByText(/Zero-Retention Privacy Architecture/)).toBeInTheDocument()
    expect(screen.getByText(/Team & Hackathon Credits/)).toBeInTheDocument()
  })
})
