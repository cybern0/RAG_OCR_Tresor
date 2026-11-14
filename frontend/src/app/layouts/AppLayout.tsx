// Cadre de l'application connectée : barre latérale (menu, compte) fixe sur grand écran, tiroir sur mobile.
import { Leaf, LogOut, Menu, UserCircle, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { signOut, useAuth } from '../../features/auth/session'
import { cn } from '../../shared/lib/cn'
import { ADMIN_NAV, MAIN_NAV, allowed } from '../nav'
import type { NavItem } from '../nav'

function NavSection({ title, items, onNavigate }: { title?: string; items: NavItem[]; onNavigate: () => void }) {
  if (items.length === 0) return null
  return (
    <div className="space-y-1">
      {title && <p className="px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider text-cream-300/70">{title}</p>}
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end} onClick={onNavigate}
          className={({ isActive }) => cn('flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
            isActive ? 'bg-gold-500 text-leaf-950' : 'text-cream-100 hover:bg-gold-500/15 hover:text-gold-300')}>
          <item.icon className="h-4 w-4 shrink-0" aria-hidden /> <span className="truncate">{item.label}</span>
        </NavLink>
      ))}
    </div>
  )
}

export function Component() {
  const { user, can } = useAuth()
  const [open, setOpen] = useState(false)

  const main = MAIN_NAV.filter((i) => allowed(i, can))
  const admin = ADMIN_NAV.filter((i) => allowed(i, can))

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-4 py-4">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gold-500 text-leaf-950"><Leaf className="h-5 w-5" /></span>
        <span className="text-lg font-bold text-gold-400">Trésor RAG</span>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 pb-4" aria-label="Navigation principale">
        <NavSection items={main} onNavigate={() => setOpen(false)} />
        <NavSection title="Administration" items={admin} onNavigate={() => setOpen(false)} />
      </nav>
      <div className="border-t border-gold-500/20 p-3">
        <NavLink to="/profil" onClick={() => setOpen(false)} aria-label="Mon profil"
          className={({ isActive }) => cn('mb-2 flex items-center gap-3 rounded-lg px-2 py-2 transition', isActive ? 'bg-gold-500/20' : 'hover:bg-gold-500/15')}>
          <UserCircle className="h-8 w-8 shrink-0 text-gold-400" aria-hidden />
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-cream-50">{user?.nom_utilisateur}</span>
            <span className="block truncate text-xs text-cream-300">{user?.role === 'ADMIN' ? 'Administrateur' : user?.service_nom ?? 'Utilisateur'} · Mon profil</span>
          </span>
        </NavLink>
        <button className="btn-ghost w-full" onClick={() => void signOut()}><LogOut className="h-4 w-4" /> Déconnexion</button>
      </div>
    </div>
  )

  return (
    <div className="min-h-svh lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-gold-500/20 bg-leaf-950 lg:block">{sidebar}</aside>

      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-gold-500/20 bg-leaf-950 px-4 py-2.5 lg:hidden">
        <span className="flex items-center gap-2 font-bold text-gold-400"><Leaf className="h-5 w-5" /> Trésor RAG</span>
        <button className="btn-icon" onClick={() => setOpen(true)} aria-label="Ouvrir le menu"><Menu className="h-5 w-5" /></button>
      </header>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 animate-fade-in bg-black/60" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85%] animate-pop bg-leaf-950 shadow-2xl">
            <button className="btn-icon absolute right-2 top-3" onClick={() => setOpen(false)} aria-label="Fermer le menu"><X className="h-5 w-5" /></button>
            {sidebar}
          </aside>
        </div>
      )}

      <main className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8"><Outlet /></main>
    </div>
  )
}
