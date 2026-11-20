// Administration des dossiers : création, modification, archivage, suppression, et accès (membres et services avec leur rôle).
import { Archive, ArchiveRestore, Pencil, Plus, Trash2, Users } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router'
import { errorMessage } from '../../../shared/api/client'
import { exempleDescription, exempleNomDossier } from '../../../shared/lib/exemples'
import { plural } from '../../../shared/lib/format'
import Badge from '../../../shared/ui/Badge'
import ConfirmDialog from '../../../shared/ui/ConfirmDialog'
import ExampleButton from '../../../shared/ui/ExampleButton'
import Field from '../../../shared/ui/Field'
import { EmptyState, ErrorBox, Loading } from '../../../shared/ui/Feedback'
import Modal from '../../../shared/ui/Modal'
import PageHeader from '../../../shared/ui/PageHeader'
import { useToast } from '../../../shared/hooks/useToast'
import * as api from '../../dossiers/api'
import { dossierKeys, useAcces, useDossiers } from '../../dossiers/queries'
import { ROLES_DOSSIER } from '../../dossiers/types'
import type { Dossier, RoleDossier } from '../../dossiers/types'
import { useAdminMutation, useServices, useUsers } from '../queries'

function DossierFormModal({ target, onClose }: { target: Dossier | null; onClose: () => void }) {
  const toast = useToast()
  const [nom, setNom] = useState(target?.nom ?? '')
  const [description, setDescription] = useState(target?.description ?? '')
  const [error, setError] = useState<string | null>(null)
  const save = useAdminMutation(() => target ? api.updateDossier(target.id, { nom, description }) : api.createDossier({ nom, description: description || null }), [dossierKeys.all])
  async function submit(e: FormEvent) { e.preventDefault(); setError(null); try { await save.mutateAsync(undefined); toast.success(target ? 'Dossier modifié.' : 'Dossier créé.'); onClose() } catch (err) { setError(errorMessage(err)) } }
  return (
    <Modal title={target ? 'Modifier le dossier' : 'Nouveau dossier'} onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end"><ExampleButton onFill={() => { setNom(exempleNomDossier()); setDescription(exempleDescription()) }} /></div>
        <Field label="Nom">{(id) => <input id={id} className="input" required maxLength={150} value={nom} onChange={(e) => setNom(e.target.value)} />}</Field>
        <Field label="Description (facultatif)">{(id) => <textarea id={id} className="input min-h-20" value={description} onChange={(e) => setDescription(e.target.value)} />}</Field>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={onClose}>Annuler</button><button className="btn" disabled={save.isPending}>{target ? 'Enregistrer' : 'Créer'}</button></div>
      </form>
    </Modal>
  )
}

