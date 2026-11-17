import { Plus } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { exempleEmail, exempleFonction, exempleMatricule, exempleNom, exemplePrenom } from '../../../shared/lib/exemples'
import Badge from '../../../shared/ui/Badge'
import ExampleButton from '../../../shared/ui/ExampleButton'
import Field from '../../../shared/ui/Field'
import { EmptyState, ErrorBox, Loading } from '../../../shared/ui/Feedback'
import Modal from '../../../shared/ui/Modal'
import PageHeader from '../../../shared/ui/PageHeader'
import { useToast } from '../../../shared/hooks/useToast'
import { createAgent, listDivisionsAdmin, transfererChef, transfererChefService, updateAgent } from '../api'
import { useQuery } from '@tanstack/react-query'
import { adminKeys, useAdminMutation, useAgents, useServices } from '../queries'

function AgentModal({ onClose }: { onClose: () => void }) {
  const toast = useToast()
  const services = useServices()
  const [f, setF] = useState({ matricule: '', nom: '', prenom: '', fonction: '', email: '', service_id: '' as number | '', division_id: '' as number | '', titre: '' as '' | 'CHEF_DIVISION' | 'CHEF_SERVICE' })
  const [error, setError] = useState<string | null>(null)
  const active = (services.data ?? []).filter((s) => s.actif)
  const divisions = useQuery({ queryKey: ['admin', 'divisions'], queryFn: listDivisionsAdmin })
  const divs = (divisions.data ?? []).filter((d) => d.actif && d.service_id === f.service_id)
  const save = useAdminMutation(() => createAgent({ matricule: f.matricule, nom: f.nom, prenom: f.prenom, fonction: f.fonction || null, email: f.email || null, service_id: Number(f.service_id), division_id: f.division_id === '' ? null : Number(f.division_id), titre: f.titre === '' ? null : f.titre }), [adminKeys.agents])
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: k === 'service_id' || k === 'division_id' ? (e.target.value ? Number(e.target.value) : '') : e.target.value, ...(k === 'service_id' ? { division_id: '' as const } : {}) }))
  async function submit(e: FormEvent) { e.preventDefault(); setError(null); try { await save.mutateAsync(undefined); toast.success('Agent créé.'); onClose() } catch (err) { setError(errorMessage(err)) } }
  function fill() { const nom = exempleNom(); const prenom = exemplePrenom(); setF({ matricule: exempleMatricule(), nom, prenom, fonction: exempleFonction(), email: exempleEmail(prenom, nom), service_id: active[0]?.id ?? '', division_id: '', titre: '' }) }
  return (
    <Modal title="Nouvel agent" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end"><ExampleButton onFill={fill} /></div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Matricule">{(id) => <input id={id} className="input" required value={f.matricule} onChange={set('matricule')} />}</Field>
          <Field label="Service">{(id) => <select id={id} className="input" required value={f.service_id} onChange={set('service_id')}><option value="">— Choisir —</option>{active.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select>}</Field>
          <Field label="Poste" hint="Chef de service : même rôle qu'un chef de division, sur toutes les divisions du service, sans division propre.">{(id) => <select id={id} className="input" value={f.titre} onChange={(e: { target: { value: string } }) => setF((s) => ({ ...s, titre: e.target.value as '' | 'CHEF_DIVISION' | 'CHEF_SERVICE', ...(e.target.value === 'CHEF_SERVICE' ? { division_id: '' as const } : {}) }))}><option value="">— Aucun —</option><option value="CHEF_DIVISION">Chef de division</option><option value="CHEF_SERVICE">Chef de service</option></select>}</Field>
          <Field label="Division" hint="Obligatoire, sauf pour un chef de service (aucune division propre).">{(id) => <select id={id} className="input" value={f.division_id} onChange={set('division_id')} disabled={!f.service_id || f.titre === 'CHEF_SERVICE'}><option value="">— Aucune —</option>{divs.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}</select>}</Field>
          <Field label="Nom">{(id) => <input id={id} className="input" required value={f.nom} onChange={set('nom')} />}</Field>
          <Field label="Prénom">{(id) => <input id={id} className="input" required value={f.prenom} onChange={set('prenom')} />}</Field>
          <Field label="Fonction (facultatif)">{(id) => <input id={id} className="input" value={f.fonction} onChange={set('fonction')} />}</Field>
          <Field label="Email (facultatif)">{(id) => <input id={id} type="email" className="input" value={f.email} onChange={set('email')} />}</Field>
        </div>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={onClose}>Annuler</button><button className="btn" disabled={save.isPending}>Créer</button></div>
      </form>
    </Modal>
  )
}

