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
import { createAgent, updateAgent } from '../api'
import { adminKeys, useAdminMutation, useAgents, useServices } from '../queries'

function AgentModal({ onClose }: { onClose: () => void }) {
  const toast = useToast()
  const services = useServices()
  const [f, setF] = useState({ matricule: '', nom: '', prenom: '', fonction: '', email: '', service_id: '' as number | '' })
  const [error, setError] = useState<string | null>(null)
  const active = (services.data ?? []).filter((s) => s.actif)
  const save = useAdminMutation(() => createAgent({ matricule: f.matricule, nom: f.nom, prenom: f.prenom, fonction: f.fonction || null, email: f.email || null, service_id: Number(f.service_id) }), [adminKeys.agents])
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: k === 'service_id' ? (e.target.value ? Number(e.target.value) : '') : e.target.value }))
  async function submit(e: FormEvent) { e.preventDefault(); setError(null); try { await save.mutateAsync(undefined); toast.success('Agent créé.'); onClose() } catch (err) { setError(errorMessage(err)) } }
  function fill() { const nom = exempleNom(); const prenom = exemplePrenom(); setF({ matricule: exempleMatricule(), nom, prenom, fonction: exempleFonction(), email: exempleEmail(prenom, nom), service_id: active[0]?.id ?? '' }) }
  return (
    <Modal title="Nouvel agent" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end"><ExampleButton onFill={fill} /></div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Matricule">{(id) => <input id={id} className="input" required value={f.matricule} onChange={set('matricule')} />}</Field>
          <Field label="Service">{(id) => <select id={id} className="input" required value={f.service_id} onChange={set('service_id')}><option value="">— Choisir —</option>{active.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select>}</Field>
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
  const toggle = useAdminMutation((v: { id: number; actif: boolean }) => updateAgent(v.id, { actif: v.actif }), [adminKeys.agents])
  return (
    <>
      <PageHeader title="Agents" description="Les personnes de la structure. Un agent peut recevoir un compte utilisateur ; son service en découle."
        actions={<button className="btn" onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> Nouvel agent</button>} />
      <ErrorBox message={agents.error ? errorMessage(agents.error) : null} />
      {agents.isPending ? <Loading /> : (agents.data ?? []).length === 0 ? <EmptyState title="Aucun agent" /> : (
        <div className="card overflow-x-auto"><table className="w-full border-collapse">
          <thead><tr><th className="th">Matricule</th><th className="th">Agent</th><th className="th">Service</th><th className="th">Compte</th><th className="th">État</th><th className="th" /></tr></thead>
          <tbody>
            {agents.data!.map((a) => (
              <tr key={a.id} className="hover:bg-leaf-700/40">
                <td className="td font-mono text-xs">{a.matricule}</td>
                <td className="td">{a.nom} {a.prenom}<br /><span className="text-xs text-cream-300">{a.fonction ?? ''}{a.email ? ` · ${a.email}` : ''}</span></td>
                <td className="td text-sm">{a.service_nom ?? '—'}</td>
                <td className="td text-sm">{a.nom_utilisateur ?? '—'}</td>
                <td className="td"><Badge tone={a.actif ? 'green' : 'gray'}>{a.actif ? 'Actif' : 'Désactivé'}</Badge></td>
                <td className="td text-right"><button className="btn-ghost" onClick={() => void toggle.mutateAsync({ id: a.id, actif: !a.actif }).catch((e) => toast.error(errorMessage(e)))}>{a.actif ? 'Désactiver' : 'Réactiver'}</button></td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      {open && <AgentModal onClose={() => setOpen(false)} />}
    </>
  )
}
