// Gestion des agents : création, changement de service, désactivation (réservé à l'ADMIN).
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../api/client'
import { createAgent, listAgents, listServices, updateAgent } from '../../api/structure'
import ExampleButton from '../../components/ui/ExampleButton'
import { ErrorBox, Loading } from '../../components/ui/Feedback'
import { exempleEmail, exempleFonction, exempleMatricule, exempleNom, exemplePrenom } from '../../lib/exemples'
import Modal from '../../components/ui/Modal'
import { useLoad } from '../../hooks/useLoad'
import type { ServiceItem } from '../../types/structure'

function AddAgentForm({ services, onClose, onDone }: { services: ServiceItem[]; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ matricule: '', nom: '', prenom: '', fonction: '', email: '' })
  const [serviceId, setServiceId] = useState<number | ''>('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!serviceId) return
    setBusy(true)
    setError(null)
    try {
      await createAgent({ ...f, fonction: f.fonction || null, email: f.email || null, service_id: serviceId })
      onDone()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal title="Nouvel agent" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="grid gap-3 sm:grid-cols-2">
        <div className="flex justify-end sm:col-span-2">
          <ExampleButton onFill={() => {
            const nom = exempleNom()
            const prenom = exemplePrenom()
            setF({ matricule: exempleMatricule(), nom, prenom, fonction: exempleFonction(), email: exempleEmail(prenom, nom) })
            setServiceId(services.find((s) => s.actif)?.id ?? '')
          }} />
        </div>
        <div><label className="label" htmlFor="ag-mat">Matricule</label><input id="ag-mat" className="input" required value={f.matricule} onChange={set('matricule')} /></div>
        <div><label className="label" htmlFor="ag-fn">Fonction</label><input id="ag-fn" className="input" value={f.fonction} onChange={set('fonction')} /></div>
        <div><label className="label" htmlFor="ag-nom">Nom</label><input id="ag-nom" className="input" required value={f.nom} onChange={set('nom')} /></div>
        <div><label className="label" htmlFor="ag-pre">Prénom</label><input id="ag-pre" className="input" required value={f.prenom} onChange={set('prenom')} /></div>
        <div className="sm:col-span-2"><label className="label" htmlFor="ag-mail">Email</label><input id="ag-mail" type="email" className="input" value={f.email} onChange={set('email')} /></div>
        <div className="sm:col-span-2">
          <label className="label" htmlFor="ag-srv">Service</label>
          <select id="ag-srv" className="input" required value={serviceId} onChange={(e) => setServiceId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">— Choisir —</option>
            {services.filter((s) => s.actif).map((s) => <option key={s.id} value={s.id}>{s.nom} ({s.direction_nom})</option>)}
          </select>
        </div>
        <div className="sm:col-span-2"><ErrorBox message={error} /></div>
        <div className="flex justify-end gap-2 sm:col-span-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={busy}>{busy ? 'Création…' : 'Créer'}</button>
        </div>
      </form>
    </Modal>
  )
}

export default function AgentsPanel() {
  const agents = useLoad(listAgents)
  const services = useLoad(listServices)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function patch(id: number, data: { actif?: boolean; service_id?: number }) {
    setError(null)
    try {
      await updateAgent(id, data)
      await agents.reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><button className="btn" onClick={() => setAdding(true)}>+ Nouvel agent</button></div>
      <ErrorBox message={agents.error ?? error} />
      {agents.loading ? <Loading /> : (
        <div className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead><tr><th className="th">Matricule</th><th className="th">Agent</th><th className="th">Service</th><th className="th">Compte</th><th className="th">État</th></tr></thead>
            <tbody>
              {(agents.data ?? []).map((a) => (
                <tr key={a.id}>
                  <td className="td text-sm">{a.matricule}</td>
                  <td className="td"><p className="font-medium">{a.nom} {a.prenom}</p><p className="text-xs text-cream-300">{a.fonction ?? ''}</p></td>
                  <td className="td">
                    <select aria-label={`Service de ${a.nom}`} className="input w-auto" value={a.service_id ?? ''} onChange={(e) => void patch(a.id, { service_id: Number(e.target.value) })}>
                      {(services.data ?? []).filter((s) => s.actif || s.id === a.service_id).map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
                    </select>
                  </td>
                  <td className="td text-sm">{a.nom_utilisateur ?? <span className="text-cream-300">—</span>}</td>
                  <td className="td">
                    <button className={a.actif ? 'btn-ghost' : 'btn-danger'} onClick={() => void patch(a.id, { actif: !a.actif })}>{a.actif ? 'Actif' : 'Inactif'}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {adding && <AddAgentForm services={services.data ?? []} onClose={() => setAdding(false)} onDone={() => { setAdding(false); void agents.reload() }} />}
    </div>
  )
}
