import { ArrowRight, Ear, FileText, Languages, Lock, Mic, ShieldCheck, Siren, Stethoscope, Volume2, UserCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Disclaimer } from '../components/ui'

const STEPS = [
  { icon: Mic, t: 'Speak', d: 'The patient describes the problem in their own dialect, 30–90 seconds.' },
  { icon: Ear, t: 'Transcribe', d: 'A pretrained Bangla speech model converts speech to text.' },
  { icon: Languages, t: 'Normalize', d: 'A curated glossary plus an LLM maps dialect words to standard Bangla.' },
  { icon: UserCheck, t: 'Confirm', d: 'The patient or helper reads, corrects and confirms. Nothing proceeds before this.' },
  { icon: FileText, t: 'Structure', d: 'Only the confirmed text is turned into a structured clinical note.' },
  { icon: Siren, t: 'Safety rules', d: 'Transparent, rule-based red-flag checks. No LLM involved.' },
  { icon: Volume2, t: 'Reply', d: 'A short spoken Bangla reply. The doctor gets a Bangla + English summary.' },
]

const DIALECTS = [
  { n: 'Sylheti (সিলেটি)', s: 'Glossary: draft entries, unverified' },
  { n: 'Chittagonian (চাটগাঁইয়া)', s: 'Glossary: draft entries, unverified' },
  { n: 'Noakhali (নোয়াখালী)', s: 'Glossary: draft entries, unverified' },
]

export default function Landing() {
  return (
    <div className="space-y-16">
      <section className="grid items-center gap-8 pt-4 md:grid-cols-2">
        <div>
          <p className="mb-3 inline-block rounded-full bg-brand/10 px-3 py-1 text-sm font-semibold text-deep">
            Healthcare accessibility · Hackathon prototype
          </p>
          <h1 className="text-4xl font-bold leading-tight text-deep md:text-5xl">
            Every Voice Deserves to Be Understood.
          </h1>
          <p className="mt-2 text-lg text-brand">Your Voice. Your Language. Better Understanding.</p>
          <p className="mt-4 text-lg">
            Kotha helps rural patients describe their health concerns in their own Bangla dialect, and gives
            clinicians a clear, bilingual intake summary — after the patient has confirmed every word.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              to="/intake"
              className="inline-flex min-h-14 items-center gap-2 rounded-xl bg-brand px-7 text-lg font-semibold text-white hover:bg-deep"
            >
              Start Voice Consultation <ArrowRight className="h-5 w-5" aria-hidden />
            </Link>
            <Link to="/about" className="inline-flex min-h-14 items-center rounded-xl border border-deep/30 bg-white px-6 font-semibold text-deep">
              How it works
            </Link>
          </div>
        </div>
        <div className="rounded-3xl bg-gradient-to-br from-deep to-brand p-6 text-white shadow-lg">
          <p className="text-sm uppercase tracking-wide text-white/70">Patient says</p>
          <p className="mt-1 text-xl" lang="bn">“…বুগত খুব ব্যতা, নিঃশ্বাস নিতে কষ্ট অয়”</p>
          <p className="mt-4 text-sm uppercase tracking-wide text-white/70">Standard Bangla (patient-confirmed)</p>
          <p className="mt-1 text-xl" lang="bn">“…বুকে খুব ব্যথা, নিঃশ্বাস নিতে কষ্ট হয়”</p>
          <p className="mt-4 text-sm uppercase tracking-wide text-white/70">Doctor sees</p>
          <p className="mt-1">Chest pain · difficulty breathing · rule-based urgent-care alert</p>
          <p className="mt-4 text-xs text-white/70">Illustrative fictional sample — not native-speaker verified.</p>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-deep">The dialect gap</h2>
        <p className="mt-2 max-w-3xl">
          Patients describe illness in the dialect spoken at home. Clinicians usually work in standard Bangla or English
          and can misread symptom words, body parts and time expressions. Speech recognition is built mainly for
          standard colloquial Bangla, so notes end up incomplete, consultations run longer, and warning signs get
          missed — hitting hardest those who live far from doctors.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-deep">How Kotha works</h2>
        <ol className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.t} className="rounded-2xl border border-deep/10 bg-white p-4">
              <s.icon className="h-6 w-6 text-brand" aria-hidden />
              <p className="mt-2 font-semibold">{i + 1}. {s.t}</p>
              <p className="text-sm text-ink/80">{s.d}</p>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-deep">Dialect support — stated honestly</h2>
        <p className="mt-2 max-w-3xl">
          Standard-Bangla speech models do not reliably handle regional dialects. Kotha has <strong>not</strong> yet
          been tested with native speakers in any dialect, so none is listed as supported. The glossary entries below
          are drafts awaiting review, and the confirmation step exists because recognition will make mistakes.
        </p>
        <ul className="mt-4 grid gap-3 sm:grid-cols-3">
          {DIALECTS.map((d) => (
            <li key={d.n} className="rounded-2xl border border-warn/50 bg-white p-4">
              <p className="font-semibold">{d.n}</p>
              <p className="text-sm text-amber-800">{d.s}</p>
              <p className="text-sm text-ink/60">Native-speaker tested: No</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl bg-white p-5">
          <h2 className="flex items-center gap-2 text-xl font-bold text-deep"><Mic className="h-5 w-5" aria-hidden />For patients</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Speak instead of typing; large buttons, simple Bangla.</li>
            <li>You read and correct the text before anything else happens.</li>
            <li>A spoken Bangla reply explains what happens next.</li>
          </ul>
        </div>
        <div className="rounded-2xl bg-white p-5">
          <h2 className="flex items-center gap-2 text-xl font-bold text-deep"><Stethoscope className="h-5 w-5" aria-hidden />For doctors</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>A one-screen Bangla + English summary, readable in about 30 seconds.</li>
            <li>Missing and uncertain information shown explicitly — never guessed.</li>
            <li>Visible, rule-based red-flag panel with the exact rules triggered.</li>
          </ul>
        </div>
      </section>

      <section className="rounded-2xl border border-deep/10 bg-white p-5">
        <h2 className="flex items-center gap-2 text-xl font-bold text-deep"><Lock className="h-5 w-5" aria-hidden />Privacy</h2>
        <p className="mt-2">
          No database. Audio and text are held in memory for the session only and discarded on expiry. Audio is sent to
          the configured speech provider and text to the configured language-model provider for processing; the
          prototype does not use analytics. See the About page for details.
        </p>
      </section>

      <section className="rounded-2xl border-l-4 border-deep bg-white p-5">
        <h2 className="flex items-center gap-2 text-xl font-bold text-deep"><ShieldCheck className="h-5 w-5" aria-hidden />Medical disclaimer</h2>
        <Disclaimer className="mt-2 text-base" />
      </section>
    </div>
  )
}
