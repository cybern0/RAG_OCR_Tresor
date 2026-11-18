// Tableau de bord du super administrateur (/admin, première page du compte ROOT) :
// indicateurs clés, statut d'indexation, TRAÇAGE DES ERREURS d'indexation par service / division / rôle,
// répartitions (catégorie, type, confidentialité, format, direction, service) et état du système.
// Les libellés viennent du serveur (jamais de simples numéros). Les erreurs viennent du tableau de bord ROOT.
import { Activity, Archive, FileText, HardDrive, Layers, Trash2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { errorMessage } from '../../../shared/api/client'
import { formatDate, formatSize } from '../../../shared/lib/format'
import Badge from '../../../shared/ui/Badge'
import { ErrorBox, Loading } from '../../../shared/ui/Feedback'
import PageHeader from '../../../shared/ui/PageHeader'
import { fetchTableauDeBord } from '../../accueil/api'
import type { ErreursIndexation } from '../../accueil/api'
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

function ErreursIndexation({ erreurs }: { erreurs: ErreursIndexation }) {
  const groupes = [
    { titre: 'Par service', data: erreurs.par_service },
    { titre: 'Par division', data: erreurs.par_division },
    { titre: 'Par rôle', data: erreurs.par_role },
  ]
  return (
    <section className="card border-red-400/40 p-4" id="erreurs">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="font-semibold text-gold-300">Erreurs d’indexation</h2>
        <Badge tone={erreurs.total > 0 ? 'red' : 'green'}>{erreurs.total} en échec</Badge>
      </div>
      <p className="mb-3 text-xs text-cream-300">Traçage de chaque échec d’ingestion : où (service, division), quelles classes (rôles), et pourquoi (message du worker).</p>
      {erreurs.total === 0 ? (
        <p className="text-sm text-cream-300">Aucune erreur : toutes les versions déposées sont indexées (ou en cours).</p>
      ) : (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            {groupes.map((g) => (
              <div key={g.titre}>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-cream-300">{g.titre}</p>
                {g.data.length === 0 ? <p className="text-sm text-cream-300">—</p> : (
                  <ul className="space-y-1 text-sm">
                    {g.data.map((n) => <li key={n.nom} className="flex justify-between gap-2"><span className="truncate">{n.nom}</span><span className="font-semibold text-red-300">{n.total}</span></li>)}
                  </ul>
                )}
              </div>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead><tr><th className="th">Fichier</th><th className="th">Division / service</th><th className="th">Rôles</th><th className="th">Erreur</th><th className="th">Déposé le</th></tr></thead>
              <tbody className="divide-y divide-gold-500/10">
                {erreurs.items.map((e) => (
                  <tr key={`${e.document_id}-${e.version_numero}`} className="hover:bg-leaf-700/40">
                    <td className="td"><Link className="font-medium text-gold-300 hover:underline" to={`/fichiers/${e.document_id}`}>{e.titre}</Link><p className="text-xs text-cream-300">v{e.version_numero} · {e.nom_fichier}</p></td>
                    <td className="td text-sm">{e.division_nom}{e.service_nom ? <><br /><span className="text-xs text-cream-300">{e.service_nom}</span></> : null}</td>
                    <td className="td text-sm text-cream-200">{e.roles.length ? e.roles.join(', ') : '—'}</td>
                    <td className="td max-w-64 text-xs text-red-200">{e.message_erreur ?? 'Erreur inconnue'}</td>
                    <td className="td whitespace-nowrap text-xs text-cream-300">{formatDate(e.cree_le)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}

export function Component() {
  const stats = useStats()
  const tableau = useQuery({ queryKey: ['tableau-de-bord'], queryFn: fetchTableauDeBord, refetchInterval: 60_000 })
  const s = stats.data
  return (
    <>
      <PageHeader title="Tableau de bord" description="Vue d’ensemble de l’organisation : fichiers, indexation, erreurs d’ingestion par service, division et rôle, état du système." />
      <ErrorBox message={stats.error ? errorMessage(stats.error) : null} />
      {stats.isPending || tableau.isPending ? <Loading /> : s && (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi icon={<FileText className="h-5 w-5" />} label="Fichiers actifs" value={s.actifs} />
            <Kpi icon={<Layers className="h-5 w-5" />} label="Versions au total" value={s.nb_versions} />
            <Kpi icon={<HardDrive className="h-5 w-5" />} label="Stockage" value={formatSize(s.stockage_octets)} />
            <Kpi icon={<Trash2 className="h-5 w-5" />} label="Dans la corbeille" value={s.corbeille} />
            <Kpi icon={<Archive className="h-5 w-5" />} label="Sans classement" value={s.sans_classement} hint="ni catégorie ni type" />
            <Kpi icon={<Activity className="h-5 w-5" />} label="Prêts à interroger" value={s.statut.ready ?? 0} />
          </div>
          {tableau.data?.alertes.length ? (
            <div className="space-y-1">{tableau.data.alertes.map((a) => <p key={a} className="rounded-lg border border-amber-400/60 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">{a}</p>)}</div>
          ) : null}
          {tableau.data?.erreurs_indexation && <ErreursIndexation erreurs={tableau.data.erreurs_indexation} />}
          {tableau.data?.repartition && (
            <section className="card overflow-x-auto"><h2 className="px-4 pt-3 font-semibold text-gold-300">{tableau.data.repartition.titre} — divisions, agents et fichiers</h2>
              <table className="mt-2 w-full text-left text-sm"><thead><tr><th className="th" />{tableau.data.repartition.colonnes.map((c) => <th key={c.cle} className="th text-right">{c.libelle}</th>)}</tr></thead>
                <tbody className="divide-y divide-gold-500/10">{tableau.data.repartition.lignes.map((l) => (
                  <tr key={`${l.id}-${l.libelle}`} className={l.alerte ? 'bg-red-400/10' : undefined}>
                    <td className="td">{l.libelle}{l.sous_titre && <><br /><span className="text-xs text-cream-300">{l.sous_titre}</span></>}</td>
                    {tableau.data!.repartition!.colonnes.map((c) => <td key={c.cle} className="td text-right">{l.valeurs[c.cle] ?? 0}</td>)}
                  </tr>))}</tbody></table></section>
          )}
          <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
            <Donut data={s.statut} />
            <SystemHealth />
            <BarList title="Par catégorie" rows={lines(s.par_categorie, 'Catégorie supprimée')} />
            <BarList title="Par type de document" rows={lines(s.par_type, 'Type supprimé')} />
            <BarList title="Par confidentialité" rows={entries(s.par_confidentialite, { PUBLIC: 'Public', INTERNE: 'Interne', CONFIDENTIEL: 'Confidentiel' })} />
            <BarList title="Par format" rows={entries(s.par_extension)} />
            <BarList title="Par direction" rows={lines(s.par_direction, 'Direction inconnue')} empty="Aucun fichier rattaché à une direction." />
            <BarList title="Par service" rows={lines(s.par_service, 'Service inconnu')} empty="Aucun fichier rattaché à un service." />
          </div>
        </div>
      )}
    </>
  )
}
