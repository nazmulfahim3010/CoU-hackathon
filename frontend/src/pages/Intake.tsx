import { FlaskConical, Mic, Pause, Play, RotateCcw, Square, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, ErrorBox, ModeBadge, Spinner, StepDots } from '../components/ui'
import { MAX_SECONDS, RECOMMENDED_MIN_SECONDS, useRecorder, isRecordingSupported } from '../hooks/useRecorder'
import { api } from '../services/api'
import { useFlow } from '../state/FlowContext'
import type { DemoScenario, Health } from '../types/api'

const ERROR_TEXT: Record<string, { t: string; d: string }> = {
  unsupported: { t: 'এই ব্রাউজারে রেকর্ড করা যাচ্ছে না', d: 'Recording is not supported in this browser. Try Chrome, Edge or Firefox over HTTPS/localhost, or use Demo mode.' },
  denied: { t: 'মাইক্রোফোনের অনুমতি দেওয়া হয়নি', d: 'Microphone permission was denied. Allow the microphone in the browser address bar, then try again.' },
  'no-device': { t: 'মাইক্রোফোন পাওয়া যায়নি', d: 'No microphone was found. Connect one and try again.' },
  failed: { t: 'রেকর্ডিং ব্যর্থ হয়েছে', d: 'Recording failed. Please try again.' },
}

export const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

function Recorder({ onSubmit }: { onSubmit: (b: Blob) => void }) {
  const r = useRecorder()
  const [playing, setPlaying] = useState(false)
  const [audioEl, setAudioEl] = useState<HTMLAudioElement | null>(null)
  const supported = isRecordingSupported()

  useEffect(() => () => audioEl?.pause(), [audioEl])

  const togglePlay = () => {
    if (!audioEl) return
    if (audioEl.paused) void audioEl.play()
    else audioEl.pause()
  }

  return (
    <div className="space-y-5 rounded-3xl bg-white p-5 shadow-sm sm:p-8">
      <div className="rounded-2xl bg-soft p-4 text-lg" lang="bn">
        <p className="font-semibold">কীভাবে বলবেন</p>
        <ul className="mt-1 list-disc pl-5">
          <li>বোতাম টিপে আপনার সমস্যার কথা নিজের ভাষায় বলুন।</li>
          <li>কবে থেকে হয়েছে, কতটা কষ্ট, কোনো ওষুধ খেয়েছেন কি না — বলুন।</li>
          <li>৩০ থেকে ৯০ সেকেন্ড বলুন। শেষ হলে থামান বোতাম টিপুন।</li>
        </ul>
      </div>

      {!supported && <ErrorBox title={ERROR_TEXT.unsupported.t} message={ERROR_TEXT.unsupported.d} />}
      {r.status === 'error' && r.error && <ErrorBox title={ERROR_TEXT[r.error].t} message={ERROR_TEXT[r.error].d} />}

      <div className="flex flex-col items-center gap-4 py-2">
        <div
          className={`flex h-28 w-28 items-center justify-center rounded-full text-white ${
            r.status === 'recording' ? 'rec-pulse bg-danger' : 'bg-brand'
          }`}
          aria-hidden
        >
          <Mic className="h-12 w-12" />
        </div>

        {r.status === 'recording' && (
          <div className="flex h-10 items-end gap-1" aria-label="Recording level" role="img">
            {Array.from({ length: 18 }).map((_, i) => (
              <span
                key={i}
                className="w-1.5 rounded bg-danger transition-all"
                style={{ height: `${8 + Math.max(0, r.level * 32 * (0.4 + 0.6 * Math.abs(Math.sin(i + r.seconds))))}px` }}
              />
            ))}
          </div>
        )}

        <p className="text-3xl font-bold tabular-nums" aria-live="polite" data-testid="timer">
          {fmt(r.seconds)} <span className="text-base font-normal text-ink/60">/ {fmt(MAX_SECONDS)}</span>
        </p>
        {r.status === 'recording' && r.seconds < RECOMMENDED_MIN_SECONDS && (
          <p className="text-ink/70" lang="bn">কমপক্ষে ৩০ সেকেন্ড বলার চেষ্টা করুন।</p>
        )}
        {r.status === 'recording' && r.seconds >= MAX_SECONDS && <p className="text-danger">সর্বোচ্চ সময় শেষ।</p>}

        {(r.status === 'idle' || r.status === 'error') && (
          <Button big onClick={r.start} disabled={!supported}>
            <Mic className="h-6 w-6" aria-hidden /> <span lang="bn">রেকর্ড শুরু করুন</span>
          </Button>
        )}
        {r.status === 'requesting' && <Spinner label="মাইক্রোফোনের অনুমতির অপেক্ষায়…" />}
        {r.status === 'recording' && (
          <Button big variant="danger" onClick={r.stop}>
            <Square className="h-6 w-6" aria-hidden /> <span lang="bn">থামান</span>
          </Button>
        )}
      </div>

      {r.status === 'recorded' && r.url && (
        <div className="space-y-4 border-t border-deep/10 pt-4">
          <p className="font-semibold" lang="bn">আপনার রেকর্ডিং শুনে দেখুন</p>
          <audio
            ref={setAudioEl}
            src={r.url}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            controls
            className="w-full"
          />
          <Button variant="secondary" onClick={togglePlay} className="sm:hidden">
            {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />} {playing ? 'Pause' : 'Play'}
          </Button>
          {r.seconds < RECOMMENDED_MIN_SECONDS && (
            <p className="text-amber-800" lang="bn">রেকর্ডিং ৩০ সেকেন্ডের কম। চাইলে আবার রেকর্ড করতে পারেন।</p>
          )}
          <div className="flex flex-wrap gap-3">
            <Button big onClick={() => r.blob && onSubmit(r.blob)}>
              <span lang="bn">জমা দিন</span>
            </Button>
            <Button variant="secondary" onClick={r.start}>
              <RotateCcw className="h-5 w-5" aria-hidden /> <span lang="bn">আবার রেকর্ড</span>
            </Button>
            <Button variant="ghost" onClick={r.discard}>
              <Trash2 className="h-5 w-5" aria-hidden /> <span lang="bn">বাতিল</span>
            </Button>
          </div>
          <p className="text-sm text-ink/60">The recording stays in your browser until you submit it, and is not stored on the server.</p>
        </div>
      )}
    </div>
  )
}