function RoleSelect({ value, onChange, label }: { value: RoleDossier; onChange: (r: RoleDossier) => void; label: string }) {
  return <select className="input w-auto" aria-label={label} value={value} onChange={(e) => onChange(e.target.value as RoleDossier)}>{ROLES_DOSSIER.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select>
}

function AccesModal({ dossier, onClose }: { dossier: Dossier; onClose: () => void }) {
  const toast = useToast()
  const acces = useAcces(dossier.id)
  const users = useUsers()
  const services = useServices()
  const keys = [dossierKeys.acces(dossier.id), dossierKeys.all]
  const setMembre = useAdminMutation((v: { id: number; role: RoleDossier }) => api.setMembre(dossier.id, v.id, v.role), keys)
  const rmMembre = useAdminMutation((id: number) => api.removeMembre(dossier.id, id), keys)
  const setService = useAdminMutation((v: { id: number; role: RoleDossier }) => api.setServiceAcces(dossier.id, v.id, v.role), keys)
  const rmService = useAdminMutation((id: number) => api.removeServiceAcces(dossier.id, id), keys)
  const [newUser, setNewUser] = useState<number | ''>('')
  const [newService, setNewService] = useState<number | ''>('')
  const [userRole, setUserRole] = useState<RoleDossier>('LECTEUR')
  const [serviceRole, setServiceRole] = useState<RoleDossier>('LECTEUR')
  const run = (p: Promise<unknown>) => p.catch((e) => toast.error(errorMessage(e)))

  const freeUsers = (users.data ?? []).filter((u) => u.actif && u.role !== 'ADMIN' && !acces.data?.membres.some((m) => m.user_id === u.id))
  const freeServices = (services.data ?? []).filter((s) => s.actif && !acces.data?.services.some((x) => x.service_id === s.id))

  return (
    <Modal title={`Accès — ${dossier.nom}`} onClose={onClose} size="lg">
      <p className="mb-4 text-sm text-slate-600">Les administrateurs voient tout. Les autres comptes n’ont accès qu’aux dossiers où ils sont membres, directement ou par leur service.</p>
      <ErrorBox message={acces.error ? errorMessage(acces.error) : null} />
      {acces.isPending ? <Loading /> : (
        <div className="space-y-6">
          <section>
            <h3 className="mb-2 text-sm font-semibold text-navy-700">Membres</h3>
            {acces.data!.membres.length === 0 ? <p className="text-sm text-slate-600">Aucun membre direct.</p> : (
              <ul className="space-y-2">
                {acces.data!.membres.map((m) => (
                  <li key={m.user_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line px-3 py-2">
                    <span className="text-sm">{m.nom_complet ?? m.nom_utilisateur}<span className="text-xs text-slate-600"> · {m.nom_utilisateur}</span></span>
                    <span className="flex items-center gap-2">
                      <RoleSelect label={`Rôle de ${m.nom_utilisateur}`} value={m.role} onChange={(r) => void run(setMembre.mutateAsync({ id: m.user_id, role: r }))} />
                      <button className="btn-icon text-red-600" aria-label={`Retirer ${m.nom_utilisateur}`} onClick={() => void run(rmMembre.mutateAsync(m.user_id))}><Trash2 className="h-4 w-4" /></button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-2 flex flex-wrap gap-2">
              <select className="input w-auto min-w-48 flex-1" aria-label="Ajouter un membre" value={newUser} onChange={(e) => setNewUser(e.target.value ? Number(e.target.value) : '')}><option value="">Ajouter un membre…</option>{freeUsers.map((u) => <option key={u.id} value={u.id}>{u.nom_utilisateur}{u.agent ? ` — ${u.agent.nom} ${u.agent.prenom}` : ''}</option>)}</select>
              <RoleSelect label="Rôle du nouveau membre" value={userRole} onChange={setUserRole} />
              <button className="btn" disabled={newUser === ''} onClick={() => void run(setMembre.mutateAsync({ id: Number(newUser), role: userRole }).then(() => setNewUser('')))}>Ajouter</button>
            </div>
          </section>
          <section>
            <h3 className="mb-2 text-sm font-semibold text-navy-700">Services</h3>
            {acces.data!.services.length === 0 ? <p className="text-sm text-slate-600">Aucun service.</p> : (
              <ul className="space-y-2">
                {acces.data!.services.map((s) => (
                  <li key={s.service_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line px-3 py-2">
                    <span className="text-sm">{s.service_nom}<span className="text-xs text-slate-600"> · {s.service_code}</span></span>
                    <span className="flex items-center gap-2">
                      <RoleSelect label={`Rôle de ${s.service_nom}`} value={s.role} onChange={(r) => void run(setService.mutateAsync({ id: s.service_id, role: r }))} />
                      <button className="btn-icon text-red-600" aria-label={`Retirer ${s.service_nom}`} onClick={() => void run(rmService.mutateAsync(s.service_id))}><Trash2 className="h-4 w-4" /></button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-2 flex flex-wrap gap-2">
              <select className="input w-auto min-w-48 flex-1" aria-label="Ajouter un service" value={newService} onChange={(e) => setNewService(e.target.value ? Number(e.target.value) : '')}><option value="">Ajouter un service…</option>{freeServices.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select>
              <RoleSelect label="Rôle du nouveau service" value={serviceRole} onChange={setServiceRole} />
              <button className="btn" disabled={newService === ''} onClick={() => void run(setService.mutateAsync({ id: Number(newService), role: serviceRole }).then(() => setNewService('')))}>Ajouter</button>
            </div>
          </section>
        </div>
      )}
    </Modal>
  )
}

type Dialog = { kind: 'form'; target: Dossier | null } | { kind: 'acces' | 'delete'; target: Dossier } | null

export function Component() {
  const toast = useToast()
  const dossiers = useDossiers()
  const [dialog, setDialog] = useState<Dialog>(null)
  const archive = useAdminMutation((d: Dossier) => api.updateDossier(d.id, { archive: !d.archive }), [dossierKeys.all])
  const remove = useAdminMutation((id: number) => api.deleteDossier(id), [dossierKeys.all])

  return (
    <>
      <PageHeader title="Dossiers et accès" description="Créer les dossiers et définir qui y accède, avec quel rôle."
        actions={<button className="btn" onClick={() => setDialog({ kind: 'form', target: null })}><Plus className="h-4 w-4" /> Nouveau dossier</button>} />
      <ErrorBox message={dossiers.error ? errorMessage(dossiers.error) : null} />
      {dossiers.isPending ? <Loading /> : (dossiers.data ?? []).length === 0 ? <EmptyState title="Aucun dossier" action={<button className="btn" onClick={() => setDialog({ kind: 'form', target: null })}>Créer le premier dossier</button>} /> : (
        <div className="card overflow-x-auto"><table className="w-full border-collapse">
          <thead><tr><th className="th">Dossier</th><th className="th">Fichiers</th><th className="th">État</th><th className="th text-right">Actions</th></tr></thead>
          <tbody>
            {dossiers.data!.map((d) => (
              <tr key={d.id} className="hover:bg-slate-50">
                <td className="td"><Link className="font-medium hover:text-navy-600" to={`/dossiers/${d.id}`}>{d.nom}</Link><br /><span className="text-xs text-slate-600">{d.description ?? ''}</span></td>
                <td className="td text-sm">{plural(d.nb_fichiers, 'fichier')}</td>
                <td className="td">{d.archive ? <Badge tone="amber">Archivé</Badge> : <Badge tone="green">Actif</Badge>}</td>
                <td className="td"><div className="flex justify-end gap-0.5">
                  <button className="btn-icon" title="Accès" aria-label={`Accès de ${d.nom}`} onClick={() => setDialog({ kind: 'acces', target: d })}><Users className="h-4 w-4" /></button>
                  <button className="btn-icon" title="Modifier" aria-label={`Modifier ${d.nom}`} onClick={() => setDialog({ kind: 'form', target: d })}><Pencil className="h-4 w-4" /></button>
                  <button className="btn-icon" title={d.archive ? 'Désarchiver' : 'Archiver'} aria-label={`${d.archive ? 'Désarchiver' : 'Archiver'} ${d.nom}`}
                    onClick={() => void archive.mutateAsync(d).then(() => toast.success(d.archive ? 'Dossier désarchivé.' : 'Dossier archivé.')).catch((e) => toast.error(errorMessage(e)))}>{d.archive ? <ArchiveRestore className="h-4 w-4" /> : <Archive className="h-4 w-4" />}</button>
                  <button className="btn-icon text-red-600" title="Supprimer" aria-label={`Supprimer ${d.nom}`} onClick={() => setDialog({ kind: 'delete', target: d })}><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      {dialog?.kind === 'form' && <DossierFormModal target={dialog.target} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'acces' && <AccesModal dossier={dialog.target} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'delete' && (
        <ConfirmDialog title="Supprimer le dossier" confirmLabel="Supprimer" onClose={() => setDialog(null)}
          onConfirm={async () => { await remove.mutateAsync(dialog.target.id); toast.success('Dossier supprimé.') }}>
          Supprimer <span className="font-semibold text-navy-600">« {dialog.target.nom} »</span> ? Un dossier qui contient encore des fichiers ne peut pas être supprimé : l’archiver à la place.
        </ConfirmDialog>
      )}
    </>
  )
}
