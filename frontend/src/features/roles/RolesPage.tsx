// Rôles métier d'une division (dictionnaire) : créer, renommer, désactiver, supprimer un rôle. L'affectation des
// fichiers aux agents est dans une page à part (/affectation), réservée aux chefs de service et de division.
import { Shield } from 'lucide-react'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { errorMessage } from '../../shared/api/client'
import Badge from '../../shared/ui/Badge'
import { EmptyState, Loading } from '../../shared/ui/Feedback'
import PageHeader from '../../shared/ui/PageHeader'
import { useToast } from '../../shared/hooks/useToast'
import ErreurAcces from '../demandes/ErreurAcces'
import { creerRole, listRoles, modifierRole, supprimerRole } from './api'
import type { RoleDivision } from './api'
import DivisionSelect from './DivisionSelect'
import { useDivisionChoisie } from './useDivisionChoisie'

function Ligne({ r, onDone }: { r: RoleDivision; onDone: () => void }) {
  const toast = useToast()
  const [libelle, setLibelle] = useState(r.libelle)
  const run = (p: Promise<unknown>, ok: string) => p.then(() => { toast.success(ok); onDone() }).catch((e) => toast.error(errorMessage(e)))
  return (
    <tr>
      <td className="td"><input className="input" aria-label={`Libellé du rôle ${r.code}`} value={libelle} onChange={(e) => setLibelle(e.target.value)} /></td>
      <td className="td text-slate-600">{r.code}</td>
      <td className="td text-right">{r.nb_agents} agent(s)</td>
      <td className="td">{r.actif ? <Badge tone="green">Actif</Badge> : <Badge tone="gray">Inactif</Badge>}</td>
      <td className="td"><div className="flex justify-end gap-1">
        {libelle.trim() !== r.libelle && <button className="btn" onClick={() => void run(modifierRole(r.division_id, r.id, { libelle: libelle.trim() }), 'Rôle renommé.')}>Enregistrer</button>}
        <button className="btn-ghost" onClick={() => void run(modifierRole(r.division_id, r.id, { actif: !r.actif }), r.actif ? 'Rôle désactivé.' : 'Rôle réactivé.')}>{r.actif ? 'Désactiver' : 'Réactiver'}</button>
        <button className="btn-danger" onClick={() => { if (window.confirm(`Supprimer le rôle « ${r.libelle} » ?`)) void run(supprimerRole(r.division_id, r.id), 'Rôle supprimé.') }}>Supprimer</button>
      </div></td>
    </tr>
  )
}

export function Component() {
  const toast = useToast()
  const qc = useQueryClient()
  const { peutChoisir, divisions, divisionId, choisir } = useDivisionChoisie()
  const [libelle, setLibelle] = useState('')
  const roles = useQuery({ queryKey: ['roles-division', divisionId], queryFn: () => listRoles(divisionId!), enabled: divisionId !== null })
  const refresh = () => qc.invalidateQueries({ queryKey: ['roles-division', divisionId] })
  const add = useMutation({ mutationFn: () => creerRole(divisionId!, { libelle: libelle.trim() }), onSuccess: () => { setLibelle(''); return refresh() } })

  if (divisionId === null) {
    // divisions du service pas encore chargées : attendre avant de conclure à « aucune division »
    if (divisions.isLoading || divisions.isError) return divisions.isError ? <ErreurAcces error={divisions.error} /> : <Loading />
    return <EmptyState icon={<Shield className="h-8 w-8" />} title="Aucune division à gérer" />
  }
  return (
    <div className="space-y-6">
      <PageHeader title="Rôles" description="Le dictionnaire de rôles décrit les agents de la division."
        actions={peutChoisir && divisions.data ? <DivisionSelect divisions={divisions.data} value={divisionId} onChange={choisir} /> : null} />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-navy-700">Dictionnaire de rôles</h2>
        <div className="flex gap-2">
          <input className="input w-72" placeholder="Nouveau rôle (ex. Paie)" aria-label="Libellé du nouveau rôle" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          <button className="btn" disabled={libelle.trim().length < 2 || add.isPending}
            onClick={() => add.mutateAsync().then(() => toast.success('Rôle créé.')).catch((e) => toast.error(errorMessage(e)))}>Créer</button>
        </div>
        {roles.isLoading ? <Loading /> : roles.error ? <ErreurAcces error={roles.error} /> : (
          <div className="card overflow-x-auto"><table className="w-full text-left text-sm">
            <thead><tr><th className="th">Libellé</th><th className="th">Code</th><th className="th text-right">Utilisation</th><th className="th">État</th><th className="th" /></tr></thead>
            <tbody className="divide-y divide-slate-200">{(roles.data ?? []).map((r) => <Ligne key={`${r.id}-${r.libelle}-${r.actif}`} r={r} onDone={() => void refresh()} />)}</tbody>
          </table></div>
        )}
      </section>
    </div>
  )
}
