import { Mic } from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { Disclaimer } from '../components/ui'

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-bold text-deep">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand text-white">
        <Mic className="h-5 w-5" aria-hidden />
      </span>
      <span className="text-xl">
        Kotha <span className="text-brand">কথা</span>
      </span>
    </Link>
  )
}

export default function AppLayout() {
  const link = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-deep/10 text-deep' : 'text-ink/70 hover:text-deep'}`
  return (
    <div className="flex min-h-screen flex-col">
      <header className="no-print sticky top-0 z-20 border-b border-deep/10 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <Logo />
          <nav className="flex items-center gap-1" aria-label="Main">
            <NavLink to="/about" className={link}>About</NavLink>
            <Link to="/intake" className="rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-deep">
              Start
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-deep/10 bg-white">
        <div className="mx-auto max-w-6xl space-y-2 px-4 py-5">
          <Disclaimer />
          <p className="text-xs text-ink/60">
            Hackathon prototype. Not a certified medical system. No audio or transcripts are stored.
          </p>
        </div>
      </footer>
    </div>
  )
}
