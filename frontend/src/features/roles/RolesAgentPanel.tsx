// Rôles de division d'un agent : cases à cocher parmi les rôles actifs de SA division, enregistrées d'un coup (avec motif facultatif).
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { errorMessage } from '../../shared/api/client'
import { useToast } from '../../shared/hooks/useToast'
import { ErrorBox, Loading } from '../../shared/ui/Feedback'
import { definirRolesUser, listRoles, rolesDeUser } from './api'

export default function RolesAgentPanel({ userId, divisionId, divisionNom }: { userId: number; divisionId: number; divisionNom: string }) {
  const toast = useToast()
  const qc = useQueryClient()
  const dispo = useQuery({ queryKey: ['roles-division', divisionId], queryFn: () => listRoles(divisionId) })
  const actuels = useQuery({ queryKey: ['roles-user', userId], queryFn: () => rolesDeUser(userId) })
  const [edit, setEdit] = useState<Set<number> | null>(null)
  const [motif, setMotif] = useState('')
  const base = new Set((actuels.data ?? []).map((r) => r.id))
  const sel = edit ?? base
  const save = useMutation({
    mutationFn: () => definirRolesUser(userId, [...sel], motif.trim() || undefined),
    onSuccess: () => { setMotif(''); setEdit(null); return Promise.all([qc.invalidateQueries({ queryKey: ['roles-user', userId] }), qc.invalidateQueries({ queryKey: ['roles-division'] })]) },
  })
  if (dispo.isLoading || actuels.isLoading) return <Loading />
  const err = dispo.error ?? actuels.error
  if (err) return <ErrorBox message={errorMessage(err)} />
  const changed = sel.size !== base.size || [...sel].some((i) => !base.has(i))
  const roles = (dispo.data ?? []).filter((r) => r.actif || base.has(r.id))
  return (
    <section className="card space-y-3 p-5">
      <h2 className="font-semibold text-navy-700">Rôles de division · {divisionNom}</h2>
      {roles.length === 0 ? <p className="text-sm text-slate-600">Aucun rôle défini dans cette division.</p> : (
        <ul className="space-y-1">{roles.map((r) => (
          <li key={r.id}><label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-navy-700" checked={sel.has(r.id)}
              onChange={(e) => { const n = new Set(sel); if (e.target.checked) n.add(r.id); else n.delete(r.id); setEdit(n) }} /> {r.libelle}{!r.actif && ' (inactif)'}
          </label></li>
        ))}</ul>
      )}
      <input className="input" placeholder="Motif (facultatif, conservé dans l’historique)" value={motif} onChange={(e) => setMotif(e.target.value)} />
      <div className="flex justify-end"><button className="btn" disabled={!changed || save.isPending}
        onClick={() => save.mutateAsync().then(() => toast.success('Rôles enregistrés.')).catch((e) => toast.error(errorMessage(e)))}>Enregistrer les rôles</button></div>
    </section>
  )
}
