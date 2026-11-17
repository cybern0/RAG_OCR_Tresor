// Tableau de bord d'accueil : le contenu dépend du niveau du compte (ROOT, SERVICE, DIVISION, AGENT) ; tout vient du serveur.
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { errorMessage } from '../../shared/api/client'
import { formatDate } from '../../shared/lib/format'
import Badge from '../../shared/ui/Badge'
import { ErrorBox, Loading } from '../../shared/ui/Feedback'
import PageHeader from '../../shared/ui/PageHeader'
import { cn } from '../../shared/lib/cn'
import { fetchTableauDeBord } from './api'
import type { FichierBrief } from './api'

const TON = { neutre: 'border-gold-500/20', attention: 'border-amber-400/60', alerte: 'border-red-400/70' } as const

function Fichiers({ titre, items }: { titre: string; items: FichierBrief[] }) {
  if (items.length === 0) return null
  return (
    <section className="card p-4"><h2 className="mb-2 font-semibold text-gold-300">{titre}</h2>
      <ul className="divide-y divide-gold-500/10 text-sm">
        {items.map((f) => (
          <li key={f.id} className="py-1.5"><Link className="text-gold-300 hover:underline" to={`/dossiers/${f.dossier_id}/fichiers/${f.id}`}>{f.titre}</Link>
            <span className="text-cream-300"> · {f.dossier_nom}{f.depose_par ? ` · ${f.depose_par}` : ''} · {formatDate(f.depose_le)}</span></li>
        ))}
      </ul></section>
  )
}

export function Component() {
  const q = useQuery({ queryKey: ['tableau-de-bord'], queryFn: fetchTableauDeBord, refetchInterval: 60_000 })
  if (q.isLoading) return <Loading />
  if (q.error || !q.data) return <ErrorBox message={errorMessage(q.error)} />
  const t = q.data
  return (
    <div className="space-y-6">
      <PageHeader title={t.titre} description={t.sous_titre} />
      {t.alertes.length > 0 && <div className="space-y-1">{t.alertes.map((a) => <p key={a} className="rounded-lg border border-amber-400/60 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">{a}</p>)}</div>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {t.indicateurs.map((i) => {
          const body = <><p className="text-3xl font-bold text-cream-50">{i.valeur}</p><p className="text-sm text-cream-300">{i.libelle}</p></>
          const cls = cn('card block border p-4', TON[i.ton])
          return i.lien ? <Link key={i.cle} to={i.lien} className={cn(cls, 'hover:bg-leaf-700/40')}>{body}</Link> : <div key={i.cle} className={cls}>{body}</div>
        })}
      </div>
      {t.repartition && (
        <section className="card overflow-x-auto"><h2 className="px-4 pt-3 font-semibold text-gold-300">{t.repartition.titre}</h2>
          <table className="w-full text-left text-sm"><thead><tr><th className="th" />{t.repartition.colonnes.map((c) => <th key={c.cle} className="th text-right">{c.libelle}</th>)}</tr></thead>
            <tbody className="divide-y divide-gold-500/10">{t.repartition.lignes.map((l) => (
              <tr key={`${l.id}-${l.libelle}`} className={l.alerte ? 'bg-red-400/10' : undefined}>
                <td className="td">{l.libelle}{l.sous_titre && <><br /><span className="text-xs text-cream-300">{l.sous_titre}</span></>}</td>
                {t.repartition!.colonnes.map((c) => <td key={c.cle} className="td text-right">{l.valeurs[c.cle] ?? 0}</td>)}
              </tr>))}</tbody></table></section>
      )}
      {t.demandes_en_attente.length > 0 && (
        <section className="card p-4"><div className="mb-2 flex items-center justify-between"><h2 className="font-semibold text-gold-300">Demandes en attente</h2><Link className="text-sm text-gold-300 underline" to="/demandes">Tout voir</Link></div>
          <ul className="text-sm">{t.demandes_en_attente.map((d) => <li key={d.id} className="py-1">{d.demandeur_nom} · {d.cible_libelle} <Badge tone="amber">{d.type_demande === 'role' ? 'Rôle' : 'Fichier'}</Badge></li>)}</ul></section>
      )}
      <Fichiers titre="Fichiers à classer" items={t.a_classer} />
      <Fichiers titre="Mes fichiers récents" items={t.mes_fichiers} />
      {t.mes_roles.length > 0 && <section className="card p-4"><h2 className="mb-2 font-semibold text-gold-300">Mes rôles</h2><div className="flex flex-wrap gap-2">{t.mes_roles.map((r) => <Badge key={r.id} tone="gold">{r.libelle}</Badge>)}</div></section>}
      {t.acces_ponctuels.length > 0 && <section className="card p-4"><h2 className="mb-2 font-semibold text-gold-300">Accès ponctuels</h2><ul className="text-sm">{t.acces_ponctuels.map((a) => <li key={a.document_id}>{a.document_titre} <span className="text-cream-300">· jusqu’au {formatDate(a.expire_le)}</span></li>)}</ul></section>}
    </div>
  )
}
