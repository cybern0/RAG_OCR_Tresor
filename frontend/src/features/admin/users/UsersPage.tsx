// Gestion des comptes. Un UTILISATEUR est lié à un agent (son service en découle) ; ses droits viennent des dossiers.
import { KeyRound, Plus, UserCheck, UserX } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { exempleIdentifiant, exempleMotDePasse } from '../../../shared/lib/exemples'
import { formatDate } from '../../../shared/lib/format'
import Badge from '../../../shared/ui/Badge'
import ExampleButton from '../../../shared/ui/ExampleButton'
import Field from '../../../shared/ui/Field'
import { EmptyState, ErrorBox, Loading } from '../../../shared/ui/Feedback'
import Modal from '../../../shared/ui/Modal'
import PageHeader from '../../../shared/ui/PageHeader'
import { useToast } from '../../../shared/hooks/useToast'
import { useAuth } from '../../auth/session'
import type { Role, UserOut } from '../../auth/types'
import { createUser, updateUser } from '../api'
import { adminKeys, useAdminMutation, useAgents, useUsers } from '../queries'

function UserModal({ target, onClose }: { target: UserOut | null; onClose: () => void }) {
  const toast = useToast()
  const agents = useAgents()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>(target?.role ?? 'UTILISATEUR')
  const [agentId, setAgentId] = useState<number | ''>(target?.agent?.id ?? '')
  const [error, setError] = useState<string | null>(null)
  const save = useAdminMutation(
    (v: { create: boolean }) => v.create
      ? createUser({ nom_utilisateur: username, mot_de_passe: password, role, agent_id: agentId || null })
      : updateUser(target!.id, {
        role: role !== target!.role ? role : undefined,
        agent_id: agentId && agentId !== target!.agent?.id ? agentId : undefined,
        retirer_agent: !agentId && target!.agent !== null ? true : undefined,
        mot_de_passe: password || undefined,
      }),
    [adminKeys.users, adminKeys.agents],
  )
  const free = (agents.data ?? []).filter((a) => a.actif && a.service_id !== null && (!a.nom_utilisateur || a.id === target?.agent?.id))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try { await save.mutateAsync({ create: !target }); toast.success(target ? 'Compte modifié.' : 'Compte créé.'); onClose() } catch (err) { setError(errorMessage(err)) }
  }

  return (
    <Modal title={target ? `Modifier ${target.nom_utilisateur}` : 'Nouvel utilisateur'} onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        {!target && <div className="flex justify-end"><ExampleButton onFill={() => { setUsername(exempleIdentifiant()); setPassword(exempleMotDePasse()); setRole('UTILISATEUR'); setAgentId(free[0]?.id ?? '') }} /></div>}
        {!target && <Field label="Nom d’utilisateur" hint="Minuscules, chiffres, point, tiret (3 à 80 caractères).">{(id) => <input id={id} className="input" required autoComplete="off" value={username} onChange={(e) => setUsername(e.target.value)} />}</Field>}
        <Field label={target ? 'Nouveau mot de passe' : 'Mot de passe initial'} hint={target ? 'Laisser vide pour ne pas le changer. 10 caractères minimum.' : '10 caractères minimum.'}>
          {(id) => <input id={id} type="password" className="input" required={!target} minLength={10} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <Field label="Rôle">
          {(id) => (
            <select id={id} className="input" value={role} onChange={(e) => setRole(e.target.value as Role)}>
              <option value="UTILISATEUR">Utilisateur (accès par dossiers)</option><option value="ADMIN">Administrateur (tout)</option>
            </select>
          )}
        </Field>
        <Field label={`Agent${role === 'UTILISATEUR' ? '' : ' (facultatif)'}`} hint={free.length === 0 ? 'Aucun agent disponible : créer d’abord un agent.' : undefined}>
          {(id) => (
            <select id={id} className="input" required={role === 'UTILISATEUR'} value={agentId} onChange={(e) => setAgentId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">— Choisir —</option>
              {free.map((a) => <option key={a.id} value={a.id}>{a.nom} {a.prenom} — {a.service_nom}</option>)}
            </select>
          )}
        </Field>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={onClose}>Annuler</button><button className="btn" disabled={save.isPending}>{save.isPending ? 'Enregistrement…' : target ? 'Enregistrer' : 'Créer'}</button></div>
      </form>
    </Modal>
  )
}

export function Component() {
  const { can, user: me } = useAuth()
  const toast = useToast()
  const users = useUsers()
  const [modal, setModal] = useState<{ target: UserOut | null } | null>(null)
  const toggle = useAdminMutation((u: UserOut) => updateUser(u.id, { actif: !u.actif }), [adminKeys.users])
  const manage = can('utilisateur.gerer')

  return (
    <>
      <PageHeader title="Utilisateurs" description="Comptes de l’application et agents associés."
        actions={manage ? <button className="btn" onClick={() => setModal({ target: null })}><Plus className="h-4 w-4" /> Nouvel utilisateur</button> : null} />
      <ErrorBox message={users.error ? errorMessage(users.error) : null} />
      {users.isPending ? <Loading /> : (users.data ?? []).length === 0 ? <EmptyState title="Aucun utilisateur" /> : (
        <div className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead><tr><th className="th">Compte</th><th className="th">Rôle</th><th className="th">Agent</th><th className="th">Dernière connexion</th><th className="th">État</th>{manage && <th className="th" />}</tr></thead>
            <tbody>
              {users.data!.map((u) => (
                <tr key={u.id} className="hover:bg-leaf-700/40">
                  <td className="td font-medium">{u.nom_utilisateur}{u.id === me?.id && <span className="ml-2 text-xs text-cream-300">(vous)</span>}</td>
                  <td className="td"><Badge tone={u.role === 'ADMIN' ? 'gold' : 'gray'}>{u.role === 'ADMIN' ? 'Administrateur' : 'Utilisateur'}</Badge></td>
                  <td className="td text-sm">{u.agent ? <>{u.agent.nom} {u.agent.prenom}<br /><span className="text-xs text-cream-300">{u.agent.service_nom ?? 'Sans service'}</span></> : '—'}</td>
                  <td className="td text-xs">{formatDate(u.derniere_connexion)}</td>
                  <td className="td">{u.actif ? <Badge tone="green">Actif</Badge> : <Badge tone="red">Désactivé</Badge>}</td>
                  {manage && (
                    <td className="td">
                      <div className="flex justify-end gap-0.5">
                        <button className="btn-icon" title="Modifier / mot de passe" aria-label={`Modifier ${u.nom_utilisateur}`} onClick={() => setModal({ target: u })}><KeyRound className="h-4 w-4" /></button>
                        <button className="btn-icon" disabled={u.id === me?.id} title={u.actif ? 'Désactiver' : 'Réactiver'} aria-label={`${u.actif ? 'Désactiver' : 'Réactiver'} ${u.nom_utilisateur}`}
                          onClick={() => void toggle.mutateAsync(u).then(() => toast.success(u.actif ? 'Compte désactivé.' : 'Compte réactivé.')).catch((e) => toast.error(errorMessage(e)))}>
                          {u.actif ? <UserX className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />}
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {modal && <UserModal target={modal.target} onClose={() => setModal(null)} />}
    </>
  )
}
