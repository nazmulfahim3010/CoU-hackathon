import { AlertTriangle, Loader2, ShieldAlert, FlaskConical, Radio } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { Mode } from '../types/api'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-brand text-white hover:bg-deep',
  secondary: 'bg-white text-deep border border-deep/30 hover:bg-soft',
  danger: 'bg-danger text-white hover:bg-red-800',
  ghost: 'text-deep hover:bg-deep/10',
}

export function Button({
  variant = 'primary',
  big = false,
  className = '',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; big?: boolean }) {
  return (
    <button
      {...rest}
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        big ? 'min-h-16 px-8 text-xl' : 'min-h-11 px-5 text-base'
      } ${VARIANTS[variant]} ${className}`}
    />
  )
}

export function Spinner({ label }: { label: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2">
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
      <span>{label}</span>
    </span>
  )
}

export function ErrorBox({ title, message, children }: { title: string; message: string; children?: ReactNode }) {
  return (
    <div role="alert" className="rounded-xl border border-danger/40 bg-red-50 p-4 text-danger">
      <p className="flex items-center gap-2 font-semibold">
        <AlertTriangle className="h-5 w-5" aria-hidden /> {title}
      </p>
      <p className="mt-1 text-ink">{message}</p>
      {children && <div className="mt-3 flex flex-wrap gap-2">{children}</div>}
    </div>
  )
}

export function ModeBadge({ mode }: { mode: Mode }) {
  return mode === 'demo' ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-warn/20 px-3 py-1 text-sm font-semibold text-amber-900" data-testid="mode-badge">
      <FlaskConical className="h-4 w-4" aria-hidden /> DEMO — prepared sample, not live AI
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-ok/15 px-3 py-1 text-sm font-semibold text-ok" data-testid="mode-badge">
      <Radio className="h-4 w-4" aria-hidden /> LIVE — real model processing
    </span>
  )
}

export const DISCLAIMER_EN = 'Kotha is not a diagnostic tool. Medical decisions must be made by a qualified healthcare professional.'
export const DISCLAIMER_BN = 'কথা কোনো রোগ নির্ণয়ের সরঞ্জাম নয়। চিকিৎসা সংক্রান্ত সব সিদ্ধান্ত যোগ্য স্বাস্থ্যসেবা পেশাদারকে নিতে হবে।'

export function Disclaimer({ className = '' }: { className?: string }) {
  return (
    <p className={`flex items-start gap-2 text-sm text-ink/80 ${className}`}>
      <ShieldAlert className="mt-1 h-4 w-4 shrink-0 text-deep" aria-hidden />
      <span>
        {DISCLAIMER_EN}
        <br />
        {DISCLAIMER_BN}
      </span>
    </p>
  )
}

export function StepDots({ step }: { step: number }) {
  const labels = ['কথা বলুন', 'যাচাই', 'প্রক্রিয়া', 'সারসংক্ষেপ']
  return (
    <ol className="mb-6 flex items-center justify-between sm:justify-start gap-2 sm:gap-4 lg:gap-6 text-sm w-full max-w-3xl" aria-label="Progress">
      {labels.map((l, i) => (
        <li key={l} className="flex items-center gap-2 lg:gap-3" aria-current={i === step ? 'step' : undefined}>
          <span
            className={`flex h-7 w-7 lg:h-8 lg:w-8 items-center justify-center rounded-full text-xs font-bold transition-all ${
              i <= step ? 'bg-brand text-white shadow-xs' : 'bg-deep/10 text-deep'
            }`}
          >
            {i + 1}
          </span>
          <span className={`hidden sm:inline text-xs sm:text-sm font-bangla ${i === step ? 'font-bold text-deep' : 'text-ink/60'}`}>{l}</span>
          {i < labels.length - 1 && <span className="h-0.5 w-6 sm:w-12 lg:w-20 bg-deep/20" aria-hidden />}
        </li>
      ))}
    </ol>
  )
}
