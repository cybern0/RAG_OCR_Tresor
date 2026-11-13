// Liste des utilisateurs : création, modification du rôle / de l'agent, activation, réinitialisation du mot de passe.
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../api/client'
import { listAgents } from '../../api/structure'
import { listUsers, updateUser } from '../../api/users'
import ExampleButton from '../../components/ui/ExampleButton'
import { ErrorBox, Loading } from '../../components/ui/Feedback'
import { exempleMotDePasse } from '../../lib/exemples'
import Modal from '../../components/ui/Modal'
import { useAuth } from '../../hooks/useAuth'
import { useLoad } from '../../hooks/useLoad'
import type { Agent } from '../../types/structure'
import type { Role, UserOut } from '../../types/user'
import AddUserForm from './AddUserForm'

function EditUserForm({ target, agents, isSelf, onClose, onDone }: { target: UserOut; agents: Agent[]; isSelf: boolean; onClose: () => void; onDone: () => void }) {
  const [role, setRole] = useState<Role>(target.role)
  const [agentId, setAgentId] = useState<number | ''>(target.agent?.id ?? '')
  const [actif, setActif] = useState(target.actif)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const choices = agents.filter((a) => a.actif && a.service_id !== null && (!a.nom_utilisateur || a.id === target.agent?.id))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await updateUser(target.id, {
        role: role !== target.role ? role : undefined,
        agent_id: agentId && agentId !== target.agent?.id ? agentId : undefined,
        retirer_agent: !agentId && target.agent !== null ? true : undefined,
        actif: actif !== target.actif ? actif : undefined,
        mot_de_passe: password || undefined,
      })
      onDone()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal title={`Modifier ${target.nom_utilisateur}`} onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end"><ExampleButton onFill={() => setPassword(exempleMotDePasse())} /></div>
        <div>
          <label className="label" htmlFor="eu-role">Rôle</label>
          <select id="eu-role" className="input" disabled={isSelf} value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="UTILISATEUR">Utilisateur</option>
            <option value="ADMIN">Administrateur</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="eu-agent">Agent</label>
          <select id="eu-agent" className="input" required={role === 'UTILISATEUR'} value={agentId} onChange={(e) => setAgentId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">— Aucun —</option>
            {choices.map((a) => <option key={a.id} value={a.id}>{a.nom} {a.prenom} — {a.service_nom}</option>)}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-gold-500" disabled={isSelf} checked={actif} onChange={(e) => setActif(e.target.checked)} />
          Compte actif
        </label>
        <div>
          <label className="label" htmlFor="eu-pass">Nouveau mot de passe (facultatif)</label>
          <input id="eu-pass" type="password" className="input" minLength={10} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <p className="mt-1 text-xs text-cream-300">Les sessions ouvertes de cet utilisateur seront coupées.</p>
        </div>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={busy}>{busy ? 'Enregistrement…' : 'Enregistrer'}</button>
        </div>
      </form>
    </Modal>
  )
}

export default function UsersPanel() {
  const { user: me } = useAuth()
  const users = useLoad(listUsers)
  const agents = useLoad(listAgents)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<UserOut | null>(null)

  const done = () => {
    setAdding(false)
    setEditing(null)
    void users.reload()
    void agents.reload()
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><button className="btn" onClick={() => setAdding(true)}>+ Nouvel utilisateur</button></div>
      <ErrorBox message={users.error} />
      {users.loading ? <Loading /> : (
        <div className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead><tr><th className="th">Utilisateur</th><th className="th">Rôle</th><th className="th">Agent / service</th><th className="th">Dernière connexion</th><th className="th">État</th><th className="th" /></tr></thead>
            <tbody>
              {(users.data ?? []).map((u) => (
                <tr key={u.id}>
                  <td className="td font-medium">{u.nom_utilisateur}</td>
                  <td className="td"><span className="badge border-gold-500/60 text-gold-300">{u.role === 'ADMIN' ? 'Administrateur' : 'Utilisateur'}</span></td>
                  <td className="td text-sm">{u.agent ? `${u.agent.nom} ${u.agent.prenom} — ${u.agent.service_nom ?? 'sans service'}` : '—'}</td>
                  <td className="td text-xs text-cream-300">{u.derniere_connexion ? new Date(u.derniere_connexion).toLocaleString('fr-FR') : 'Jamais'}</td>
                  <td className="td"><span className={`badge ${u.actif ? 'border-emerald-300/70 text-emerald-100' : 'border-red-300/70 text-red-100'}`}>{u.actif ? 'Actif' : 'Désactivé'}</span></td>
                  <td className="td text-right"><button className="btn-ghost" onClick={() => setEditing(u)}>Modifier</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {adding && <AddUserForm agents={agents.data ?? []} onClose={() => setAdding(false)} onDone={done} />}
      {editing && <EditUserForm target={editing} agents={agents.data ?? []} isSelf={editing.id === me?.id} onClose={() => setEditing(null)} onDone={done} />}
    </div>
  )
}
