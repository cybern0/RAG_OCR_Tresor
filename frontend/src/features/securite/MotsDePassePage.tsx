// Mots de passe de dossier : chaque DIVISION protégée a son mot de passe individuel, géré par le super administrateur
// (déverrouillage temporaire, verrouillage, définition). Aucun dossier ni mot de passe au niveau des services.
import { Lock, Unlock } from 'lucide-react'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { errorMessage } from '../../shared/api/client'
import { formatDate } from '../../shared/lib/format'
import Badge from '../../shared/ui/Badge'
import { EmptyState, ErrorBox, Loading } from '../../shared/ui/Feedback'
import PageHeader from '../../shared/ui/PageHeader'
import { useToast } from '../../shared/hooks/useToast'
import { definirSecret, deverrouiller, listUnites, verrouiller } from './api'
import type { UniteSecret } from './api'

function Unite({ u }: { u: UniteSecret }) {
  const toast = useToast()
  const qc = useQueryClient()
  const [mdp, setMdp] = useState('')
  const [ancien, setAncien] = useState('')
  const [edition, setEdition] = useState(false)
  const refresh = () => qc.invalidateQueries()
  const run = (p: Promise<unknown>, ok: string) => p.then(() => { setMdp(''); setAncien(''); setEdition(false); toast.success(ok); return refresh() }).catch((e) => toast.error(errorMessage(e)))
  const unlock = useMutation({ mutationFn: () => deverrouiller(u.type, u.id, mdp) })
  const lock = useMutation({ mutationFn: () => verrouiller(u.type, u.id) })
  const secret = useMutation({ mutationFn: () => definirSecret(u.type, u.id, mdp, ancien) })
  return (
    <li className="card space-y-2 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><span className="font-medium">{u.nom}</span> <span className="text-xs text-cream-300">Division · {u.service_nom}</span></div>
        {u.deverrouille
          ? <Badge tone="green"><Unlock className="mr-1 inline h-3 w-3" />Ouverte{u.valide_jusqua ? ` jusqu’à ${formatDate(u.valide_jusqua)}` : ''}</Badge>
          : <Badge tone="amber"><Lock className="mr-1 inline h-3 w-3" />Verrouillée</Badge>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input className="input w-56" type="password" autoComplete="off" aria-label={`Mot de passe de dossier : ${u.nom}`}
          placeholder={edition ? 'Nouveau mot de passe' : 'Mot de passe de dossier'} value={mdp} onChange={(e) => setMdp(e.target.value)} />
        {edition && u.secret_defini && <input className="input w-56" type="password" autoComplete="off" placeholder="Ancien mot de passe" value={ancien} onChange={(e) => setAncien(e.target.value)} />}
        {edition
          ? <button className="btn" disabled={!mdp || secret.isPending} onClick={() => void run(secret.mutateAsync(), 'Mot de passe de dossier enregistré.')}>Enregistrer</button>
          : <button className="btn" disabled={!mdp || unlock.isPending || !u.secret_defini} onClick={() => void run(unlock.mutateAsync(), 'Déverrouillé.')}>Déverrouiller</button>}
        {u.deverrouille && !edition && <button className="btn-ghost" disabled={lock.isPending} onClick={() => void run(lock.mutateAsync(), 'Verrouillé.')}>Verrouiller</button>}
        <button className="btn-ghost" onClick={() => { setEdition((e) => !e); setMdp(''); setAncien('') }}>{edition ? 'Annuler' : u.secret_defini ? 'Changer mon mot de passe' : 'Définir mon mot de passe'}</button>
      </div>
      {!u.secret_defini && !edition && <p className="text-xs text-cream-300">Aucun mot de passe de dossier défini : définissez-le pour pouvoir ouvrir cette unité.</p>}
    </li>
  )
}

export function Component() {
  const q = useQuery({ queryKey: ['securite', 'unites'], queryFn: listUnites })
  if (q.isLoading) return <Loading />
  if (q.error) return <ErrorBox message={errorMessage(q.error)} />
  const items = q.data ?? []
  return (
    <div className="space-y-4">
      <PageHeader title="Mots de passe de dossier" description="Chaque division protégée a son propre mot de passe, individuel. Le déverrouillage est temporaire ; il se referme tout seul à l’échéance." />
      {items.length === 0 ? <EmptyState icon={<Lock className="h-8 w-8" />} title="Aucune unité protégée pour votre compte" />
        : <ul className="space-y-3">{items.map((u) => <Unite key={`${u.type}-${u.id}`} u={u} />)}</ul>}
    </div>
  )
}
