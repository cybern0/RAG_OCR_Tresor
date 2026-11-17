// Liste des comptes. Création ici ; modification (rôle, agent, activation, mot de passe) sur la page de détail du compte.
// Permissions du backend : utilisateur.creer (créer), utilisateur.modifier (modifier / désactiver).
import { useQuery } from '@tanstack/react-query'
import { Plus, Settings2, UserCheck, UserX } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { errorMessage } from '../../../shared/api/client'
import { useToast } from '../../../shared/hooks/useToast'
import { exempleIdentifiant, exempleMotDePasse } from '../../../shared/lib/exemples'
import { formatDate } from '../../../shared/lib/format'
import Badge from '../../../shared/ui/Badge'
import ExampleButton from '../../../shared/ui/ExampleButton'
import Field from '../../../shared/ui/Field'
import { EmptyState, ErrorBox, Loading } from '../../../shared/ui/Feedback'
import Modal from '../../../shared/ui/Modal'
import PageHeader from '../../../shared/ui/PageHeader'
import { useAuth } from '../../auth/session'
import type { Role, UserOut } from '../../auth/types'
import { listRoles } from '../../roles/api'
import { createUser, updateUser } from '../api'
import { adminKeys, useAdminMutation, useAgents, useUsers } from '../queries'

function CreateUserModal({ onClose }: { onClose: () => void }) {
  const toast = useToast()
  const navigate = useNavigate()
  const agents = useAgents()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('UTILISATEUR')
  const [agentId, setAgentId] = useState<number | ''>('')
  const [roleIds, setRoleIds] = useState<number[]>([])
  const [error, setError] = useState<string | null>(null)
  const save = useAdminMutation(() => createUser({ nom_utilisateur: username, mot_de_passe: password, role, agent_id: agentId || null, role_ids: roleIds }), [adminKeys.users, adminKeys.agents])
  const free = (agents.data ?? []).filter((a) => a.actif && a.service_id !== null && !a.nom_utilisateur)
  const selectedAgent = free.find((a) => a.id === Number(agentId)) ?? (agents.data ?? []).find((a) => a.id === Number(agentId)) ?? null
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
    setError(null)
    try {
      const created = await save.mutateAsync(undefined)
      toast.success('Compte créé.')
      onClose()
      navigate(`/admin/utilisateurs/${created.id}`)
    } catch (err) { setError(errorMessage(err)) }
  }

  return (
    <Modal title="Nouvel utilisateur" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end"><ExampleButton onFill={() => { setUsername(exempleIdentifiant()); setPassword(exempleMotDePasse()); setRole('UTILISATEUR'); setAgentId(free[0]?.id ?? ''); setRoleIds([]) }} /></div>
        <Field label="Nom d’utilisateur" hint="Minuscules, chiffres, point, tiret (3 à 80 caractères).">{(id) => <input id={id} className="input" required autoComplete="off" value={username} onChange={(e) => setUsername(e.target.value)} />}</Field>
        <Field label="Mot de passe initial" hint="10 caractères minimum. L’utilisateur pourra le changer depuis son profil.">
          {(id) => <input id={id} type="password" className="input" required minLength={10} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <Field label="Rôle">
          {(id) => (
            <select id={id} className="input" value={role} onChange={(e) => setRole(e.target.value as Role)}>
              <option value="UTILISATEUR">Utilisateur (accès par dossiers)</option><option value="ADMIN">Administrateur (tout)</option>
            </select>
          )}
        </Field>
        <Field label={`Agent${role === 'UTILISATEUR' ? '' : ' (facultatif)'}`} hint={free.length === 0 ? 'Aucun agent disponible : créer d’abord un agent (menu Agents).' : undefined}>
          {(id) => (
            <select id={id} className="input" required={role === 'UTILISATEUR'} value={agentId} onChange={(e) => { const nextId = e.target.value ? Number(e.target.value) : ''; setAgentId(nextId); setRoleIds([]) }}>
              <option value="">— Choisir —</option>
              {free.map((a) => <option key={a.id} value={a.id}>{a.nom} {a.prenom} — {a.service_nom}</option>)}
            </select>
          )}
        </Field>
        {divisionId !== null && roleQuery.data && roleQuery.data.length > 0 && (
          <div>
            <label className="label">Rôles de division</label>
            <div className="space-y-2 rounded-lg border border-gold-500/30 bg-ink-900/40 p-3">
              {roleQuery.data.map((option) => (
                <label key={option.id} className="flex items-center gap-2 text-sm text-cream-200">
                  <input type="checkbox" checked={roleIds.includes(option.id)} onChange={() => toggleRole(option.id)} className="h-4 w-4 accent-gold-500" />
                  {option.libelle}
                </label>
              ))}
            </div>
          </div>
        )}
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={onClose}>Annuler</button><button className="btn" disabled={save.isPending}>{save.isPending ? 'Création…' : 'Créer'}</button></div>
      </form>
    </Modal>
  )
}

