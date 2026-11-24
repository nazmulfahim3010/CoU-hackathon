import { FlaskConical, Mic, Radio } from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { Disclaimer } from '../components/ui'
import { useFlow } from '../state/FlowContext'

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-bold text-deep shrink-0">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand text-white shadow-sm">
        <Mic className="h-5 w-5" aria-hidden />
      </span>
      <span className="text-xl tracking-tight">
        Kotha <span className="text-brand">কথা</span>
      </span>
    </Link>
  )
}

export default function AppLayout() {
  const { mode, setMode } = useFlow()

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors ${
      isActive ? 'bg-deep/10 text-deep font-semibold' : 'text-ink/70 hover:text-deep'
    }`

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink selection:bg-brand/20">
      <header className="no-print sticky top-0 z-20 border-b border-deep/10 bg-white/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8 py-3">
          <Logo />

          <nav className="hidden md:flex items-center gap-1.5 lg:gap-4 text-sm" aria-label="Main navigation">
            <a href="/#how-it-works" className="rounded-lg px-3 py-1.5 text-ink/70 hover:text-deep hover:bg-soft transition-colors font-medium">
              How it works
            </a>
            <a href="/#dialects" className="rounded-lg px-3 py-1.5 text-ink/70 hover:text-deep hover:bg-soft transition-colors font-medium">
              Dialects
            </a>
            <a href="/#privacy" className="rounded-lg px-3 py-1.5 text-ink/70 hover:text-deep hover:bg-soft transition-colors font-medium">
              Privacy
            </a>
            <NavLink to="/about" className={linkClass}>
              About
            </NavLink>
          </nav>

          <div className="flex items-center gap-2 sm:gap-4">
            {/* Live / Demo Mode Switch */}
            <div
              className="inline-flex rounded-xl border border-deep/20 bg-soft p-0.5 text-xs font-semibold"
              role="group"
              aria-label="System mode"
            >
              <button
                type="button"
                onClick={() => setMode('live')}
                aria-pressed={mode === 'live'}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 transition-all ${
                  mode === 'live'
                    ? 'bg-ok text-white shadow-sm font-bold'
                    : 'text-ink/70 hover:text-deep'
                }`}
              >
                <Radio className="h-3.5 w-3.5" aria-hidden />
                <span>Live</span>
              </button>
              <button
                type="button"
                onClick={() => setMode('demo')}
                aria-pressed={mode === 'demo'}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 transition-all ${
                  mode === 'demo'
                    ? 'bg-amber-600 text-white shadow-sm font-bold'
                    : 'text-ink/70 hover:text-deep'
                }`}
              >
                <FlaskConical className="h-3.5 w-3.5" aria-hidden />
                <span>Demo</span>
              </button>
            </div>

            <Link
              to="/intake"
              className="inline-flex min-h-10 items-center justify-center rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-deep transition-colors"
            >
              <span className="sm:hidden">Start</span>
              <span className="hidden sm:inline">Start / শুরু করুন</span>
            </Link>
          </div>
        </div>

        {/* Persistent Demo Mode Banner across all pages */}
        {mode === 'demo' && (
          <div
            className="border-t border-amber-300 bg-amber-100/90 px-4 py-1.5 text-center text-xs sm:text-sm font-semibold text-amber-950 flex items-center justify-center gap-2"
            role="status"
            aria-live="polite"
          >
            <FlaskConical className="h-4 w-4 text-amber-800 shrink-0" aria-hidden />
            <span>DEMO — prepared sample (লাইভ এআই নয় · Prepared synthetic sample data)</span>
          </div>
        )}
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 sm:px-6 lg:px-8 py-6 lg:py-8">
        <Outlet />
      </main>

      <footer className="border-t border-deep/10 bg-white">
        <div className="mx-auto max-w-7xl space-y-4 px-4 sm:px-6 lg:px-8 py-8">
          <Disclaimer />
          <div className="flex flex-wrap items-center justify-between gap-4 text-xs text-ink/60 border-t border-deep/5 pt-4">
            <p className="max-w-xl">
              Hackathon prototype. Not a certified medical system. Zero-storage architecture: no audio or transcripts are saved to disk.
            </p>
            <div className="flex items-center gap-3 font-medium">
              <NavLink to="/about" className="hover:underline hover:text-deep">About Kotha</NavLink>
              <span>·</span>
              <a href="https://github.com" target="_blank" rel="noreferrer" className="hover:underline hover:text-deep">Documentation</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
