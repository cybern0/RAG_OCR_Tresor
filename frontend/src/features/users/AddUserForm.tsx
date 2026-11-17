// Formulaire de création d'utilisateur (ADMIN). Un UTILISATEUR doit être lié à un agent : son service en découle.
// Ses droits sur les fichiers viennent des dossiers (rôle direct, ou rôle de son service).
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { createUser } from '../../api/users'
import { errorMessage } from '../../api/client'
import Modal from '../../components/ui/Modal'
import ExampleButton from '../../components/ui/ExampleButton'
import { ErrorBox } from '../../components/ui/Feedback'
import { exempleIdentifiant, exempleMotDePasse } from '../../lib/exemples'
import { listRoles } from '../roles/api'
import type { Agent } from '../../types/structure'
import type { Role } from '../../types/user'

interface Props {
  agents: Agent[]
  onClose: () => void
  onDone: () => void
}

export default function AddUserForm({ agents, onClose, onDone }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('UTILISATEUR')
  const [agentId, setAgentId] = useState<number | ''>('')
  const [roleIds, setRoleIds] = useState<number[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const free = agents.filter((a) => a.actif && !a.nom_utilisateur && a.service_id !== null)
  const selectedAgent = free.find((a) => a.id === Number(agentId)) ?? agents.find((a) => a.id === Number(agentId)) ?? null
  const divisionId = selectedAgent?.division_id ?? null
  const roleQuery = useQuery({
    queryKey: ['roles-division', divisionId],
    queryFn: () => divisionId === null ? Promise.resolve([]) : listRoles(divisionId),
    enabled: divisionId !== null,
    staleTime: 30000,
  })

  const toggleRole = (id: number) => {
    setRoleIds((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id])
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await createUser({ nom_utilisateur: username, mot_de_passe: password, role, agent_id: agentId || null, role_ids: roleIds })
      onDone()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal title="Nouvel utilisateur" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end">
          <ExampleButton onFill={() => {
            setUsername(exempleIdentifiant())
            setPassword(exempleMotDePasse())
            setRole('UTILISATEUR')
            setAgentId(free[0]?.id ?? '')
            setRoleIds([])
          }} />
        </div>
        <div>
          <label className="label" htmlFor="nu-name">Nom d'utilisateur</label>
          <input id="nu-name" className="input" required autoComplete="off" value={username} onChange={(e) => setUsername(e.target.value)} />
          <p className="mt-1 text-xs text-cream-300">Minuscules, chiffres, point, tiret (3 à 80 caractères).</p>
        </div>
        <div>
          <label className="label" htmlFor="nu-pass">Mot de passe initial</label>
          <input id="nu-pass" type="password" className="input" required minLength={10} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <p className="mt-1 text-xs text-cream-300">10 caractères minimum.</p>
        </div>
        <div>
          <label className="label" htmlFor="nu-role">Rôle</label>
          <select id="nu-role" className="input" value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="UTILISATEUR">Utilisateur (accès par dossiers)</option>
            <option value="ADMIN">Administrateur (tout)</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="nu-agent">Agent{role === 'UTILISATEUR' ? '' : ' (facultatif)'}</label>
          <select id="nu-agent" className="input" required={role === 'UTILISATEUR'} value={agentId} onChange={(e) => {
            const nextId = e.target.value ? Number(e.target.value) : ''
            setAgentId(nextId)
            setRoleIds([])
          }}>
            <option value="">— Choisir —</option>
            {free.map((a) => <option key={a.id} value={a.id}>{a.nom} {a.prenom} — {a.service_nom}</option>)}
          </select>
          {free.length === 0 && <p className="mt-1 text-xs text-gold-300">Aucun agent disponible : créer d'abord un agent (onglet Agents).</p>}
        </div>
        {divisionId !== null && roleQuery.data && roleQuery.data.length > 0 && (
          <div>
            <label className="label">Rôles de division</label>
            <div className="space-y-2 rounded-lg border border-gold-500/30 bg-ink-900/40 p-3">
              {roleQuery.data.map((roleOption) => (
                <label key={roleOption.id} className="flex items-center gap-2 text-sm text-cream-200">
                  <input type="checkbox" checked={roleIds.includes(roleOption.id)} onChange={() => toggleRole(roleOption.id)} className="h-4 w-4 accent-gold-500" />
                  {roleOption.libelle}
                </label>
              ))}
            </div>
          </div>
        )}
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={busy}>{busy ? 'Création…' : 'Créer'}</button>
        </div>
      </form>
    </Modal>
  )
}