export function Component() {
  const { can, user: me } = useAuth()
  const toast = useToast()
  const users = useUsers()
  const [creating, setCreating] = useState(false)
  const toggle = useAdminMutation((u: UserOut) => updateUser(u.id, { actif: !u.actif }), [adminKeys.users])
  const mayCreate = can('utilisateur.creer')
  const mayEdit = can('utilisateur.modifier')

  return (
    <>
      <PageHeader title="Utilisateurs" description="Comptes de l’application. Ouvrir un compte pour modifier son rôle, son agent ou son mot de passe."
        actions={mayCreate ? <button className="btn" onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Nouvel utilisateur</button> : null} />
      <ErrorBox message={users.error ? errorMessage(users.error) : null} />
      {users.isPending ? <Loading /> : (users.data ?? []).length === 0 ? <EmptyState title="Aucun utilisateur" /> : (
        <div className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead><tr><th className="th">Compte</th><th className="th">Rôle</th><th className="th">Agent</th><th className="th">Dernière connexion</th><th className="th">État</th><th className="th" /></tr></thead>
            <tbody>
              {users.data!.map((u) => (
                <tr key={u.id} className="hover:bg-leaf-700/40">
                  <td className="td font-medium"><Link className="hover:text-gold-300" to={`/admin/utilisateurs/${u.id}`}>{u.nom_utilisateur}</Link>{u.id === me?.id && <span className="ml-2 text-xs text-cream-300">(vous)</span>}</td>
                  <td className="td"><Badge tone={u.role === 'ADMIN' ? 'gold' : 'gray'}>{u.role === 'ADMIN' ? 'Administrateur' : 'Utilisateur'}</Badge></td>
                  <td className="td text-sm">{u.agent ? <>{u.agent.nom} {u.agent.prenom}<br /><span className="text-xs text-cream-300">{u.agent.service_nom ?? 'Sans service'}</span></> : '—'}</td>
                  <td className="td text-xs">{formatDate(u.derniere_connexion)}</td>
                  <td className="td">{u.actif ? <Badge tone="green">Actif</Badge> : <Badge tone="red">Désactivé</Badge>}</td>
                  <td className="td">
                    <div className="flex justify-end gap-0.5">
                      <Link className="btn-icon" title="Ouvrir le compte" aria-label={`Ouvrir le compte ${u.nom_utilisateur}`} to={`/admin/utilisateurs/${u.id}`}><Settings2 className="h-4 w-4" /></Link>
                      {mayEdit && (
                        <button className="btn-icon" disabled={u.id === me?.id} title={u.actif ? 'Désactiver' : 'Réactiver'} aria-label={`${u.actif ? 'Désactiver' : 'Réactiver'} ${u.nom_utilisateur}`}
                          onClick={() => void toggle.mutateAsync(u).then(() => toast.success(u.actif ? 'Compte désactivé.' : 'Compte réactivé.')).catch((e) => toast.error(errorMessage(e)))}>
                          {u.actif ? <UserX className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {creating && <CreateUserModal onClose={() => setCreating(false)} />}
    </>
  )
}
