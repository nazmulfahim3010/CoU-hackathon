import { Pause, Play, RotateCcw, Volume2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../services/api'
import { Button, ErrorBox, Spinner } from './ui'

/** Patient-facing spoken Bangla reply. Never pretends audio exists when TTS fails. */
export default function SpokenReply({ sessionId }: { sessionId: string }) {
  const [text, setText] = useState<string | null>(null)
  const [src, setSrc] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const audio = useRef<HTMLAudioElement | null>(null)

  useEffect(() => () => audio.current?.pause(), [])

  const generate = async () => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.speech(sessionId)
      setText(r.text_bn)
      setSrc(`data:${r.mime_type};base64,${r.audio_base64}`)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Audio could not be generated.')
      try {
        setText((await api.spokenText(sessionId)).text_bn) // show the words even without audio
      } catch {
        /* text unavailable too */
      }
    } finally {
      setBusy(false)
    }
  }

  const toggle = () => {
    const a = audio.current
    if (!a) return
    if (a.paused) void a.play()
    else a.pause()
  }
  const replay = () => {
    const a = audio.current
    if (!a) return
    a.currentTime = 0
    void a.play()
  }

  return (
    <section className="no-print rounded-2xl bg-white p-5" aria-label="Spoken reply for the patient">
      <h2 className="flex items-center gap-2 text-lg font-bold text-deep">
        <Volume2 className="h-5 w-5" aria-hidden /> রোগীর জন্য কথা বলা উত্তর / Spoken reply for the patient
      </h2>
      {!text && !busy && (
        <Button className="mt-3" onClick={generate}>
          <Volume2 className="h-5 w-5" aria-hidden /> <span lang="bn">উত্তর শুনুন</span>
        </Button>
      )}
      {busy && <p className="mt-3"><Spinner label="Generating Bangla speech…" /></p>}
      {text && (
        <p className="mt-3 rounded-xl bg-soft p-4 text-lg" lang="bn" data-testid="spoken-text">{text}</p>
      )}
      {src && (
        <div className="mt-3 flex flex-wrap gap-2">
          <audio
            ref={audio}
            src={src}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
          />
          <Button onClick={toggle}>
            {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />} {playing ? 'Pause' : 'Play'}
          </Button>
          <Button variant="secondary" onClick={replay}>
            <RotateCcw className="h-5 w-5" /> Replay
          </Button>
        </div>
      )}
      {error && (
        <div className="mt-3">
          <ErrorBox title="Audio unavailable — please read the text above aloud to the patient" message={error}>
            <Button variant="secondary" onClick={generate}>Try again</Button>
          </ErrorBox>
        </div>
      )}
    </section>
  )
}
