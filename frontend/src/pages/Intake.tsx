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
  onSubmit,
}: {
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
    <div className="space-y-6 rounded-3xl bg-white p-6 sm:p-8 lg:p-10 shadow-sm border border-deep/10 flex flex-col justify-center">
      {!supported && <ErrorBox title={ERROR_TEXT.unsupported.t} message={ERROR_TEXT.unsupported.d} />}
      {r.status === 'error' && r.error && (
        <ErrorBox title={ERROR_TEXT[r.error]?.t || ERROR_TEXT.failed.t} message={ERROR_TEXT[r.error]?.d || ERROR_TEXT.failed.d} />
      )}

      {/* Record and Timer Area */}
      <div className="flex flex-col items-center gap-5 py-3">
        <div
          className={`flex h-28 w-28 sm:h-32 sm:w-32 items-center justify-center rounded-full text-white shadow-md transition-all ${
            r.status === 'recording' ? 'rec-pulse bg-danger' : 'bg-brand'
          }`}
          aria-hidden
        >
          <Mic className="h-12 w-12 sm:h-14 sm:w-14" />
        </div>

        {r.status === 'recording' && (
          <div className="flex h-10 items-end gap-1.5" aria-label="Recording level" role="img">
            {Array.from({ length: 22 }).map((_, i) => (
              <span
                key={i}
                className="w-1.5 rounded-full bg-danger transition-all"
                style={{
                  height: `${8 + Math.max(0, r.level * 36 * (0.4 + 0.6 * Math.abs(Math.sin(i + r.seconds))))}px`,
                }}
              />
            ))}
          </div>
        )}

        <div className="text-center">
          <p className="text-3xl sm:text-4xl font-extrabold tabular-nums tracking-tight text-deep" aria-live="polite" data-testid="timer">
            {fmt(r.seconds)} <span className="text-lg sm:text-xl font-normal text-ink/50">/ {fmt(MAX_SECONDS)}</span>
          </p>
          <p className="text-xs text-ink/60 mt-0.5">
            {r.status === 'recording' ? 'রেকর্ডিং চলছে... কথা শেষ হলে থামান বোতাম চাপুন' : 'সর্বোচ্চ ৯০ সেকেন্ড রেকর্ড করতে পারবেন'}
          </p>
        </div>

        {r.status === 'recording' && r.seconds < RECOMMENDED_MIN_SECONDS && (
          <p className="text-sm text-amber-800 font-bangla text-center" lang="bn">
            কমপক্ষে ৩০ সেকেন্ড বলার চেষ্টা করুন। (Recommended: at least 30s)
          </p>
        )}
        {r.status === 'recording' && r.seconds >= MAX_SECONDS && (
          <p className="text-sm font-semibold text-danger">সর্বোচ্চ সময় (৯০ সেকেন্ড) শেষ। রেকর্ডিং স্বয়ংক্রিয়ভাবে থেমেছে।</p>
        )}

        {(r.status === 'idle' || r.status === 'error') && (
          <Button big onClick={r.start} disabled={!supported} className="min-h-14 px-8 text-lg font-bold shadow-sm">
            <Mic className="h-6 w-6" aria-hidden /> <span lang="bn">রেকর্ড শুরু করুন (Record)</span>
          </Button>
        )}
        {r.status === 'requesting' && <Spinner label="মাইক্রোফোনের অনুমতির অপেক্ষায়… (Waiting for mic permission)" />}
        {r.status === 'recording' && (
          <Button big variant="danger" onClick={r.stop} className="min-h-14 px-8 text-lg font-bold shadow-sm">
            <Square className="h-6 w-6" aria-hidden /> <span lang="bn">থামান (Stop)</span>
          </Button>
        )}
      </div>

      {/* Recorded Preview & Actions */}
      {r.status === 'recorded' && r.url && (
        <div className="space-y-4 border-t border-deep/10 pt-5">
          <p className="font-bold text-base sm:text-lg text-deep" lang="bn">আপনার রেকর্ডিং শুনে দেখুন (Review Recording)</p>
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
              className="min-h-12 px-6 font-bold"
            >
              <span lang="bn">Use this recording (জমা দিন)</span>
            </Button>
            <Button
              variant="secondary"
              onClick={r.start}
              className="min-h-12 px-5 font-semibold"
            >
              <RotateCcw className="h-5 w-5" aria-hidden /> <span lang="bn">Record again (আবার রেকর্ড)</span>
            </Button>
            <Button
              variant="ghost"
              onClick={r.discard}
              className="min-h-12 px-4 text-danger hover:bg-red-50"
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
          <FlaskConical className="h-5 w-5" aria-hidden /> Demo Mode — Prepared Sylheti Scenarios
        </p>
        <p className="text-sm text-text/80 mt-1">
          These 3 fictional scenarios let you try Kotha without a microphone or live API keys. The Sylheti sentences are copied from the team-verified glossary; the standard-Bangla rendering is prepared by the team and not independently verified. The baseline transcript is prepared text (labelled <code>demo_sample</code>), never speech recognition. The audio clips are a <strong>synthetic standard-Bangla voice, not a Sylheti speaker</strong>, so running live ASR on them shows only that the audio pipeline works, not how well Kotha recognises real Sylheti speech.</p>
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
                <div className="flex items-center justify-between gap-1 mb-1">
                  <p className="text-[11px] font-semibold text-ink/60 uppercase tracking-wide flex items-center gap-1">
                    <Volume2 className="h-3.5 w-3.5 text-brand" /> Play Demo Audio Clip
                  </p>
                  <span className="text-[10px] font-medium text-amber-900 bg-amber-100 rounded px-1.5 py-0.5">
                    Synthetic voice — not a real dialect speaker
                  </span>
                </div>
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
                      <span>Run live ASR on this synthetic clip (pipeline check)</span>
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
    <div className="w-full max-w-7xl mx-auto space-y-6 lg:space-y-8">
      <StepDots step={0} />

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-deep/10 pb-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-deep font-bangla" lang="bn">
            আপনার সমস্যার কথা বলুন (Voice Intake)
          </h1>
          <p className="text-xs sm:text-sm text-ink/70 mt-0.5">
            Describe your health symptoms in your regional dialect or select a prepared scenario.
          </p>
        </div>
        <ModeBadge mode={mode} />
      </div>

      <div className="grid gap-6 lg:gap-8 lg:grid-cols-12 lg:items-start">
        {/* Left Column: Mode Switch, Alerts, Instructions, and Context Selectors */}
        <div className="space-y-5 lg:col-span-5">
          {/* Intake Source Switch Tabs */}
          <div className="rounded-2xl border border-deep/15 bg-white p-3.5 sm:p-4 shadow-xs space-y-2">
            <span className="text-xs font-bold uppercase tracking-wider text-ink/60 block">
              ইনটেক মাধ্যম নির্বাচন (Intake Source)
            </span>
            <div className="inline-flex w-full rounded-xl border border-deep/20 bg-soft p-1" role="group" aria-label="Mode">
              {(['live', 'demo'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  aria-pressed={mode === m}
                  className={`flex-1 min-h-11 rounded-lg px-3 sm:px-4 text-xs sm:text-sm font-bold transition-all ${
                    mode === m ? 'bg-deep text-white shadow-sm' : 'text-deep hover:bg-white/70'
                  }`}
                >
                  {m === 'live' ? 'Live voice (মাইক্রোফোন)' : 'Demo samples (নমুনা)'}
                </button>
              ))}
            </div>
          </div>

          {mode === 'live' && health?.ffmpeg && !health.ffmpeg.available && (
            <ErrorBox
              title="ffmpeg is not installed on this server"
              message="Audio processing requires ffmpeg in the system PATH. Install ffmpeg on the server to record live audio, or use Demo samples meanwhile."
            >
              <Button variant="secondary" onClick={() => setMode('demo')}>
                Switch to Demo samples
              </Button>
            </ErrorBox>
          )}

          {mode === 'live' && health && (!health.providers.speech.configured || !health.providers.llm.configured) && (
            <ErrorBox
              title="Live processing is not fully configured on this server"
              message={`Speech provider configured: ${health.providers.speech.configured ? 'yes' : 'no'}. Language model configured: ${health.providers.llm.configured ? 'yes' : 'no'}. Audio processing (ffmpeg) available: ${health.ffmpeg?.available === false ? 'NO (install ffmpeg or run via Docker)' : 'yes'}. For live processing, configure a local model (download only) or API credentials in backend/.env. You can use Demo samples meanwhile.`}
            >
              <Button variant="secondary" onClick={() => setMode('demo')}>
                Switch to Demo samples
              </Button>
            </ErrorBox>
          )}
          {!health && (
            <p className="text-sm text-amber-800">
              Backend not reachable yet — start it with uvicorn (see README).
            </p>
          )}

          {/* Simple Bangla instructions */}
          <div className="rounded-3xl border border-deep/10 bg-white p-5 sm:p-6 shadow-sm space-y-2.5 font-bangla" lang="bn">
            <h2 className="text-lg sm:text-xl font-bold text-deep">
              বোতাম চাপুন এবং আপনার সমস্যার কথা নিজের ভাষায় বলুন।
            </h2>
            <ul className="list-disc space-y-1.5 pl-5 text-sm sm:text-base text-text leading-relaxed font-bangla">
              <li>কবে থেকে লক্ষণ শুরু হয়েছে, কোথায় ব্যথা বা কষ্ট, কোনো ওষুধ খেয়েছেন কি না তা স্পষ্ট করে বলুন।</li>
              <li>অন্তত ৩০ থেকে ৯০ সেকেন্ড নিজের ভাষায় কথা বলুন।</li>
              <li>কথা শেষ হলে নিচের থামান (Stop) বোতামটি চাপুন।</li>
            </ul>
          </div>

          {/* Patient Context Fields */}
          <div className="rounded-3xl border border-deep/10 bg-white p-5 sm:p-6 shadow-sm space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-deep/80">
              রোগীর প্রাথমিক তথ্য (Optional Patient Context)
            </h3>
            <div className="space-y-4">
              <div>
                <label htmlFor="age-group" className="block text-sm font-semibold text-deep mb-1">
                  রোগীর বয়সসীমা (Optional Age Group)
                </label>
                <select
                  id="age-group"
                  value={ageGroup}
                  onChange={(e) => setAgeGroup(e.target.value as AgeGroup)}
                  className="w-full rounded-xl border border-deep/20 bg-soft px-3.5 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-brand focus:bg-white"
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
                  className="w-full rounded-xl border border-deep/20 bg-soft px-3.5 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-brand focus:bg-white"
                >
                  <option value="not_sure">নিশ্চিত নই / Not sure</option>
                  <option value="sylheti">সিলেটি (Sylheti) — টিম-যাচাইকৃত শব্দকোষ; কথা এখনো পরীক্ষিত নয় / team-verified glossary, speech not yet tested</option>
                  <option value="standard">প্রমিত বাংলা (Standard Bangla)</option>
                </select>
                <span className="text-xs text-text/60 mt-1 block">আঞ্চলিক শব্দাবলি প্রমিত রূপান্তরে সহায়তা করে।</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Large Recorder Card or Demo Scenario Picker */}
        <div className="lg:col-span-7">
          {mode === 'live' ? (
            <Recorder onSubmit={(blob) => go({ kind: 'audio', blob, ageGroup, dialectHint })} />
          ) : (
            <DemoPicker onPick={(id) => go({ kind: 'demo', scenarioId: id })} />
          )}
        </div>
      </div>
    </div>
  )
}
