// Rôles métier d'une division : créer, renommer, désactiver, supprimer. Le serveur contrôle le périmètre (404 / 403).
// Un seul onglet : le dictionnaire de rôles (la description « classement par rôle » est retirée — les rôles parlent d'eux-mêmes).
import { Shield } from 'lucide-react'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { errorMessage } from '../../shared/api/client'
import Badge from '../../shared/ui/Badge'
import { EmptyState, Loading } from '../../shared/ui/Feedback'
import PageHeader from '../../shared/ui/PageHeader'
import { useToast } from '../../shared/hooks/useToast'
import ErreurAcces from '../demandes/ErreurAcces'
import { useAuth } from '../auth/session'
import { creerRole, listDivisions, listRoles, modifierRole, supprimerRole } from './api'
import type { RoleDivision } from './api'

function Ligne({ r, onDone }: { r: RoleDivision; onDone: () => void }) {
  const toast = useToast()
  const [libelle, setLibelle] = useState(r.libelle)
  const run = (p: Promise<unknown>, ok: string) => p.then(() => { toast.success(ok); onDone() }).catch((e) => toast.error(errorMessage(e)))
  return (
    <tr>
      <td className="td"><input className="input" aria-label={`Libellé du rôle ${r.code}`} value={libelle} onChange={(e) => setLibelle(e.target.value)} /></td>
      <td className="td text-cream-300">{r.code}</td>
      <td className="td text-right">{r.nb_agents} agent(s) · {r.nb_fichiers} fichier(s)</td>
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
  const { user } = useAuth()
  const toast = useToast()
  const qc = useQueryClient()
  // le super administrateur choisit parmi toutes les divisions ; le chef de service parmi celles de SON
  // service (le serveur renvoie déjà la liste scopée) ; le chef de division voit la sienne, fixe.
  const peutChoisir = user?.niveau === 'ROOT' || user?.niveau === 'SERVICE'
  const divisions = useQuery({ queryKey: ['divisions'], queryFn: listDivisions, enabled: peutChoisir })
  const [choix, setChoix] = useState<number | null>(null)
  const [libelle, setLibelle] = useState('')
  const divisionId = choix ?? user?.division_id ?? divisions.data?.[0]?.id ?? null
  const roles = useQuery({ queryKey: ['roles-division', divisionId], queryFn: () => listRoles(divisionId!), enabled: divisionId !== null })
  const refresh = () => qc.invalidateQueries({ queryKey: ['roles-division', divisionId] })
  const add = useMutation({ mutationFn: () => creerRole(divisionId!, { libelle: libelle.trim() }), onSuccess: () => { setLibelle(''); return refresh() } })

  if (divisionId === null) {
    // divisions du service pas encore chargées : attendre avant de conclure à « aucune division »
    if (divisions.isLoading || divisions.isError) return divisions.isError ? <ErreurAcces error={divisions.error} /> : <Loading />
    return <EmptyState icon={<Shield className="h-8 w-8" />} title="Aucune division à gérer" />
  }
  return (
    <div className="space-y-4">
      <PageHeader title="Rôles et classement" description="Le dictionnaire de rôles de la division : la même référence sert aux agents et aux fichiers — un fichier peut recevoir plusieurs classes, un agent peut en porter plusieurs."
        actions={peutChoisir && divisions.data ? (
          <select className="input w-64" aria-label="Division" value={divisionId} onChange={(e) => setChoix(Number(e.target.value))}>
            {divisions.data.map((d) => <option key={d.id} value={d.id}>{d.nom}{d.service_nom ? ` (${d.service_nom})` : ''}</option>)}
          </select>
        ) : null} />

      <div className="flex gap-2">
        <input className="input w-72" placeholder="Nouveau rôle (ex. Paie)" aria-label="Libellé du nouveau rôle" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
        <button className="btn" disabled={libelle.trim().length < 2 || add.isPending}
          onClick={() => add.mutateAsync().then(() => toast.success('Rôle créé.')).catch((e) => toast.error(errorMessage(e)))}>Créer</button>
      </div>
      {roles.isLoading ? <Loading /> : roles.error ? <ErreurAcces error={roles.error} /> : (
        <div className="card overflow-x-auto"><table className="w-full text-left text-sm">
          <thead><tr><th className="th">Libellé</th><th className="th">Code</th><th className="th text-right">Utilisation</th><th className="th">État</th><th className="th" /></tr></thead>
          <tbody className="divide-y divide-gold-500/10">{(roles.data ?? []).map((r) => <Ligne key={`${r.id}-${r.libelle}-${r.actif}`} r={r} onDone={() => void refresh()} />)}</tbody>
        </table></div>
      )}
    </div>
  )
}
