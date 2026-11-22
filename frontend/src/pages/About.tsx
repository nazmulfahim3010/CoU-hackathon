import { ArrowRight, BookOpen, ExternalLink, HeartPulse, Lock, ShieldCheck, Siren, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Disclaimer } from '../components/ui'

function SectionBlock({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-3xl border border-deep/10 bg-white p-6 sm:p-8 shadow-sm space-y-3">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10 text-brand">
          <Icon className="h-5 w-5" aria-hidden />
        </span>
        <h2 className="text-xl font-bold text-deep">{title}</h2>
      </div>
      <div className="text-sm sm:text-base text-ink/80 leading-relaxed space-y-2.5 pt-1">
        {children}
      </div>
    </section>
  )
}

export default function About() {
  return (
    <div className="mx-auto max-w-4xl space-y-8 pb-12">
      {/* Title & Introduction */}
      <div className="space-y-3">
        <h1 className="text-3xl sm:text-4xl font-extrabold text-deep">About Kotha (কথা)</h1>
        <p className="text-lg sm:text-xl text-brand font-semibold font-bangla" lang="bn">
          আপনার কণ্ঠ। আপনার ভাষা। উন্নত স্বাস্থ্যসেবা।
        </p>
        <p className="text-base sm:text-lg text-ink/85 leading-relaxed">
          Kotha is an AI-assisted patient intake and clinical documentation prototype designed for Bangladesh's linguistically diverse healthcare landscape. It enables patients to voice health concerns in their regional dialect, empowers them to confirm the text, and generates a structured bilingual clinical summary for healthcare providers.
        </p>
      </div>

      {/* 1. The Dialect Barrier */}
      <SectionBlock icon={HeartPulse} title="The Dialect Barrier in Bangladesh Healthcare">
        <p>
          Bangladesh is home to more than 170 million people. Although Standard Colloquial Bangla is the language of instruction and official business, the majority of the rural population speaks distinctive regional dialects—such as Sylheti, Chittagonian, and Noakhali.
        </p>
        <p>
          In healthcare, this linguistic divergence creates serious clinical bottlenecks:
        </p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li><strong>Anatomical & Symptom Terminology:</strong> Regional terms for pain (e.g., <em>ব্যতা</em>, <em>বিষ</em>), body parts (e.g., <em>বুগত</em>, <em>ফেডে</em>, <em>মাতাত</em>), and time expressions differ from standard Bangla medical texts.</li>
          <li><strong>Consultation Delays:</strong> Clinicians trained in urban teaching hospitals often struggle to parse dialect terms rapidly, increasing triage time in high-volume rural clinics.</li>
          <li><strong>Diagnostic Risk:</strong> Crucial symptoms—such as radiating chest pain or infant lethargy—can be misinterpreted or overlooked when patients feel pressured to communicate in unfamiliar standard registers.</li>
        </ul>
      </SectionBlock>

      {/* 2. Our Approach */}
      <SectionBlock icon={BookOpen} title="Our Four-Pillar Clinical Pipeline">
        <p>
          Kotha bridges this divide through four tightly coordinated pillars:
        </p>
        <div className="grid gap-3 sm:grid-cols-2 pt-2">
          <div className="rounded-2xl bg-soft p-4 border border-deep/5 space-y-1">
            <h3 className="font-bold text-deep text-sm">1. Dialect-Aware ASR</h3>
            <p className="text-xs text-ink/70">Pretrained Bangla acoustic models convert speech to raw phonetic text, allowing patients to speak without typing barriers.</p>
          </div>
          <div className="rounded-2xl bg-soft p-4 border border-deep/5 space-y-1">
            <h3 className="font-bold text-deep text-sm">2. Curated Normalization</h3>
            <p className="text-xs text-ink/70">A longest-first dialect glossary combined with LLM context mapping converts regional idioms into standard colloquial Bangla.</p>
          </div>
          <div className="rounded-2xl bg-soft p-4 border border-deep/5 space-y-1">
            <h3 className="font-bold text-deep text-sm">3. Deterministic Safety Rules</h3>
            <p className="text-xs text-ink/70">Zero learned models or LLMs are involved in safety triage. Transparent keyword rules evaluate emergency red flags with negation protection.</p>
          </div>
          <div className="rounded-2xl bg-soft p-4 border border-deep/5 space-y-1">
            <h3 className="font-bold text-deep text-sm">4. Bilingual Summary</h3>
            <p className="text-xs text-ink/70">A concise Bangla + English intake card readable in under 30 seconds, surfacing missing information explicitly as "Ask about...".</p>
          </div>
        </div>
      </SectionBlock>

      {/* 3. Safety Architecture & Boundaries */}
      <SectionBlock icon={ShieldCheck} title="Safety Architecture: What Is AI and What Is Not">
        <p>
          In healthcare AI, boundary clarity is essential for patient safety:
        </p>
        <div className="overflow-x-auto pt-1">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="border-b border-deep/20 text-deep">
                <th className="pb-2 font-bold">Pipeline Stage</th>
                <th className="pb-2 font-bold">Technology Used</th>
                <th className="pb-2 font-bold">Fail-Safe Guardrail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-deep/10 text-xs sm:text-sm">
              <tr>
                <td className="py-2 font-semibold">Speech Recognition</td>
                <td className="py-2 text-ink/70">Acoustic ASR (Whisper / HF)</td>
                <td className="py-2 text-ink/80">Patient reviews and can re-record or type manually</td>
              </tr>
              <tr>
                <td className="py-2 font-semibold">Dialect Normalization</td>
                <td className="py-2 text-ink/70">Curated Glossary + LLM</td>
                <td className="py-2 text-ink/80">Mandatory Confirmation Gate — backend blocks extraction without user approval</td>
              </tr>
              <tr>
                <td className="py-2 font-semibold">Clinical Extraction</td>
                <td className="py-2 text-ink/70">LLM structured output</td>
                <td className="py-2 text-ink/80">Strictly grounded in confirmed text; no inferred diagnosis or medication suggestions</td>
              </tr>
              <tr>
                <td className="py-2 font-semibold text-danger">Red-Flag Safety Triage</td>
                <td className="py-2 font-bold text-danger">Deterministic Keyword Rules (NO AI)</td>
                <td className="py-2 text-ink/80">Rule-based pattern matching with clause-bounded negation and age co-occurrence</td>
              </tr>
              <tr>
                <td className="py-2 font-semibold">Spoken Patient Guidance</td>
                <td className="py-2 text-ink/70">Deterministic Bangla Template + TTS</td>
                <td className="py-2 text-ink/80">Template text carries zero patient-identifiable data; purely procedural reassurance</td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionBlock>

      {/* 4. Privacy & Zero-Retention Model */}
      <SectionBlock icon={Lock} title="Zero-Retention Privacy Architecture">
        <ul className="list-disc space-y-2 pl-5">
          <li><strong>No Disk or Database Storage:</strong> Audio and transcript data exist exclusively in ephemeral process memory. Once the session expires (default 30 minutes) or is explicitly ended, all in-memory representations are permanently deleted.</li>
          <li><strong>Ephemeral Audio Processing:</strong> Audio recordings are temporarily converted in a memory-mapped or temp scratch buffer with immediate file deletion in <code>finally</code> blocks.</li>
          <li><strong>Redacted System Telemetry:</strong> Loggers are strictly filtered to ensure patient transcripts, names, contact details, and API credentials are never written to standard output or log streams.</li>
        </ul>
      </SectionBlock>

      {/* 5. Dialect Limitations & Medical Disclaimer */}
      <SectionBlock icon={Siren} title="Limitations and Clinical Disclaimer">
        <div className="space-y-3">
          <p>
            <strong>Honest Dialect Validation:</strong> Kotha currently features starter glossaries for Sylheti, Chittagonian, and Noakhali. These entries are drafts awaiting formal community and native speaker validation. Kotha makes no unverified claims of native fluency.
          </p>
          <p>
            <strong>Red Flag Rules Status:</strong> The starter safety rules (covering chest pain, respiratory distress, infant fever, heavy bleeding, loss of consciousness, seizures, dehydration, and stroke symptoms) are marked as <code>pending_clinical_review</code>. Absence of a red flag alert does <strong>never</strong> indicate that a patient is clinically stable.
          </p>
          <Disclaimer className="pt-2" />
        </div>
      </SectionBlock>

      {/* 6. Team & Credits */}
      <SectionBlock icon={Users} title="Team & Hackathon Credits">
        <p>
          Kotha was built for the <strong>CoU Hackathon</strong> by a dedicated team passionate about breaking linguistic barriers in digital health.
        </p>
        <p className="text-xs text-ink/70">
          Built with FastAPI, React, TypeScript, Tailwind CSS, Hugging Face Transformers, and deterministic rule engines.
        </p>
        <div className="pt-2">
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand hover:underline"
          >
            <span>View Architecture & Documentation on GitHub / README</span>
            <ExternalLink className="h-4 w-4" aria-hidden />
          </a>
        </div>
      </SectionBlock>

      {/* CTA Button */}
      <div className="pt-4 flex justify-center">
        <Link
          to="/intake"
          className="inline-flex min-h-14 items-center gap-2 rounded-2xl bg-brand px-8 text-lg font-bold text-white shadow-md hover:bg-deep transition-all"
        >
          <span>Start Voice Consultation / পরামর্শ শুরু করুন</span>
          <ArrowRight className="h-5 w-5" aria-hidden />
        </Link>
      </div>
    </div>
  )
}
