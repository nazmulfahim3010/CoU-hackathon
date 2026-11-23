import { FlaskConical, Mic, Pause, Play, Radio, RotateCcw, Sparkles, Square, Trash2, Volume2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, ErrorBox, ModeBadge, Spinner, StepDots } from '../components/ui'
import { MAX_SECONDS, RECOMMENDED_MIN_SECONDS, isRecordingSupported, useRecorder } from '../hooks/useRecorder'
import { api } from '../services/api'
import { useFlow, type AgeGroup, type DialectHint } from '../state/FlowContext'
import type { DemoSample, Health } from '../types/api'

const ERROR_TEXT: Record<string, { t: string; d: string }> = {
  unsupported: {
    t: 'এই ব্রাউজারে অডিও রেকর্ড করা যাচ্ছে না',
    d: 'Audio recording is not supported in this browser. Try Chrome, Edge or Firefox over HTTPS/localhost, or use Demo mode.',
  },
  denied: {
    t: 'মাইক্রোফোনের অনুমতি দেওয়া হয়নি',
    d: 'Microphone permission was denied. Please allow microphone access in your browser address bar, then try again.',
  },
  'no-device': {
    t: 'মাইক্রোফোন পাওয়া যায়নি',
    d: 'No microphone was found. Please connect a microphone and try again.',
  },
  'insecure-context': {
    t: 'অনিরাপদ সংযোগ — মাইক্রোফোন ব্যবহারের জন্য HTTPS প্রয়োজন',
    d: 'Insecure context. Microphone recording requires HTTPS or localhost.',
  },
  failed: {
    t: 'রেকর্ডিং শুরু করা যায়নি',
    d: 'Recording failed. Please try again.',
  },
}

