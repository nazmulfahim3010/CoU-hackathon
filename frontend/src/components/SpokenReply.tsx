import { AlertCircle, Pause, Play, RotateCcw, Volume2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import { Button, Spinner } from './ui'

/** Patient-facing spoken Bangla reply. Never pretends audio exists when TTS fails. */
export default function SpokenReply({ sessionId }: { sessionId: string }) {
  const [text, setText] = useState<string | null>(null)
  const [src, setSrc] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [usingBrowserTts, setUsingBrowserTts] = useState(false)
  const audio = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    return () => {
      audio.current?.pause()
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  const findBanglaBrowserVoice = (): SpeechSynthesisVoice | null => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null
    const voices = window.speechSynthesis.getVoices()
    return (
      voices.find(
        (v) =>
          v.lang.toLowerCase().startsWith('bn') ||
          v.name.toLowerCase().includes('bangla') ||
          v.name.toLowerCase().includes('bengali')
      ) ?? null
    )
  }

  const speakWithBrowser = (textToSpeak: string) => {
    const banglaVoice = findBanglaBrowserVoice()
    if (!banglaVoice) {
      setError('ভয়েস চালানো যায়নি')
      setPlaying(false)
      return
    }

    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(textToSpeak)
    utterance.voice = banglaVoice
    utterance.lang = banglaVoice.lang || 'bn-BD'
    utterance.onstart = () => {
      setPlaying(true)
      setUsingBrowserTts(true)
    }
    utterance.onend = () => {
      setPlaying(false)
      setUsingBrowserTts(false)
    }
    utterance.onerror = () => {
      setPlaying(false)
      setUsingBrowserTts(false)
      setError('ভয়েস চালানো যায়নি')
    }
    window.speechSynthesis.speak(utterance)
  }

  const generate = async () => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.speech(sessionId)
      setText(r.text_bn)
      setSrc(`data:${r.mime_type};base64,${r.audio_base64}`)
    } catch (e) {
      // Cloud TTS failed: fetch text alone so patient can still see/read it
      let fallbackText = text
      try {
        const textRes = await api.spokenText(sessionId)
        fallbackText = textRes.text_bn
        setText(textRes.text_bn)
      } catch {
        /* text endpoint unavailable */
      }

      // Check if browser has a genuine Bangla voice
      const browserVoice = findBanglaBrowserVoice()
      if (fallbackText && browserVoice) {
        setError(null)
        speakWithBrowser(fallbackText)
      } else {
        setError('ভয়েস চালানো যায়নি')
      }
    } finally {
      setBusy(false)
    }
  }

  const toggle = () => {
    if (usingBrowserTts) {
      if (window.speechSynthesis.speaking) {
        if (window.speechSynthesis.paused) {
          window.speechSynthesis.resume()
          setPlaying(true)
        } else {
          window.speechSynthesis.pause()
          setPlaying(false)
        }
      }
      return
    }

    const a = audio.current
    if (!a) return
    if (a.paused) {
      void a.play()
    } else {
      a.pause()
    }
  }

  const replay = () => {
    if (usingBrowserTts && text) {
      speakWithBrowser(text)
      return
    }

    const a = audio.current
    if (!a) return
    a.currentTime = 0
    void a.play()
  }

  return (
    <section className="no-print rounded-2xl bg-white p-5 shadow-sm border border-deep/10" aria-label="Spoken reply for the patient">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-bold text-deep font-bangla">
          <Volume2 className="h-5 w-5 text-brand" aria-hidden /> রোগীর জন্য কথা বলা উত্তর / Spoken reply for patient
        </h2>
        {usingBrowserTts && (
          <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-900">
            Browser TTS voice
          </span>
        )}
      </div>

      {!text && !busy && (
        <div className="mt-3">
          <Button className="min-h-12 px-6 text-base font-semibold" onClick={generate}>
            <Volume2 className="h-5 w-5 mr-2" aria-hidden /> <span lang="bn">উত্তর শুনুন (Play spoken reply)</span>
          </Button>
        </div>
      )}

      {busy && (
        <div className="mt-3">
          <Spinner label="Generating Bangla speech…" />
        </div>
      )}

      {text && (
        <div className="mt-3 rounded-xl bg-soft p-4 border border-deep/10">
          <p className="text-xs font-semibold text-ink/60 uppercase tracking-wide mb-1">
            কথোপকথন পাঠ্য / Spoken transcript:
          </p>
          <p className="font-bangla text-xl leading-relaxed text-deep" lang="bn" data-testid="spoken-text">
            {text}
          </p>
        </div>
      )}

      {/* Audio playback controls */}
      {(src || usingBrowserTts) && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {src && (
            <audio
              ref={audio}
              src={src}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onEnded={() => setPlaying(false)}
            />
          )}
          <Button
            className="min-h-12 px-6 text-base font-semibold"
            onClick={toggle}
            aria-label={playing ? 'Pause audio' : 'Play audio'}
          >
            {playing ? <Pause className="h-5 w-5 mr-2" /> : <Play className="h-5 w-5 mr-2" />}
            {playing ? 'Pause' : 'Play'}
          </Button>
          <Button
            variant="secondary"
            className="min-h-12 px-5 text-base font-medium"
            onClick={replay}
            aria-label="Replay audio"
          >
            <RotateCcw className="h-5 w-5 mr-2" /> Replay
          </Button>
        </div>
      )}

      {/* Honest error display when speech synthesis fails */}
      {error && (
        <div className="mt-4 rounded-xl border border-danger/30 bg-red-50 p-4 text-red-950" role="alert">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="h-5 w-5 shrink-0 text-danger mt-0.5" aria-hidden />
            <div>
              <p className="font-bold text-danger font-bangla text-base" lang="bn">
                ভয়েস চালানো যায়নি
              </p>
              <p className="mt-1 text-sm text-red-900/90 leading-relaxed font-bangla">
                ভয়েস চালানো যায়নি — অডিও তৈরি করা সম্ভব হয়নি। অনুগ্রহ করে উপরের লেখাটি রোগীকে পড়ে শোনান।
              </p>
              <p className="mt-0.5 text-xs text-red-800/80">
                Audio unavailable — please read the text above aloud to the patient.
              </p>
              <div className="mt-3">
                <Button variant="secondary" className="min-h-10 text-xs" onClick={generate}>
                  Try again
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