export function Component() {
  const toast = useToast()
  const agents = useAgents()
  const [open, setOpen] = useState(false)
  const poste = (kind: 'division' | 'service', unitId: number, agentId: number | null, ok: string) =>
    void (kind === 'division' ? transfererChef(unitId, agentId) : transfererChefService(unitId, agentId))
      .then(() => { toast.success(ok); return agents.refetch() }).catch((e) => toast.error(errorMessage(e)))
  const toggle = useAdminMutation((v: { id: number; actif: boolean }) => updateAgent(v.id, { actif: v.actif }), [adminKeys.agents])
  return (
    <>
      <PageHeader title="Agents" description="Les personnes de la structure. Un agent peut recevoir un compte utilisateur ; son service en découle."
        actions={<button className="btn" onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> Nouvel agent</button>} />
      <ErrorBox message={agents.error ? errorMessage(agents.error) : null} />
      {agents.isPending ? <Loading /> : (agents.data ?? []).length === 0 ? <EmptyState title="Aucun agent" /> : (
        <div className="card overflow-x-auto"><table className="w-full border-collapse">
          <thead><tr><th className="th">Matricule</th><th className="th">Agent</th><th className="th">Service / division</th><th className="th">Poste</th><th className="th">Compte</th><th className="th">État</th><th className="th" /></tr></thead>
          <tbody>
            {agents.data!.map((a) => (
              <tr key={a.id} className="hover:bg-leaf-700/40">
                <td className="td font-mono text-xs">{a.matricule}</td>
                <td className="td">{a.nom} {a.prenom}<br /><span className="text-xs text-cream-300">{a.fonction ?? ''}{a.email ? ` · ${a.email}` : ''}</span></td>
                <td className="td text-sm">{a.service_nom ?? '—'}{a.division_nom ? <><br /><span className="text-xs text-cream-300">{a.division_nom}</span></> : null}</td>
                <td className="td text-sm">{a.titre === 'CHEF_DIVISION' ? <Badge tone="gold">Chef de division</Badge> : a.titre === 'CHEF_SERVICE' ? <Badge tone="gold">Chef de service</Badge> : '—'}</td>
                <td className="td text-sm">{a.nom_utilisateur ?? '—'}</td>
                <td className="td"><Badge tone={a.actif ? 'green' : 'gray'}>{a.actif ? 'Actif' : 'Désactivé'}</Badge></td>
                <td className="td text-right">{a.actif && a.titre === 'CHEF_SERVICE' && <button className="btn-ghost" onClick={() => poste('service', a.service_id!, null, 'Poste de chef de service rendu vacant.')}>Retirer le poste</button>}{a.actif && a.titre === 'CHEF_DIVISION' && a.division_id !== null && <button className="btn-ghost" onClick={() => poste('division', a.division_id!, null, 'Poste rendu vacant.')}>Retirer le poste</button>}{a.actif && !a.titre && a.division_id !== null && <button className="btn-ghost" onClick={() => poste('division', a.division_id!, a.id, 'Nommé chef de division (le titulaire précédent est remplacé).')}>Nommer chef de division</button>}{a.actif && !a.titre && a.division_id === null && a.service_id !== null && <button className="btn-ghost" onClick={() => poste('service', a.service_id!, a.id, 'Nommé chef de service (le titulaire précédent est remplacé).')}>Nommer chef de service</button>}<button className="btn-ghost" onClick={() => void toggle.mutateAsync({ id: a.id, actif: !a.actif }).catch((e) => toast.error(errorMessage(e)))}>{a.actif ? 'Désactiver' : 'Réactiver'}</button></td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      {open && <AgentModal onClose={() => setOpen(false)} />}
    </>
  )
}
