import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SharePanel from '../components/SharePanel'
import SummaryCardView from '../components/SummaryCardView'
import Confirm from '../pages/Confirm'
import ShareView, { ShareEntry } from '../pages/ShareView'
import { ApiError, api } from '../services/api'
import { FlowProvider } from '../state/FlowContext'
import type { ShareCreated, SharedSummary } from '../types/api'
import { normalization, renderAt, summary, transcription } from './fixtures'

vi.mock('../services/api', async (orig) => {
  const actual = await orig<typeof import('../services/api')>()
  return {
    ...actual,
    api: {
      createShare: vi.fn(),
      revokeShare: vi.fn().mockResolvedValue(undefined),
      getShare: vi.fn(),
      shareAudioUrl: (code: string) => `/api/share/${code}/audio`,
      confirm: vi.fn(),
      endSession: vi.fn(),
    },
  }
})

const created = (over: Partial<ShareCreated> = {}): ShareCreated => ({
  code: 'ABCDEFGHJKMN',
  display_code: 'ABCD-EFGH-JKMN',
  share_path: '/s/ABCDEFGHJKMN',
  share_url: '/s/ABCDEFGHJKMN',
  expires_at: Date.now() / 1000 + 1800,
  ttl_seconds: 1800,
  has_audio: false,
  notice: 'Shared with the patient\'s consent. Held in memory only.',
  ...over,
})

const shared = (over: Partial<SharedSummary> = {}): SharedSummary => ({
  code: 'ABCDEFGHJKMN',
  summary: summary(true),
  has_audio: false,
  mode: 'demo',
  created_at: Date.now() / 1000,
  expires_at: Date.now() / 1000 + 1800,
  seconds_left: 1700,
  views: 1,
  notice: 'Shared with the patient\'s consent.',
  ...over,
})

beforeEach(() => vi.clearAllMocks())

