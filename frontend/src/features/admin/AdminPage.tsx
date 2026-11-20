// Page d'administration (ADMIN) : dossiers et accès, utilisateurs, agents, services, journal d'audit.
import { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'
import AuditPanel from '../audit/AuditPanel'
import DossiersPanel from '../dossiers/DossiersPanel'
import AgentsPanel from '../structure/AgentsPanel'
import ServicesPanel from '../structure/ServicesPanel'
import UsersPanel from '../users/UsersPanel'
import GedDashboardPanel from './GedDashboardPanel'

type Tab = 'dossiers' | 'users' | 'agents' | 'services' | 'audit' | 'ged'

export default function AdminPage() {
  const { can } = useAuth()
  const tabs: { id: Tab; label: string; allowed: boolean }[] = [
    { id: 'dossiers', label: 'Dossiers et accès', allowed: can('dossier.gerer') },
    { id: 'users', label: 'Utilisateurs', allowed: can('utilisateur.lister') },
    { id: 'agents', label: 'Agents', allowed: can('structure.gerer') },
    { id: 'services', label: 'Services', allowed: can('structure.gerer') },
    { id: 'ged', label: 'GED / Tableau de bord', allowed: can('statistiques.globales') || can('classement.gerer') },
    { id: 'audit', label: "Journal d'audit", allowed: can('audit.consulter') },
  ]
  const visible = tabs.filter((t) => t.allowed)
  const [tab, setTab] = useState<Tab>(visible[0]?.id ?? 'users')

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-bold text-navy-700">Administration</h1>
      <div className="flex flex-wrap gap-2" role="tablist">
        {visible.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={tab === t.id ? 'btn' : 'btn-ghost'}>{t.label}</button>
        ))}
      </div>
      {tab === 'dossiers' && <DossiersPanel />}
      {tab === 'users' && <UsersPanel />}
      {tab === 'agents' && <AgentsPanel />}
      {tab === 'services' && <ServicesPanel />}
      {tab === 'ged' && <GedDashboardPanel />}
      {tab === 'audit' && <AuditPanel />}
    </section>
  )
}