function DemoPicker({ onPick }: { onPick: (id: string) => void }) {
  const [list, setList] = useState<DemoScenario[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    api.scenarios().then(setList).catch((e: Error) => setErr(e.message))
  }, [])
  if (err) return <ErrorBox title="Could not load demo samples" message={err} />
  if (!list) return <Spinner label="Loading samples…" />
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-warn/60 bg-warn/10 p-4">
        <p className="flex items-center gap-2 font-semibold text-amber-900">
          <FlaskConical className="h-5 w-5" aria-hidden /> Demo mode
        </p>
        <p className="text-sm">
          These are fictional, synthetic sample statements. The text is <strong>prepared</strong>: it is not produced by
          speech recognition, and demo normalization and extraction outputs are prepared too. Glossary matching, the
          confirmation gate, the red-flag rules and the summary run for real.
        </p>
      </div>
      <ul className="grid gap-3 md:grid-cols-3">
        {list.map((s) => (
          <li key={s.id} className="flex flex-col rounded-2xl border border-deep/10 bg-white p-4">
            <p className="font-semibold">{s.title}</p>
            <p className="flex-1 text-sm text-ink/80">{s.purpose}</p>
            <p className="mt-2 text-xs text-ink/60">{s.dialect_label}. {s.patient_note}</p>
            <Button className="mt-3" onClick={() => onPick(s.id)}>Use this sample</Button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function Intake() {
  const { mode, setMode, setPending, reset } = useFlow()
  const nav = useNavigate()
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  const go = (p: Parameters<typeof setPending>[0]) => {
    reset()
    setPending(p)
    nav('/transcribe')
  }

  return (
    <div className="mx-auto max-w-3xl">
      <StepDots step={0} />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-deep" lang="bn">আপনার সমস্যার কথা বলুন</h1>
        <ModeBadge mode={mode} />
      </div>

      <div className="mb-4 inline-flex rounded-xl border border-deep/20 bg-white p-1" role="group" aria-label="Mode">
        {(['live', 'demo'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            aria-pressed={mode === m}
            className={`min-h-10 rounded-lg px-4 text-sm font-semibold ${mode === m ? 'bg-deep text-white' : 'text-deep'}`}
          >
            {m === 'live' ? 'Live voice' : 'Demo samples'}
          </button>
        ))}
      </div>

      {mode === 'live' && health && !health.live_mode_ready && (
        <div className="mb-4">
          <ErrorBox
            title="Live processing is not fully configured on this server"
            message={`Speech provider configured: ${health.providers.speech.configured ? 'yes' : 'no'}. Language model configured: ${health.providers.llm.configured ? 'yes' : 'no'}. Recording will work, but live processing needs API keys in backend/.env. You can use Demo samples meanwhile.`}
          >
            <Button variant="secondary" onClick={() => setMode('demo')}>Switch to Demo samples</Button>
          </ErrorBox>
        </div>
      )}
      {!health && <p className="mb-4 text-sm text-amber-800">Backend not reachable yet — start it with uvicorn (see README).</p>}

      {mode === 'live' ? <Recorder onSubmit={(blob) => go({ kind: 'audio', blob })} /> : <DemoPicker onPick={(id) => go({ kind: 'demo', scenarioId: id })} />}
    </div>
  )
}
