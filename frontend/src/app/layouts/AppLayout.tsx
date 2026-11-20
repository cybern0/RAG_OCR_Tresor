// Cadre de l'application connectée : barre latérale fixe sur grand écran, tiroir mobile, et menu utilisateur flottant draggable.
import { Leaf, LogOut, Menu, MessageSquare, UserCircle, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import NotificationBell from '../../features/notifications/NotificationBell'
import { signOut, useAuth } from '../../features/auth/session'
import { cn } from '../../shared/lib/cn'
import { ADMIN_NAV, INTERMEDIATE_NAV, MAIN_NAV, allowed, isIntermediateAdmin } from '../nav'
import type { NavItem } from '../nav'

type Point = { x: number; y: number }

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function useDraggable(initial: Point, bounds: { minX: number; minY: number; maxX: number; maxY: number }) {
  const [position, setPosition] = useState<Point>(initial)
  const [dragging, setDragging] = useState(false)
  const offset = useRef<Point>({ x: 0, y: 0 })

  useEffect(() => {
    if (!dragging) return
    const onMove = (event: PointerEvent) => {
      setPosition({
        x: clamp(event.clientX - offset.current.x, bounds.minX, bounds.maxX),
        y: clamp(event.clientY - offset.current.y, bounds.minY, bounds.maxY),
      })
    }
    const onStop = () => setDragging(false)
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onStop)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onStop)
    }
  }, [bounds, dragging])

  const handlePointerDown = (event: React.PointerEvent<HTMLElement>) => {
    event.preventDefault()
    offset.current = { x: event.clientX - position.x, y: event.clientY - position.y }
    setDragging(true)
  }

  return { position, handlePointerDown }
}

function NavSection({ title, items, onNavigate }: { title?: string; items: NavItem[]; onNavigate: () => void }) {
  if (items.length === 0) return null
  return (
    <div className="space-y-1">
      {title && <p className="px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider text-white/60">{title}</p>}
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end} onClick={onNavigate}
          className={({ isActive }) => cn('flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
            isActive ? 'bg-white text-navy-900 shadow-sm' : 'text-white hover:bg-white/10')}>
          <item.icon className="h-4 w-4 shrink-0" aria-hidden /> <span className="truncate">{item.label}</span>
        </NavLink>
      ))}
    </div>
  )
}

export function Component() {
  const { user, can } = useAuth()
  const viewport = typeof window === 'undefined' ? { width: 1200, height: 800 } : { width: window.innerWidth, height: window.innerHeight }
  const [open, setOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const menu = useDraggable(
    { x: Math.max(20, viewport.width - 320), y: 18 },
    { minX: 12, minY: 12, maxX: Math.max(12, viewport.width - 220), maxY: Math.max(12, viewport.height - 220) },
  )
  const chatFab = useDraggable(
    { x: 18, y: Math.max(90, viewport.height - 120) },
    { minX: 12, minY: 56, maxX: Math.max(12, viewport.width - 120), maxY: Math.max(56, viewport.height - 120) },
  )

  const main = MAIN_NAV.filter((i) => allowed(i, can, user?.niveau))
  const intermediate = isIntermediateAdmin(user) ? INTERMEDIATE_NAV : []
  // rootOnly : la gestion des agents et de la structure ne se montre qu'au super administrateur
  const admin = ADMIN_NAV.filter((i) => allowed(i, can, user?.niveau))

  const sidebar = (
    <div className="flex h-full flex-col text-white">
      <div className="on-navy flex items-center gap-2 px-4 py-4">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white text-navy-900"><Leaf className="h-5 w-5" /></span>
        <span className="flex-1 text-lg font-bold text-white">Trésor RAG</span><span className="hidden lg:block"><NotificationBell /></span>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 pb-4" aria-label="Navigation principale">
        <NavSection items={main} onNavigate={() => setOpen(false)} />
        <NavSection title="Administration intermédiaire" items={intermediate} onNavigate={() => setOpen(false)} />
        <NavSection title="Administration" items={admin} onNavigate={() => setOpen(false)} />
      </nav>
    </div>
  )

  return (
    <div className="min-h-svh lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-navy-950/40 bg-navy-900 text-white shadow-float lg:block">{sidebar}</aside>

      <header className="sticky top-0 z-20 flex items-center justify-between on-navy border-b border-navy-950/40 bg-navy-900 px-4 py-2.5 text-white shadow-sm lg:hidden">
        <span className="flex items-center gap-2 font-bold text-white"><Leaf className="h-5 w-5" /> Trésor RAG</span>
        <span className="flex items-center gap-1"><NotificationBell /><button className="btn-icon" onClick={() => setOpen(true)} aria-label="Ouvrir le menu"><Menu className="h-5 w-5" /></button></span>
      </header>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 animate-fade-in bg-navy-950/60" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85%] on-navy animate-pop bg-navy-900 shadow-float">
            <button className="btn-icon absolute right-2 top-3" onClick={() => setOpen(false)} aria-label="Fermer le menu"><X className="h-5 w-5" /></button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="fixed right-4 top-4 z-50 hidden lg:block">
        <button
          type="button"
          className="flex items-center gap-2 rounded-full border border-line bg-white px-3 py-2 text-sm text-black shadow-card transition hover:border-navy-600"
          onClick={() => setMenuOpen((v) => !v)}
          aria-label="Menu du compte"
        >
          <UserCircle className="h-5 w-5 text-navy-700" aria-hidden />
          <span className="max-w-32 truncate">{user?.nom_utilisateur}</span>
        </button>

        {menuOpen && (
          <div
            className="absolute right-0 mt-2 w-64 rounded-2xl border border-line bg-white p-2 text-black shadow-float"
            style={{ left: menu.position.x, top: menu.position.y, position: 'fixed' }}
          >
            <div className="mb-2 flex cursor-grab items-center justify-between rounded-t-xl border-b border-line px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-600 active:cursor-grabbing" onPointerDown={menu.handlePointerDown}>
              <span>Compte</span>
              <button type="button" className="btn-icon h-7 w-7" onClick={() => setMenuOpen(false)} aria-label="Fermer le menu"><X className="h-4 w-4" /></button>
            </div>
            <div className="space-y-2 p-1">
              <NavLink to="/profil" onClick={() => setMenuOpen(false)} className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-black hover:bg-slate-100">
                <UserCircle className="h-4 w-4 text-navy-700" aria-hidden />
                <span>Mon profil</span>
              </NavLink>
              <button type="button" className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-black hover:bg-red-50" onClick={() => void signOut()}>
                <LogOut className="h-4 w-4 text-red-600" aria-hidden />
                <span>Déconnexion</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {can('chat.utiliser') && (
        <div className="fixed bottom-5 left-5 z-50">
          <NavLink
            to="/chat"
            className="flex h-14 w-14 items-center justify-center rounded-full border border-navy-800 bg-navy-700 text-white shadow-float transition hover:scale-105 hover:bg-navy-600"
            style={{ position: 'fixed', left: chatFab.position.x, top: chatFab.position.y, zIndex: 60 }}
            onPointerDown={chatFab.handlePointerDown}
            aria-label="Ouvrir le chat"
            title="Assistant"
          >
            <MessageSquare className="h-6 w-6" aria-hidden />
          </NavLink>
        </div>
      )}

      <main className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8"><Outlet /></main>
    </div>
  )
}
