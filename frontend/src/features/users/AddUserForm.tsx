// Formulaire de création d'utilisateur (ADMIN). Un UTILISATEUR doit être lié à un agent : son service en découle.
// Ses droits sur les fichiers viennent des dossiers (rôle direct, ou rôle de son service).
import { useState } from 'react'
import type { FormEvent } from 'react'
import { createUser } from '../../api/users'
import { errorMessage } from '../../api/client'
import Modal from '../../components/ui/Modal'
import ExampleButton from '../../components/ui/ExampleButton'
import { ErrorBox } from '../../components/ui/Feedback'
import { exempleIdentifiant, exempleMotDePasse } from '../../lib/exemples'
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
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const free = agents.filter((a) => a.actif && !a.nom_utilisateur && a.service_id !== null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await createUser({ nom_utilisateur: username, mot_de_passe: password, role, agent_id: agentId || null })
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
          <select id="nu-agent" className="input" required={role === 'UTILISATEUR'} value={agentId} onChange={(e) => setAgentId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">— Choisir —</option>
            {free.map((a) => <option key={a.id} value={a.id}>{a.nom} {a.prenom} — {a.service_nom}</option>)}
          </select>
          {free.length === 0 && <p className="mt-1 text-xs text-gold-300">Aucun agent disponible : créer d'abord un agent (onglet Agents).</p>}
        </div>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={busy}>{busy ? 'Création…' : 'Créer'}</button>
        </div>
      </form>
    </Modal>
  )
}
