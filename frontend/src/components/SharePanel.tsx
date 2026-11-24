import { Check, Clipboard, ExternalLink, Share2, ShieldCheck, Trash2 } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api } from '../services/api'
import { useFlow } from '../state/FlowContext'
import type { ShareCreated } from '../types/api'
import { Button, ErrorBox, Spinner } from './ui'

export function fmtClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

/** The link a phone should open. Absolute when the server knows its public address, else this page's origin. */
export function absoluteShareUrl(share: ShareCreated): string {
  return /^https?:\/\//.test(share.share_url) ? share.share_url : `${window.location.origin}${share.share_path}`
}

export function isLocalOnly(url: string): boolean {
  try {
    const h = new URL(url).hostname
    return h === 'localhost' || h === '127.0.0.1' || h === '[::1]'
  } catch {
    return false
  }
}

/**
 * Patient-side sharing: hand the SAME summary card (and, only if the patient chooses, the voice clip) to a
 * health worker's phone via a short code, link and QR. Requires explicit consent; in-memory on the server,
 * expires automatically, revocable at any time.
 */
export default function SharePanel({ sessionId }: { sessionId: string }) {
  const { recording, setShareCode } = useFlow()
  const [consent, setConsent] = useState(false)
  const [includeAudio, setIncludeAudio] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [share, setShare] = useState<ShareCreated | null>(null)
  const [left, setLeft] = useState(0)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!share) return
    const tick = () => setLeft(share.expires_at - Date.now() / 1000)
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [share])

  const create = async () => {
    setBusy(true)
    setError(null)
    try {
      const created = await api.createShare(sessionId, consent, includeAudio ? recording : null)
      setShare(created)
      setShareCode(created.code)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not create the share link.')
    } finally {
      setBusy(false)
    }
  }

  const revoke = async () => {
    if (!share) return
    await api.revokeShare(share.code)
    setShare(null)
    setShareCode(null)
    setConsent(false)
    setIncludeAudio(false)
  }

  const url = share ? absoluteShareUrl(share) : ''
  const expired = share !== null && left <= 0

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      window.prompt('Copy this link:', url)
    }
  }

  return (
    <section
      className="no-print rounded-2xl border border-deep/15 bg-white p-5 shadow-sm"
      aria-label="Share with a health worker"
      data-testid="share-panel"
    >
      <h2 className="flex items-center gap-2 text-lg font-bold text-deep">
        <Share2 className="h-5 w-5 text-brand" aria-hidden />
        <span lang="bn">স্বাস্থ্যকর্মীকে পাঠান</span> / Share with a health worker
      </h2>

      {!share && (
        <div className="mt-3 space-y-3">
          <p className="text-sm text-ink/80">
            Send this same summary card to a health worker&apos;s phone with a short code, link or QR code.
          </p>

          <label className="flex cursor-pointer items-start gap-3 rounded-xl bg-soft p-3">
            <input
              type="checkbox"
              className="mt-1 h-5 w-5 shrink-0"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            <span className="text-sm">
              <strong lang="bn">আমি সম্মতি দিচ্ছি</strong> — I agree to share this summary card with a health worker. It is
              kept in memory only, expires automatically, and I can delete it at any time.
            </span>
          </label>

          <label
            className={`flex items-start gap-3 rounded-xl p-3 ${recording ? 'cursor-pointer bg-soft' : 'bg-soft/50 opacity-70'}`}
          >
            <input
              type="checkbox"
              className="mt-1 h-5 w-5 shrink-0"
              checked={includeAudio}
              disabled={!recording}
              onChange={(e) => setIncludeAudio(e.target.checked)}
            />
            <span className="text-sm">
              Also share my <strong>voice recording</strong> so the health worker can hear it.
              {!recording && (
                <span className="block text-xs text-ink/60">
                  No recording is available in this session (for example a demo sample or typed text).
                </span>
              )}
            </span>
          </label>

          {error && <ErrorBox title="Could not share" message={error} />}

          <Button big onClick={create} disabled={!consent || busy}>
            {busy ? <Spinner label="Creating link…" /> : <><Share2 className="h-5 w-5" aria-hidden /> <span lang="bn">শেয়ার লিংক তৈরি করুন</span> / Create share link</>}
          </Button>
        </div>
      )}

      {share && (
        <div className="mt-3 space-y-4" data-testid="share-created">
          {expired ? (
            <ErrorBox title="This share has expired" message="The link no longer works. You can create a new one." />
          ) : (
            <div className="flex flex-wrap items-center gap-5">
              <div className="rounded-xl border border-deep/15 bg-white p-2" aria-label="QR code for the health worker">
                <QRCodeSVG value={url} size={140} level="M" marginSize={1} />
              </div>
              <div className="min-w-0 flex-1 space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-ink/60">Code (read aloud or type at /s)</p>
                <p className="font-mono text-3xl font-bold tracking-widest text-deep" data-testid="share-code">
                  {share.display_code}
                </p>
                <p className="break-all text-xs text-ink/70" data-testid="share-url">{url}</p>
                <p className="text-sm font-semibold text-ok">
                  Expires in <span data-testid="share-countdown">{fmtClock(left)}</span>
                  {share.has_audio ? ' · voice clip included' : ' · summary only'}
                </p>
              </div>
            </div>
          )}

          {!expired && isLocalOnly(url) && (
            <p className="rounded-xl bg-warn/15 p-3 text-sm text-amber-900" data-testid="localhost-warning">
              This link uses <code>localhost</code>, which a phone cannot open. Open Kotha on this computer using its
              Wi-Fi address (for example <code>http://192.168.x.x:8080</code>) or set <code>PUBLIC_BASE_URL</code> on the
              server, then create the share again. A health worker can also type the code on their own phone at{' '}
              <code>/s</code> of that address.
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            {!expired && (
              <>
                <Button variant="secondary" onClick={copy}>
                  {copied ? <Check className="h-4 w-4 text-ok" /> : <Clipboard className="h-4 w-4" />} {copied ? 'Copied' : 'Copy link'}
                </Button>
                <Link
                  to={share.share_path}
                  className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-deep/30 bg-white px-5 font-semibold text-deep hover:bg-soft"
                >
                  <ExternalLink className="h-4 w-4" aria-hidden /> View what the health worker sees
                </Link>
              </>
            )}
            <Button variant="ghost" onClick={revoke}>
              <Trash2 className="h-4 w-4" aria-hidden /> <span lang="bn">মুছে ফেলুন</span> / Stop sharing &amp; delete
            </Button>
          </div>

          <p className="flex items-start gap-2 text-xs text-ink/70">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-deep" aria-hidden />
            <span>{share.notice}</span>
          </p>
        </div>
      )}
    </section>
  )
}
