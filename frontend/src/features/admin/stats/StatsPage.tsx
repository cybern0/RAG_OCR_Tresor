// Tableau de bord : indicateurs clés, répartitions (statut, catégorie, type, confidentialité, service, dossier), état du système.
// Les libellés viennent du serveur (jamais de simples numéros).
import { Activity, Archive, FileText, FolderOpen, HardDrive, Layers, Trash2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { formatSize } from '../../../shared/lib/format'
import Badge from '../../../shared/ui/Badge'
import { ErrorBox, Loading } from '../../../shared/ui/Feedback'
import PageHeader from '../../../shared/ui/PageHeader'
import { useHealth, useStats } from '../queries'
import type { StatLine } from '../types'

function Kpi({ icon, label, value, hint }: { icon: ReactNode; label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="card flex items-center gap-3 p-4">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gold-500/15 text-gold-400">{icon}</span>
      <div className="min-w-0"><p className="text-2xl font-bold leading-none text-cream-50">{value}</p><p className="mt-1 truncate text-xs text-cream-300">{label}{hint ? ` · ${hint}` : ''}</p></div>
    </div>
  )
}

interface Row { label: string; value: number; color?: string | null }

function BarList({ title, rows, empty = 'Aucune donnée.' }: { title: string; rows: Row[]; empty?: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value))
  return (
    <section className="card p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gold-400">{title}</h2>
      {rows.length === 0 ? <p className="text-sm text-cream-300">{empty}</p> : (
        <ul className="space-y-2.5">
          {rows.map((r) => (
            <li key={r.label}>
              <div className="mb-1 flex justify-between gap-2 text-sm"><span className="truncate">{r.label}</span><span className="font-semibold text-gold-300">{r.value}</span></div>
              <div className="h-2 overflow-hidden rounded-full bg-leaf-950/70" role="img" aria-label={`${r.label} : ${r.value}`}>
                <div className="h-full rounded-full" style={{ width: `${(r.value / max) * 100}%`, background: r.color || 'var(--color-gold-500)' }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

const lines = (items: StatLine[], fallback: string): Row[] => items.map((i) => ({ label: i.nom ?? fallback, value: i.total, color: i.couleur }))
const entries = (o: Record<string, number>, names?: Record<string, string>): Row[] => Object.entries(o).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ label: names?.[k] ?? k, value: v }))

const STATUS_NAMES = { ready: 'Prêts', processing: 'Indexation', pending: 'En attente', error: 'En erreur' }
const STATUS_COLORS: Record<string, string> = { ready: '#6ee7b7', processing: '#e9c24f', pending: '#bccdb0', error: '#fca5a5' }

function Donut({ data }: { data: Record<string, number> }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0)
  let offset = 0
  const radius = 42
  const circ = 2 * Math.PI * radius
  return (
    <section className="card p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gold-400">Statut d’indexation</h2>
      <div className="flex items-center gap-5">
        <svg viewBox="0 0 100 100" className="h-28 w-28 shrink-0 -rotate-90" role="img" aria-label="Répartition des statuts">
          <circle cx="50" cy="50" r={radius} fill="none" stroke="var(--color-leaf-950)" strokeWidth="14" />
          {total > 0 && Object.entries(data).filter(([, v]) => v > 0).map(([k, v]) => {
            const len = (v / total) * circ
            const el = <circle key={k} cx="50" cy="50" r={radius} fill="none" stroke={STATUS_COLORS[k] ?? '#999'} strokeWidth="14" strokeDasharray={`${len} ${circ - len}`} strokeDashoffset={-offset} />
            offset += len
            return el
          })}
        </svg>
        <ul className="space-y-1 text-sm">
          {Object.entries(data).map(([k, v]) => (
            <li key={k} className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLORS[k] ?? '#999' }} />{STATUS_NAMES[k as keyof typeof STATUS_NAMES] ?? k} <span className="font-semibold text-gold-300">{v}</span></li>
          ))}
        </ul>
      </div>
    </section>
  )
}

function SystemHealth() {
  const health = useHealth()
  const items: [string, string][] = [['api', 'API'], ['postgres', 'Base de données'], ['ollama', 'Modèle (Ollama)'], ['ocr', 'Serveur OCR']]
  return (
    <section className="card p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gold-400">État du système</h2>
      {health.isPending ? <Loading className="py-2" /> : health.error ? <ErrorBox message={errorMessage(health.error)} /> : (
        <ul className="space-y-2 text-sm">
          {items.map(([key, label]) => (
            <li key={key} className="flex items-center justify-between"><span>{label}</span>{health.data?.[key] ? <Badge tone="green">Opérationnel</Badge> : <Badge tone="red">Indisponible</Badge>}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function Component() {
  const stats = useStats()
  const s = stats.data
  return (
    <>
      <PageHeader title="Tableau de bord" description="Vue d’ensemble des fichiers, de leur classement et de l’état du système." />
      <ErrorBox message={stats.error ? errorMessage(stats.error) : null} />
      {stats.isPending ? <Loading /> : s && (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi icon={<FileText className="h-5 w-5" />} label="Fichiers actifs" value={s.actifs} />
            <Kpi icon={<Layers className="h-5 w-5" />} label="Versions au total" value={s.nb_versions} />
            <Kpi icon={<HardDrive className="h-5 w-5" />} label="Stockage" value={formatSize(s.stockage_octets)} />
            <Kpi icon={<Trash2 className="h-5 w-5" />} label="Dans la corbeille" value={s.corbeille} />
            <Kpi icon={<Archive className="h-5 w-5" />} label="Sans classement" value={s.sans_classement} hint="ni catégorie ni type" />
            <Kpi icon={<FolderOpen className="h-5 w-5" />} label="Dossiers avec fichiers" value={s.par_dossier.length} />
            <Kpi icon={<Activity className="h-5 w-5" />} label="Prêts à interroger" value={s.statut.ready ?? 0} />
          </div>
          <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
            <Donut data={s.statut} />
            <BarList title="Par catégorie" rows={lines(s.par_categorie, 'Catégorie supprimée')} />
            <BarList title="Par type de document" rows={lines(s.par_type, 'Type supprimé')} />
            <BarList title="Par confidentialité" rows={entries(s.par_confidentialite, { PUBLIC: 'Public', INTERNE: 'Interne', CONFIDENTIEL: 'Confidentiel' })} />
            <BarList title="Par format" rows={entries(s.par_extension)} />
            <SystemHealth />
            <BarList title="Par direction" rows={lines(s.par_direction, 'Direction inconnue')} empty="Aucun fichier rattaché à une direction." />
            <BarList title="Par service" rows={lines(s.par_service, 'Service inconnu')} empty="Aucun fichier rattaché à un service." />
            <BarList title="Par dossier" rows={lines(s.par_dossier, 'Dossier supprimé')} />
          </div>
        </div>
      )}
    </>
  )
}
