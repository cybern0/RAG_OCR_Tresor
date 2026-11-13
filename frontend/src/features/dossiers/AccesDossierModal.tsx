// Accès à un dossier (ADMIN) : rôle donné à des utilisateurs, ou à un service entier (tous ses agents actifs).
// Le rôle effectif d'un utilisateur est le plus élevé entre son rôle direct et celui de son service.
// Un retrait prend effet immédiatement (fichiers, aperçu, chatbot, historique).
import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../api/client'
import { getAcces, removeMembre, removeServiceAcces, setMembre, setServiceAcces } from '../../api/dossiers'
import { listServices } from '../../api/structure'
import { listUsers } from '../../api/users'
import ExampleButton from '../../components/ui/ExampleButton'
import { ErrorBox, Loading } from '../../components/ui/Feedback'
import Modal from '../../components/ui/Modal'
import { useLoad } from '../../hooks/useLoad'
import { ROLES_DOSSIER } from '../../types/dossier'
import type { Dossier, RoleDossier } from '../../types/dossier'

function RoleSelect({ id, value, onChange, label }: { id: string; value: RoleDossier; onChange: (r: RoleDossier) => void; label: string }) {
  return (
    <select id={id} aria-label={label} className="input w-auto" value={value} onChange={(e) => onChange(e.target.value as RoleDossier)}>
      {ROLES_DOSSIER.map((r) => <option key={r.id} value={r.id} title={r.aide}>{r.label}</option>)}
    </select>
  )
}

export default function AccesDossierModal({ dossier, onClose }: { dossier: Dossier; onClose: () => void }) {
  const acces = useLoad(useCallback(() => getAcces(dossier.id), [dossier.id]))
  const users = useLoad(listUsers)
  const services = useLoad(listServices)
  const [error, setError] = useState<string | null>(null)
  const [newUser, setNewUser] = useState<number | ''>('')
  const [newUserRole, setNewUserRole] = useState<RoleDossier>('LECTEUR')
  const [newService, setNewService] = useState<number | ''>('')
  const [newServiceRole, setNewServiceRole] = useState<RoleDossier>('LECTEUR')

  const membres = acces.data?.membres ?? []
  const serviceAcces = acces.data?.services ?? []
  const freeUsers = (users.data ?? []).filter((u) => u.actif && u.role === 'UTILISATEUR' && !membres.some((m) => m.user_id === u.id))
  const freeServices = (services.data ?? []).filter((s) => s.actif && !serviceAcces.some((a) => a.service_id === s.id))

  async function run(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
      await acces.reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  const addUser = (e: FormEvent) => {
    e.preventDefault()
    if (newUser) void run(async () => { await setMembre(dossier.id, newUser, newUserRole); setNewUser('') })
  }
  const addService = (e: FormEvent) => {
    e.preventDefault()
    if (newService) void run(async () => { await setServiceAcces(dossier.id, newService, newServiceRole); setNewService('') })
  }

  return (
    <Modal title={`Accès au dossier « ${dossier.nom} »`} onClose={onClose} wide>
      <div className="space-y-6">
        <ErrorBox message={error ?? acces.error ?? users.error ?? services.error} />
        {acces.loading ? <Loading /> : (
          <>
            <section className="space-y-3">
              <h3 className="font-semibold text-gold-400">Utilisateurs</h3>
              <ul className="divide-y divide-leaf-700">
                {membres.map((m) => (
                  <li key={m.user_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                    <span>{m.nom_utilisateur}{m.nom_complet ? <span className="ml-2 text-xs text-cream-300">{m.nom_complet}</span> : null}</span>
                    <span className="flex items-center gap-2">
                      <RoleSelect id={`m-${m.user_id}`} label={`Rôle de ${m.nom_utilisateur}`} value={m.role} onChange={(r) => void run(() => setMembre(dossier.id, m.user_id, r))} />
                      <button className="btn-danger" onClick={() => void run(() => removeMembre(dossier.id, m.user_id))}>Retirer</button>
                    </span>
                  </li>
                ))}
                {membres.length === 0 && <li className="py-2 text-sm text-cream-300">Aucun utilisateur n’a de rôle direct dans ce dossier.</li>}
              </ul>
              <form onSubmit={addUser} className="flex flex-wrap items-center gap-2">
                <select aria-label="Utilisateur à ajouter" className="input min-w-0 flex-1" value={newUser} onChange={(e) => setNewUser(e.target.value ? Number(e.target.value) : '')}>
                  <option value="">— Utilisateur —</option>
                  {freeUsers.map((u) => <option key={u.id} value={u.id}>{u.nom_utilisateur}{u.agent ? ` — ${u.agent.nom} ${u.agent.prenom}` : ''}</option>)}
                </select>
                <RoleSelect id="new-user-role" label="Rôle de l’utilisateur à ajouter" value={newUserRole} onChange={setNewUserRole} />
                <button className="btn" disabled={!newUser}>Ajouter</button>
                <ExampleButton onFill={() => { if (freeUsers[0]) setNewUser(freeUsers[0].id); setNewUserRole('CONTRIBUTEUR') }} />
              </form>
            </section>

            <section className="space-y-3">
              <h3 className="font-semibold text-gold-400">Services entiers</h3>
              <p className="text-xs text-cream-300">Tous les agents actifs du service reçoivent ce rôle. En cas de double rôle, le plus élevé s’applique.</p>
              <ul className="divide-y divide-leaf-700">
                {serviceAcces.map((s) => (
                  <li key={s.service_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                    <span><span className="mr-2 text-xs text-gold-300">{s.service_code}</span>{s.service_nom}</span>
                    <span className="flex items-center gap-2">
                      <RoleSelect id={`s-${s.service_id}`} label={`Rôle du service ${s.service_nom}`} value={s.role} onChange={(r) => void run(() => setServiceAcces(dossier.id, s.service_id, r))} />
                      <button className="btn-danger" onClick={() => void run(() => removeServiceAcces(dossier.id, s.service_id))}>Retirer</button>
                    </span>
                  </li>
                ))}
                {serviceAcces.length === 0 && <li className="py-2 text-sm text-cream-300">Aucun service n’a accès à ce dossier.</li>}
              </ul>
              <form onSubmit={addService} className="flex flex-wrap items-center gap-2">
                <select aria-label="Service à ajouter" className="input min-w-0 flex-1" value={newService} onChange={(e) => setNewService(e.target.value ? Number(e.target.value) : '')}>
                  <option value="">— Service —</option>
                  {freeServices.map((s) => <option key={s.id} value={s.id}>{s.nom} ({s.direction_nom})</option>)}
                </select>
                <RoleSelect id="new-service-role" label="Rôle du service à ajouter" value={newServiceRole} onChange={setNewServiceRole} />
                <button className="btn" disabled={!newService}>Ajouter</button>
                <ExampleButton onFill={() => { if (freeServices[0]) setNewService(freeServices[0].id); setNewServiceRole('LECTEUR') }} />
              </form>
            </section>
          </>
        )}
      </div>
    </Modal>
  )
}
