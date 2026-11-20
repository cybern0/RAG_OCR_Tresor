// Demandes d'accès : celles à traiter (chef) et les miennes. Accepter / refuser avec réponse, annuler une demande en attente.
import { Inbox } from 'lucide-react'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { errorMessage } from '../../shared/api/client'
import { formatDate } from '../../shared/lib/format'
import Badge from '../../shared/ui/Badge'
import { EmptyState, ErrorBox, Loading } from '../../shared/ui/Feedback'
import PageHeader from '../../shared/ui/PageHeader'
import { useToast } from '../../shared/hooks/useToast'
import { annuler, decider, listDemandes } from './api'
import type { Demande } from './api'

const demandesKey = ['demandes'] as const
const STATUT = { en_attente: ['En attente', 'amber'], acceptee: ['Acceptée', 'green'], refusee: ['Refusée', 'red'], annulee: ['Annulée', 'gray'] } as const

function Ligne({ d }: { d: Demande }) {
  const toast = useToast()
  const qc = useQueryClient()
  const [reponse, setReponse] = useState('')
  const done = () => qc.invalidateQueries({ queryKey: demandesKey })
  const dec = useMutation({ mutationFn: (accepter: boolean) => decider(d.id, { accepter, reponse: reponse.trim() || undefined }), onSuccess: done })
  const ann = useMutation({ mutationFn: () => annuler(d.id), onSuccess: done })
  const [label, tone] = STATUT[d.statut]
  const run = (p: Promise<unknown>, ok: string) => p.then(() => toast.success(ok)).catch((e) => toast.error(errorMessage(e)))
  return (
    <tr className="hover:bg-slate-50">
      <td className="td"><span className="font-medium">{d.demandeur_nom}</span><br /><span className="text-xs text-slate-600">{formatDate(d.date_creation)}</span></td>
      <td className="td">{d.type_demande === 'role' ? 'Rôle' : 'Fichier'} · <span className="text-navy-600">{d.cible_libelle}</span><br /><span className="text-xs text-slate-600">{d.division_nom}{d.duree_heures ? ` · ${d.duree_heures} h` : ''}</span></td>
      <td className="td max-w-xs text-sm text-slate-600">{d.motif}{d.reponse && <><br /><em>Réponse : {d.reponse}</em></>}</td>
      <td className="td"><Badge tone={tone}>{label}</Badge></td>
      <td className="td">
        <div className="flex flex-wrap justify-end gap-1">
          {d.peut_decider && <>
            <input className="input w-40" placeholder="Réponse (facultatif)" value={reponse} onChange={(e) => setReponse(e.target.value)} />
            <button className="btn" disabled={dec.isPending} onClick={() => void run(dec.mutateAsync(true), 'Demande acceptée.')}>Accepter</button>
            <button className="btn-danger" disabled={dec.isPending} onClick={() => void run(dec.mutateAsync(false), 'Demande refusée.')}>Refuser</button>
          </>}
          {d.peut_annuler && <button className="btn-ghost" disabled={ann.isPending} onClick={() => void run(ann.mutateAsync(), 'Demande annulée.')}>Annuler</button>}
        </div>
      </td>
    </tr>
  )
}

function Tableau({ items }: { items: Demande[] }) {
  return (
    <div className="card overflow-x-auto"><table className="w-full text-left text-sm">
      <thead><tr><th className="th">Demandeur</th><th className="th">Objet</th><th className="th">Motif</th><th className="th">Statut</th><th className="th" /></tr></thead>
      <tbody className="divide-y divide-slate-200">{items.map((d) => <Ligne key={d.id} d={d} />)}</tbody>
    </table></div>
  )
}

export function Component() {
  const q = useQuery({ queryKey: demandesKey, queryFn: listDemandes })
  if (q.isLoading) return <Loading />
  if (q.error) return <ErrorBox message={errorMessage(q.error)} />
  const items = q.data ?? []
  const aTraiter = items.filter((d) => d.peut_decider)
  const autres = items.filter((d) => !d.peut_decider)
  return (
    <div className="space-y-6">
      <PageHeader title="Demandes d’accès" description="Rôles de division et accès ponctuels à un fichier." />
      {items.length === 0 && <EmptyState icon={<Inbox className="h-8 w-8" />} title="Aucune demande" />}
      {aTraiter.length > 0 && <section className="space-y-2"><h2 className="font-semibold text-navy-600">À traiter ({aTraiter.length})</h2><Tableau items={aTraiter} /></section>}
      {autres.length > 0 && <section className="space-y-2"><h2 className="font-semibold text-navy-600">Historique</h2><Tableau items={autres} /></section>}
    </div>
  )
}
