import { useCallback, useEffect, useRef, useState } from 'react'

export const MAX_SECONDS = 90
export const RECOMMENDED_MIN_SECONDS = 30

export type RecorderStatus = 'idle' | 'requesting' | 'recording' | 'recorded' | 'error'
export type RecorderError = 'unsupported' | 'denied' | 'no-device' | 'insecure-context' | 'failed'

// Preferred MIME candidates in prioritized order: WebM/Opus, then MP4, then OGG
const MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4',
  'audio/ogg;codecs=opus',
  'audio/ogg',
]

export function isInsecureContext(): boolean {
  if (typeof window === 'undefined') return false
  if (window.isSecureContext === false) return true
  const host = window.location?.hostname
  if (host && host !== 'localhost' && host !== '127.0.0.1' && window.location?.protocol === 'http:') {
    return true
  }
  return false
}

export function isRecordingSupported(): boolean {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined'
}

function pickMime(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined
  return MIME_CANDIDATES.find((m) => MediaRecorder.isTypeSupported?.(m))
}

/** Browser audio capture. The recording lives only in memory and is released on discard/unmount. */
export function useRecorder(maxSeconds = MAX_SECONDS) {
  const [status, setStatus] = useState<RecorderStatus>('idle')
  const [error, setError] = useState<RecorderError | null>(null)
  const [seconds, setSeconds] = useState(0)
  const [level, setLevel] = useState(0)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [url, setUrl] = useState<string | null>(null)

  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const chunks = useRef<Blob[]>([])
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)
  const raf = useRef<number | null>(null)
  const audioCtx = useRef<AudioContext | null>(null)

  const teardownCapture = useCallback(() => {
    if (timer.current) clearInterval(timer.current)
    if (raf.current && typeof cancelAnimationFrame !== 'undefined') cancelAnimationFrame(raf.current)
    timer.current = null
    raf.current = null
    stream.current?.getTracks().forEach((t) => t.stop())
    stream.current = null
    audioCtx.current?.close().catch(() => undefined)
    audioCtx.current = null
    setLevel(0)
  }, [])

  const stop = useCallback(() => {
    if (recorder.current && recorder.current.state !== 'inactive') {
      recorder.current.stop()
    }
  }, [])

  const discard = useCallback(() => {
    setUrl((u) => {
      if (u) URL.revokeObjectURL(u)
      return null
    })
    setBlob(null)
    chunks.current = []
    setSeconds(0)
    setError(null)
    setStatus('idle')
  }, [])

  const start = useCallback(async () => {
    if (isInsecureContext()) {
      setError('insecure-context')
      setStatus('error')
      return
    }
    if (!isRecordingSupported()) {
      setError('unsupported')
      setStatus('error')
      return
    }
    discard()
    setStatus('requesting')
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.current = s
      const mime = pickMime()
      const rec = new MediaRecorder(s, mime ? { mimeType: mime } : undefined)
      recorder.current = rec
      chunks.current = []
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data)
      }
      rec.onstop = () => {
        const b = new Blob(chunks.current, { type: rec.mimeType || 'audio/webm' })
        teardownCapture()
        if (b.size === 0) {
          setError('failed')
          setStatus('error')
          return
        }
        setBlob(b)
        setUrl(URL.createObjectURL(b))
        setStatus('recorded')
      }
      rec.onerror = () => {
        teardownCapture()
        setError('failed')
        setStatus('error')
      }

      // Live level meter using Web Audio AnalyserNode
      try {
        if (typeof AudioContext !== 'undefined') {
          const ctx = new AudioContext()
          audioCtx.current = ctx
          const analyser = ctx.createAnalyser()
          analyser.fftSize = 256
          ctx.createMediaStreamSource(s).connect(analyser)
          const data = new Uint8Array(analyser.frequencyBinCount)
          const tick = () => {
            analyser.getByteTimeDomainData(data)
            let peak = 0
            for (const v of data) peak = Math.max(peak, Math.abs(v - 128))
            setLevel(Math.min(1, peak / 64))
            if (typeof requestAnimationFrame !== 'undefined') {
              raf.current = requestAnimationFrame(tick)
            }
          }
          tick()
        }
      } catch {
        /* Level meter is optional */
      }

      rec.start(250)
      setSeconds(0)
      setStatus('recording')
      const startedAt = Date.now()
      timer.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startedAt) / 1000)
        setSeconds(Math.min(elapsed, maxSeconds))
        if (elapsed >= maxSeconds) {
          if (timer.current) clearInterval(timer.current)
          timer.current = null
          if (recorder.current && recorder.current.state !== 'inactive') {
            recorder.current.stop()
          }
        }
      }, 250)
    } catch (e) {
      teardownCapture()
      const name = e instanceof DOMException ? e.name : ''
      setError(
        name === 'NotAllowedError' || name === 'PermissionDeniedError' || name === 'SecurityError'
          ? 'denied'
          : name === 'NotFoundError' || name === 'DevicesNotFoundError' || name === 'OverconstrainedError'
            ? 'no-device'
            : 'failed',
      )
      setStatus('error')
    }
  }, [discard, maxSeconds, teardownCapture])

  useEffect(
    () => () => {
      if (recorder.current && recorder.current.state !== 'inactive') {
        recorder.current.onstop = null
        recorder.current.stop()
      }
      teardownCapture()
      if (url) URL.revokeObjectURL(url)
    },
    [teardownCapture, url],
  )

  return { status, error, seconds, level, blob, url, start, stop, discard }
}