export const fmt = (s: number) =>
  `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

function Recorder({
  ageGroup,
  setAgeGroup,
  dialectHint,
  setDialectHint,
  onSubmit,
}: {
  ageGroup: AgeGroup
  setAgeGroup: (a: AgeGroup) => void
  dialectHint: DialectHint
  setDialectHint: (d: DialectHint) => void
  onSubmit: (b: Blob) => void
}) {
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
    <div className="space-y-6 rounded-3xl bg-white p-5 shadow-sm sm:p-8">
      {/* Simple Bangla instructions */}
      <div className="rounded-2xl bg-bg border border-deep/10 p-5 text-lg font-bangla" lang="bn">
        <p className="text-xl font-bold text-deep">বোতাম চাপুন এবং আপনার সমস্যার কথা নিজের ভাষায় বলুন।</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-text">
          <li>কবে থেকে লক্ষণ শুরু হয়েছে, কোথায় ব্যথা বা কষ্ট, কোনো ওষুধ খেয়েছেন কি না তা স্পষ্ট করে বলুন।</li>
          <li>অন্তত ৩০ থেকে ৯০ সেকেন্ড নিজের ভাষায় কথা বলুন।</li>
          <li>কথা শেষ হলে নিচের থামান (Stop) বোতামটি চাপুন।</li>
        </ul>
      </div>

      {/* Optional Patient Context Fields */}
      <div className="grid gap-4 sm:grid-cols-2 rounded-2xl border border-deep/10 bg-soft p-4">
        <div>
          <label htmlFor="age-group" className="block text-sm font-semibold text-deep mb-1">
            রোগীর বয়সসীমা (Optional Age Group)
          </label>
          <select
            id="age-group"
            value={ageGroup}
            onChange={(e) => setAgeGroup(e.target.value as AgeGroup)}
            className="w-full rounded-xl border border-deep/20 bg-white px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-brand"
          >
            <option value="not_stated">বলা হয়নি / Not stated (Default)</option>
            <option value="infant">১ বছরের কম শিশু / Infant (under 1 year)</option>
            <option value="child">শিশু ১-১২ বছর / Child (1-12 years)</option>
            <option value="adult">প্রাপ্তবয়স্ক ১৩-৫৯ বছর / Adult (13-59 years)</option>
            <option value="older_adult">বয়োজ্যেষ্ঠ ৬০+ বছর / Older adult (60+ years)</option>
          </select>
          <span className="text-xs text-text/60 mt-1 block">জরুরি লক্ষণ ও শিশুর জ্বর মূল্যায়নে সাহায্য করে।</span>
        </div>

        <div>
          <label htmlFor="dialect-hint" className="block text-sm font-semibold text-deep mb-1">
            আঞ্চলিক ভাষা বা উপভাষা (Dialect)
          </label>
          <select
            id="dialect-hint"
            value={dialectHint}
            onChange={(e) => setDialectHint(e.target.value as DialectHint)}
            className="w-full rounded-xl border border-deep/20 bg-white px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-brand"
          >
            <option value="not_sure">নিশ্চিত নই / Not sure</option>
            <option value="sylheti">সিলেটি (Sylheti) — পরীক্ষাধীন / not yet tested</option>
            <option value="chittagonian">চাঁটগাঁইয়া (Chittagonian) — পরীক্ষাধীন / not yet tested</option>
            <option value="noakhali">নোয়াখাইল্লা (Noakhali) — পরীক্ষাধীন / not yet tested</option>
            <option value="standard">প্রমিত বাংলা (Standard Bangla)</option>
          </select>
          <span className="text-xs text-text/60 mt-1 block">আঞ্চলিক শব্দাবলি প্রমিত রূপান্তরে সহায়তা করে।</span>
        </div>
      </div>

      {!supported && <ErrorBox title={ERROR_TEXT.unsupported.t} message={ERROR_TEXT.unsupported.d} />}
      {r.status === 'error' && r.error && (
        <ErrorBox title={ERROR_TEXT[r.error]?.t || ERROR_TEXT.failed.t} message={ERROR_TEXT[r.error]?.d || ERROR_TEXT.failed.d} />
      )}

      {/* Record and Timer Area */}
      <div className="flex flex-col items-center gap-4 py-3">
        <div
          className={`flex h-28 w-28 items-center justify-center rounded-full text-white shadow-md transition-all ${
            r.status === 'recording' ? 'rec-pulse bg-danger' : 'bg-brand'
          }`}
          aria-hidden
        >
          <Mic className="h-12 w-12" />
        </div>

        {r.status === 'recording' && (
          <div className="flex h-10 items-end gap-1" aria-label="Recording level" role="img">
            {Array.from({ length: 20 }).map((_, i) => (
              <span
                key={i}
                className="w-1.5 rounded bg-danger transition-all"
                style={{
                  height: `${8 + Math.max(0, r.level * 32 * (0.4 + 0.6 * Math.abs(Math.sin(i + r.seconds))))}px`,
                }}
              />
            ))}
          </div>
        )}

        <p className="text-3xl font-bold tabular-nums" aria-live="polite" data-testid="timer">
          {fmt(r.seconds)} <span className="text-base font-normal text-ink/60">/ {fmt(MAX_SECONDS)}</span>
        </p>

        {r.status === 'recording' && r.seconds < RECOMMENDED_MIN_SECONDS && (
          <p className="text-sm text-text/70 font-bangla" lang="bn">
            কমপক্ষে ৩০ সেকেন্ড বলার চেষ্টা করুন। (Recommended: at least 30s)
          </p>
        )}
        {r.status === 'recording' && r.seconds >= MAX_SECONDS && (
          <p className="text-sm font-semibold text-danger">সর্বোচ্চ সময় (৯০ সেকেন্ড) শেষ। রেকর্ডিং স্বয়ংক্রিয়ভাবে থেমেছে।</p>
        )}

        {(r.status === 'idle' || r.status === 'error') && (
          <Button big onClick={r.start} disabled={!supported} className="min-h-14 px-8 text-lg">
            <Mic className="h-6 w-6" aria-hidden /> <span lang="bn">রেকর্ড শুরু করুন (Record)</span>
          </Button>
        )}
        {r.status === 'requesting' && <Spinner label="মাইক্রোফোনের অনুমতির অপেক্ষায়… (Waiting for mic permission)" />}
        {r.status === 'recording' && (
          <Button big variant="danger" onClick={r.stop} className="min-h-14 px-8 text-lg">
            <Square className="h-6 w-6" aria-hidden /> <span lang="bn">থামান (Stop)</span>
          </Button>
        )}
      </div>

      {/* Recorded Preview & Actions */}
      {r.status === 'recorded' && r.url && (
        <div className="space-y-4 border-t border-deep/10 pt-5">
          <p className="font-semibold text-lg text-deep" lang="bn">আপনার রেকর্ডিং শুনে দেখুন (Review Recording)</p>
          <audio
            ref={setAudioEl}
            src={r.url}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            controls
            className="w-full"
          />
          <Button variant="secondary" onClick={togglePlay} className="sm:hidden min-h-11">
            {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />} {playing ? 'Pause' : 'Play'}
          </Button>
          {r.seconds < RECOMMENDED_MIN_SECONDS && (
            <p className="text-sm text-amber-800 font-bangla" lang="bn">
              রেকর্ডিং ৩০ সেকেন্ডের কম। আরও বিস্তারিত বলতে চাইলে আবার রেকর্ড করতে পারেন।
            </p>
          )}

          <div className="flex flex-wrap gap-3 pt-2">
            <Button
              big
              onClick={() => r.blob && onSubmit(r.blob)}
              className="min-h-12 px-6"
            >
              <span lang="bn">Use this recording (জমা দিন)</span>
            </Button>
            <Button
              variant="secondary"
              onClick={r.start}
              className="min-h-12 px-5"
            >
              <RotateCcw className="h-5 w-5" aria-hidden /> <span lang="bn">Record again (আবার রেকর্ড)</span>
            </Button>
            <Button
              variant="ghost"
              onClick={r.discard}
              className="min-h-12 px-5 text-danger hover:bg-red-50"
            >
              <Trash2 className="h-5 w-5" aria-hidden /> <span lang="bn">Discard (বাতিল)</span>
            </Button>
          </div>
          <p className="text-xs text-ink/60">
            রেকর্ডিংটি জমা দেওয়ার আগে আপনার ব্রাউজারেই থাকে; সার্ভারে কোনো অডিও ফাইল স্থায়ীভাবে সংরক্ষণ করা হয় না।
          </p>
        </div>
      )}
    </div>
  )
}

function DemoPicker({ onPick }: { onPick: (id: string) => void }) {
  const [list, setList] = useState<DemoSample[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [asrLoading, setAsrLoading] = useState<Record<string, boolean>>({})
  const [asrResults, setAsrResults] = useState<
    Record<string, { transcript: string; provider: string; model: string | null }>
  >({})
  const [asrErrors, setAsrErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    api
      .demoSamples()
      .then(setList)
      .catch((e: Error) => setErr(e.message))
  }, [])

  const runLiveAsr = async (sampleId: string) => {
    setAsrLoading((prev) => ({ ...prev, [sampleId]: true }))
    setAsrErrors((prev) => {
      const copy = { ...prev }
      delete copy[sampleId]
      return copy
    })
    try {
      const res = await api.demoLiveAsr(sampleId)
      setAsrResults((prev) => ({
        ...prev,
        [sampleId]: { transcript: res.transcript, provider: res.provider, model: res.model },
      }))
    } catch (e: any) {
      setAsrErrors((prev) => ({
        ...prev,
        [sampleId]: e?.message || 'Live speech recognition failed on this audio sample.',
      }))
    } finally {
      setAsrLoading((prev) => ({ ...prev, [sampleId]: false }))
    }
  }

  if (err) return <ErrorBox title="Could not load demo samples" message={err} />
  if (!list) return <Spinner label="Loading samples…" />

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-warn/60 bg-warn/10 p-4">
        <p className="flex items-center gap-2 font-semibold text-amber-900">
          <FlaskConical className="h-5 w-5" aria-hidden /> Demo Mode — Prepared Dialect Scenarios
        </p>
        <p className="text-sm text-text/80 mt-1">
          These 3 fictional scenarios let you evaluate Kotha without audio hardware or live API keys. Audio clips can be played directly in your browser. The baseline transcript is a prepared sample (labelled as <code>demo_sample</code>, never speech recognition; unverified by native speakers). You can also run live ASR on the clip to compare actual model performance.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {list.map((s) => {
          const isLoadingAsr = Boolean(asrLoading[s.id])
          const asr = asrResults[s.id]
          const asrErr = asrErrors[s.id]

          return (
            <div
              key={s.id}
              className="flex flex-col rounded-2xl border border-deep/15 bg-white p-5 shadow-sm space-y-3"
            >
              <div>
                <div className="flex items-start justify-between gap-1">
                  <h3 className="font-bold text-deep text-base">{s.title}</h3>
                  <span className="rounded bg-soft px-2 py-0.5 text-[11px] font-semibold text-deep capitalize shrink-0">
                    {s.dialect}
                  </span>
                </div>
                <p className="text-xs text-ink/75 mt-1">{s.purpose}</p>
              </div>

              {/* Browser Audio Player */}
              <div className="rounded-xl bg-soft p-2.5">
                <p className="text-[11px] font-semibold text-ink/60 uppercase tracking-wide flex items-center gap-1 mb-1">
                  <Volume2 className="h-3.5 w-3.5 text-brand" /> Play Demo Audio Clip
                </p>
                <audio
                  controls
                  src={s.audio_url}
                  className="w-full h-8"
                  preload="metadata"
                />
              </div>

              {/* Prepared Baseline Transcript */}
              <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-3 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <p className="font-bold text-blue-900 text-[11px] uppercase tracking-wide">
                    Sample / Unverified Dialect Transcript
                  </p>
                  <span className="text-[10px] text-blue-700 bg-blue-100 rounded px-1.5 py-0.2">
                    Source: demo_sample
                  </span>
                </div>
                <p className="font-bangla text-sm text-blue-950 font-medium" lang="bn">
                  "{s.original_transcript}"
                </p>
                <p className="text-[11px] text-blue-800">
                  <strong>Std:</strong> <span lang="bn">{s.standard_bangla}</span>
                </p>
              </div>

              {/* Optional Live ASR on Sample */}
              {asr && (
                <div className="rounded-xl border border-emerald-300 bg-emerald-50/80 p-3 text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-emerald-900 text-[11px] uppercase tracking-wide">
                      Live Speech Recognition Result
                    </p>
                    <span className="text-[10px] text-emerald-800 bg-emerald-100 rounded px-1.5 py-0.2">
                      {asr.provider} {asr.model ? `(${asr.model})` : ''}
                    </span>
                  </div>
                  <p className="font-bangla text-sm text-emerald-950" lang="bn">
                    "{asr.transcript}"
                  </p>
                </div>
              )}

              {asrErr && (
                <div className="rounded-xl border border-danger/30 bg-red-50 p-2.5 text-xs text-danger">
                  <p className="font-semibold">Live ASR Note:</p>
                  <p>{asrErr}</p>
                </div>
              )}

              <div className="pt-2 flex flex-col gap-2 mt-auto">
                <Button
                  variant="secondary"
                  onClick={() => runLiveAsr(s.id)}
                  disabled={isLoadingAsr}
                  className="min-h-10 text-xs py-1.5"
                >
                  {isLoadingAsr ? (
                    <Spinner label="Running ASR…" />
                  ) : (
                    <>
                      <Radio className="h-3.5 w-3.5 text-brand" />
                      <span>Run live ASR on this sample</span>
                    </>
                  )}
                </Button>

                <Button
                  onClick={() => onPick(s.id)}
                  className="min-h-11 text-sm font-bold"
                >
                  <Sparkles className="h-4 w-4" />
                  <span>Use this sample (ডেমো শুরু করুন)</span>
                </Button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function Intake() {
  const { mode, setMode, ageGroup, setAgeGroup, dialectHint, setDialectHint, setPending, reset } = useFlow()
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
    <div className="mx-auto max-w-3xl space-y-6">
      <StepDots step={0} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-deep font-bangla" lang="bn">
          আপনার সমস্যার কথা বলুন (Voice Intake)
        </h1>
        <ModeBadge mode={mode} />
      </div>

      <div className="inline-flex rounded-xl border border-deep/20 bg-white p-1" role="group" aria-label="Mode">
        {(['live', 'demo'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            aria-pressed={mode === m}
            className={`min-h-11 rounded-lg px-5 text-sm font-semibold transition-colors ${
              mode === m ? 'bg-deep text-white shadow-sm' : 'text-deep hover:bg-soft'
            }`}
          >
            {m === 'live' ? 'Live voice' : 'Demo samples'}
          </button>
        ))}
      </div>

      {mode === 'live' && health?.ffmpeg && !health.ffmpeg.available && (
        <div>
          <ErrorBox
            title="ffmpeg is not installed on this server"
            message="Audio processing requires ffmpeg in the system PATH. Install ffmpeg on the server to record live audio, or use Demo samples meanwhile."
          >
            <Button variant="secondary" onClick={() => setMode('demo')}>
              Switch to Demo samples
            </Button>
          </ErrorBox>
        </div>
      )}

      {mode === 'live' && health && (!health.providers.speech.configured || !health.providers.llm.configured) && (
        <div>
          <ErrorBox
            title="Live processing is not fully configured on this server"
            message={`Speech provider configured: ${health.providers.speech.configured ? 'yes' : 'no'}. Language model configured: ${health.providers.llm.configured ? 'yes' : 'no'}. For live processing, configure a local model (download only) or API credentials in backend/.env (configurable via LLM_PROVIDER / LLM_MODEL / LLM_BASE_URL). You can use Demo samples meanwhile.`}
          >
            <Button variant="secondary" onClick={() => setMode('demo')}>
              Switch to Demo samples
            </Button>
          </ErrorBox>
        </div>
      )}
      {!health && (
        <p className="text-sm text-amber-800">
          Backend not reachable yet — start it with uvicorn (see README).
        </p>
      )}

      {mode === 'live' ? (
        <Recorder
          ageGroup={ageGroup}
          setAgeGroup={setAgeGroup}
          dialectHint={dialectHint}
          setDialectHint={setDialectHint}
          onSubmit={(blob) => go({ kind: 'audio', blob, ageGroup, dialectHint })}
        />
      ) : (
        <DemoPicker onPick={(id) => go({ kind: 'demo', scenarioId: id })} />
      )}
    </div>
  )
}
