// Historique de traçabilité (registre en ajout seul, chaîné par hash) : filtre par type de cible, pagination, vérification d'intégrité.
import { ScrollText, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { errorMessage } from '../../shared/api/client'
import { formatDate } from '../../shared/lib/format'
import { EmptyState, ErrorBox, Loading } from '../../shared/ui/Feedback'
import PageHeader from '../../shared/ui/PageHeader'
import { listHistorique, verifierHistorique } from './api'

const PAR_PAGE = 50
// Valeurs réellement écrites par le backend (cible_type) : document, utilisateur, role_division, agent.
// Le filtre « demande » a été retiré à la demande de l'utilisateur ; les entrées de type demande restent
// visibles dans « Tous les types » (le backend continue de les journaliser). Les anciennes entrées
// « user », « service », « division » ne correspondaient à rien (et « dossier »/« unite »
// appartenaient à des modules supprimés) — dictionnaire nettoyé et libellés lisibles.
const TYPES: [string, string][] = [
  ['', 'Tous les types'],
  ['document', 'Document'],
  ['utilisateur', 'Utilisateur'],
  ['role_division', 'Rôle de division'],
  ['agent', 'Agent'],
]

export function Component() {
  const [type, setType] = useState('')
  const [page, setPage] = useState(0)
  const q = useQuery({ queryKey: ['historique', type, page], queryFn: () => listHistorique({ cible_type: type || undefined, limit: PAR_PAGE, offset: page * PAR_PAGE }) })
  const verif = useMutation({ mutationFn: verifierHistorique })
  const total = q.data?.total ?? 0
  return (
    <div className="space-y-4">
      <PageHeader title="Historique" description="Registre des modifications, impossible à altérer sans que la vérification le détecte."
        actions={<div className="flex gap-2">
          <select className="input w-44" aria-label="Type de cible" value={type} onChange={(e) => { setType(e.target.value); setPage(0) }}>
            {TYPES.map(([v, libelle]) => <option key={v} value={v}>{libelle}</option>)}
          </select>
          <button className="btn" disabled={verif.isPending} onClick={() => verif.mutate()}><ShieldCheck className="h-4 w-4" /> Vérifier la chaîne</button>
        </div>} />
      {verif.data && <p className={`rounded-lg border px-3 py-2 text-sm ${verif.data.ok ? 'border-emerald-300 text-emerald-800' : 'border-red-300 text-red-800'}`}>
        {verif.data.ok ? `Chaîne intègre (${verif.data.total} entrées).` : `Altération détectée à partir du rang ${verif.data.premier_rang_invalide}.`}</p>}
      {verif.error && <ErrorBox message={errorMessage(verif.error)} />}
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox message={errorMessage(q.error)} />
        : (q.data?.items ?? []).length === 0 ? <EmptyState icon={<ScrollText className="h-8 w-8" />} title="Aucune entrée" /> : (
          <div className="card overflow-x-auto"><table className="w-full text-left text-sm">
            <thead><tr><th className="th">Date</th><th className="th">Acteur</th><th className="th">Action</th><th className="th">Cible</th><th className="th">Avant → Après</th><th className="th">Motif</th></tr></thead>
            <tbody className="divide-y divide-slate-200">{q.data!.items.map((e) => (
              <tr key={e.id}>
                <td className="td whitespace-nowrap">{formatDate(e.date_action)}</td><td className="td">{e.acteur_nom ?? '—'}</td><td className="td">{e.action}</td>
                <td className="td">{e.cible_type}{e.cible_id !== null ? ` #${e.cible_id}` : ''}</td>
                <td className="td max-w-xs break-words text-slate-600">{e.avant ?? '—'} → {e.apres ?? '—'}</td><td className="td text-slate-600">{e.motif ?? ''}</td>
              </tr>))}</tbody></table></div>)}
      <div className="flex items-center justify-between text-sm text-slate-600">
        <span>{total} entrée(s)</span>
        <div className="flex gap-2"><button className="btn-ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Précédent</button>
          <button className="btn-ghost" disabled={(page + 1) * PAR_PAGE >= total} onClick={() => setPage((p) => p + 1)}>Suivant</button></div>
      </div>
    </div>
  )
}