describe('SharePanel (patient side)', () => {
  it('cannot create a share until the patient consents', async () => {
    renderAt('/summary', <SharePanel sessionId="s1" />, { sessionId: 's1' })
    const btn = screen.getByRole('button', { name: /Create share link/ })
    expect(btn).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox', { name: /I agree to share this summary card/ }))
    expect(btn).toBeEnabled()
  })

  it('shares the summary only (no audio) by default', async () => {
    vi.mocked(api.createShare).mockResolvedValue(created())
    renderAt('/summary', <SharePanel sessionId="s1" />, { sessionId: 's1', recording: new Blob(['x']) })
    await userEvent.click(screen.getByRole('checkbox', { name: /I agree to share/ }))
    await userEvent.click(screen.getByRole('button', { name: /Create share link/ }))
    await waitFor(() => expect(api.createShare).toHaveBeenCalledWith('s1', true, null))
    expect(await screen.findByTestId('share-code')).toHaveTextContent('ABCD-EFGH-JKMN')
    expect(screen.getByTestId('share-countdown')).toHaveTextContent(/^(29|30):/)
    expect(screen.getByText(/summary only/)).toBeInTheDocument()
  })

  it('includes the voice clip only when the patient ticks the box', async () => {
    vi.mocked(api.createShare).mockResolvedValue(created({ has_audio: true }))
    const blob = new Blob(['voice'])
    renderAt('/summary', <SharePanel sessionId="s1" />, { sessionId: 's1', recording: blob })
    await userEvent.click(screen.getByRole('checkbox', { name: /I agree to share/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Also share my voice recording/ }))
    await userEvent.click(screen.getByRole('button', { name: /Create share link/ }))
    await waitFor(() => expect(api.createShare).toHaveBeenCalledWith('s1', true, blob))
    expect(await screen.findByText(/voice clip included/)).toBeInTheDocument()
  })

  it('disables the voice-clip option when there is no recording (demo or typed)', () => {
    renderAt('/summary', <SharePanel sessionId="s1" />, { sessionId: 's1' })
    expect(screen.getByRole('checkbox', { name: /Also share my voice recording/ })).toBeDisabled()
    expect(screen.getByText(/No recording is available/)).toBeInTheDocument()
  })

  it('warns that a localhost link cannot be opened from a phone', async () => {
    vi.mocked(api.createShare).mockResolvedValue(created())
    renderAt('/summary', <SharePanel sessionId="s1" />, { sessionId: 's1' })
    await userEvent.click(screen.getByRole('checkbox', { name: /I agree to share/ }))
    await userEvent.click(screen.getByRole('button', { name: /Create share link/ }))
    expect(await screen.findByTestId('localhost-warning')).toHaveTextContent(/cannot open/)
  })

  it('does not warn when the server provides a real address', async () => {
    vi.mocked(api.createShare).mockResolvedValue(created({ share_url: 'http://192.168.1.20:8080/s/ABCDEFGHJKMN' }))
    renderAt('/summary', <SharePanel sessionId="s1" />, { sessionId: 's1' })
    await userEvent.click(screen.getByRole('checkbox', { name: /I agree to share/ }))
    await userEvent.click(screen.getByRole('button', { name: /Create share link/ }))
    expect(await screen.findByTestId('share-url')).toHaveTextContent('http://192.168.1.20:8080/s/ABCDEFGHJKMN')
    expect(screen.queryByTestId('localhost-warning')).toBeNull()
  })

  it('revokes the share and returns to the consent state', async () => {
    vi.mocked(api.createShare).mockResolvedValue(created())
    renderAt('/summary', <SharePanel sessionId="s1" />, { sessionId: 's1' })
    await userEvent.click(screen.getByRole('checkbox', { name: /I agree to share/ }))
    await userEvent.click(screen.getByRole('button', { name: /Create share link/ }))
    await userEvent.click(await screen.findByRole('button', { name: /Stop sharing/ }))
    expect(api.revokeShare).toHaveBeenCalledWith('ABCDEFGHJKMN')
    expect(await screen.findByRole('button', { name: /Create share link/ })).toBeDisabled() // consent reset
  })

  it('shows an API failure without losing the consent form', async () => {
    vi.mocked(api.createShare).mockRejectedValue(new ApiError(409, 'WORKFLOW_ORDER_VIOLATION', 'Generate the summary before sharing it.'))
    renderAt('/summary', <SharePanel sessionId="s1" />, { sessionId: 's1' })
    await userEvent.click(screen.getByRole('checkbox', { name: /I agree to share/ }))
    await userEvent.click(screen.getByRole('button', { name: /Create share link/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Generate the summary before sharing it.')
  })
})

function renderShareView(code = 'ABCDEFGHJKMN') {
  return render(
    <MemoryRouter initialEntries={[`/s/${code}`]}>
      <Routes>
        <Route path="/s" element={<ShareEntry />} />
        <Route path="/s/:code" element={<ShareView />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ShareView (health worker side)', () => {
  it('shows the SAME summary card, read-only, with a countdown', async () => {
    vi.mocked(api.getShare).mockResolvedValue(shared())
    renderShareView()
    expect(await screen.findByTestId('share-view')).toBeInTheDocument()
    expect(api.getShare).toHaveBeenCalledWith('ABCDEFGHJKMN')
    expect(screen.getByTestId('red-flag-panel')).toHaveTextContent('Chest pain')
    expect(screen.getByTestId('ai-label')).toHaveTextContent('clinician verification required')
    expect(screen.getByTestId('share-view-countdown')).toHaveTextContent(/Expires in 28:/)
    expect(screen.queryByRole('button', { name: /End Session/i })).toBeNull() // patient-flow actions are not offered
    expect(screen.queryByTestId('share-audio')).toBeNull()
  })

  it('offers the voice clip only when one was shared', async () => {
    vi.mocked(api.getShare).mockResolvedValue(shared({ has_audio: true }))
    renderShareView()
    const audio = await screen.findByTestId('share-audio')
    expect(audio).toHaveAttribute('src', '/api/share/ABCDEFGHJKMN/audio')
    expect(screen.getByText(/shared with consent/i)).toBeInTheDocument()
  })

  it('explains an invalid or expired link without leaking anything', async () => {
    vi.mocked(api.getShare).mockRejectedValue(new ApiError(404, 'SHARE_NOT_FOUND', 'This share link is invalid or has expired.'))
    renderShareView('WRONGCODE123')
    expect(await screen.findByTestId('share-error')).toHaveTextContent(/invalid or has expired/)
    expect(screen.queryByTestId('summary-card')).toBeNull()
  })

  it('lets a health worker type the code on their phone', async () => {
    vi.mocked(api.getShare).mockResolvedValue(shared())
    render(
      <MemoryRouter initialEntries={['/s']}>
        <Routes>
          <Route path="/s" element={<ShareEntry />} />
          <Route path="/s/:code" element={<ShareView />} />
        </Routes>
      </MemoryRouter>,
    )
    await userEvent.type(screen.getByLabelText('Share code'), 'abcd-efgh-jkmn')
    await userEvent.click(screen.getByRole('button', { name: /Open summary/ }))
    await waitFor(() => expect(api.getShare).toHaveBeenCalledWith('abcdefghjkmn'))
  })
})

describe('Summary card: removed model proposals (Challenge 2)', () => {
  it('shows what the model proposed but the patient never said', () => {
    const s = { ...summary(false), removed_ungrounded: [{ bn: 'বুকে ব্যথা', en: 'Chest pain', evidence: '' }] }
    render(<SummaryCardView summary={s} />)
    const panel = screen.getByTestId('removed-ungrounded')
    expect(panel).toHaveTextContent('Removed: not said by the patient')
    expect(panel).toHaveTextContent('Chest pain')
  })

  it('shows nothing when everything was grounded', () => {
    render(<SummaryCardView summary={summary(false)} />)
    expect(screen.queryByTestId('removed-ungrounded')).toBeNull()
  })
})

describe('Confirm screen: undo a symptom word that normalization changed (Challenge 2)', () => {
  const symptomNorm = {
    ...normalization,
    original: 'আমার মাথাত বেদনা করের',
    normalized: 'আমার মাথাত ব্যথা করের',
    glossary_matches: [
      { regional: 'বেদনা', standard: 'ব্যথা', english: 'pain', dialect: 'sylheti', category: 'pain_description', verification: 'verified' },
      { regional: 'আমার', standard: 'আমার', english: 'my', dialect: 'sylheti', category: 'common_medical', verification: 'verified' },
    ],
  }

  function renderConfirm() {
    return render(
      <FlowProvider initial={{ sessionId: 's1', normalization: symptomNorm, transcription }}>
        <MemoryRouter initialEntries={['/review']}>
          <Routes>
            <Route path="/review" element={<Confirm />} />
          </Routes>
        </MemoryRouter>
      </FlowProvider>,
    )
  }

  it('flags symptom substitutions and offers Undo only for them', () => {
    renderConfirm()
    expect(screen.getByTestId('symptom-change-warning')).toHaveTextContent(/1 symptom word was changed/)
    expect(screen.getAllByTestId('undo-change')).toHaveLength(1) // not for the non-symptom word
  })

  it('Undo puts the patient\'s own word back into the text that will be confirmed', async () => {
    renderConfirm()
    const std = screen.getByLabelText('Standard Bangla transcript') as HTMLTextAreaElement
    expect(std.value).toContain('ব্যথা')
    await userEvent.click(screen.getByTestId('undo-change'))
    expect(std.value).toBe('আমার মাথাত বেদনা করের')
  })
})
