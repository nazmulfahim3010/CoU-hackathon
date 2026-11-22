import { Link } from 'react-router-dom'
import { Disclaimer } from '../components/ui'

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl bg-white p-5">
      <h2 className="text-xl font-bold text-deep">{title}</h2>
      <div className="mt-2 space-y-2">{children}</div>
    </section>
  )
}

export default function About() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-3xl font-bold text-deep">About Kotha (কথা)</h1>
      <p className="text-lg">
        Kotha is a patient-intake and clinical-documentation assistant. It helps a patient be understood and gives a
        clinician a structured, bilingual summary. It is <strong>not</strong> a diagnostic system, does not prescribe,
        and is a hackathon prototype, not a certified medical system.
      </p>
      <Block title="What is AI and what is not">
        <ul className="list-disc space-y-1 pl-5">
          <li><strong>AI:</strong> speech-to-text, dialect normalization (glossary + LLM), structured extraction, Bangla text-to-speech.</li>
          <li><strong>Not AI:</strong> the confirmation gate (enforced by the backend) and the red-flag engine (deterministic keyword rules with explicit negation handling; no LLM, no learned weights).</li>
        </ul>
      </Block>
      <Block title="Dialect support and limitations">
        <p>
          No dialect has yet been tested with native speakers, so Kotha does not claim support for any. Draft glossaries
          for Sylheti, Chittagonian and Noakhali are marked unverified. Standard Bangla speech recognition is known to
          struggle with regional dialects; the patient-confirmation step exists for that reason. Confidence scores are
          shown only when a model genuinely returns one (currently never).
        </p>
      </Block>
      <Block title="Red-flag rules">
        <p>
          Rules cover chest pain, difficulty breathing, heavy bleeding, vomiting blood, loss of consciousness, seizure,
          possible stroke signs and fever in infants. They are draft rules that have <strong>not</strong> been clinically
          reviewed. An absent alert never means the patient is safe. Guidance is limited to seeking urgent care.
        </p>
      </Block>
      <Block title="Privacy">
        <ul className="list-disc space-y-1 pl-5">
          <li>No database; audio is never written to disk; text lives in server memory for the session (default 30 min) and is deleted on expiry or when a consultation is cleared.</li>
          <li>Audio is sent to the configured speech provider and text to the configured LLM provider. Review those providers’ terms before real use.</li>
          <li>The spoken reply uses fixed template text containing no patient information.</li>
          <li>The server logs event names only — never transcripts, audio or keys.</li>
        </ul>
      </Block>
      <Block title="Demo mode">
        <p>
          Demo samples are fictional, prepared texts that let you walk through the full flow without provider keys.
          They are labelled everywhere and are never presented as live recognition.
        </p>
      </Block>
      <Disclaimer className="text-base" />
      <Link to="/intake" className="inline-flex min-h-12 items-center rounded-xl bg-brand px-6 font-semibold text-white">
        Start Voice Consultation
      </Link>
    </div>
  )
}
