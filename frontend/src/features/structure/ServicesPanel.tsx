// Gestion des directions et des services (réservé à l'ADMIN). Pas de suppression : on désactive.
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../api/client'
import { createDirection, createService, listDirections, listServices, updateDirection, updateService } from '../../api/structure'
import ExampleButton from '../../components/ui/ExampleButton'
import { ErrorBox, Loading } from '../../components/ui/Feedback'
import { exempleCode, exempleNomDirection, exempleNomService } from '../../lib/exemples'
import { useLoad } from '../../hooks/useLoad'

export default function ServicesPanel() {
  const directions = useLoad(listDirections)
  const services = useLoad(listServices)
  const [error, setError] = useState<string | null>(null)
  const [dir, setDir] = useState({ code: '', nom: '' })
  const [srv, setSrv] = useState({ code: '', nom: '' })
  const [srvDirection, setSrvDirection] = useState<number | ''>('')

  async function run(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
      await Promise.all([directions.reload(), services.reload()])
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  const addDirection = (e: FormEvent) => {
    e.preventDefault()
    void run(async () => { await createDirection(dir); setDir({ code: '', nom: '' }) })
  }
  const addService = (e: FormEvent) => {
    e.preventDefault()
    if (!srvDirection) return
    void run(async () => { await createService({ ...srv, direction_id: srvDirection }); setSrv({ code: '', nom: '' }) })
  }

  if (directions.loading || services.loading) return <Loading />

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="lg:col-span-2"><ErrorBox message={error ?? directions.error ?? services.error} /></div>

      <section className="card space-y-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-semibold text-navy-700">Directions</h2>
          <ExampleButton onFill={() => setDir({ code: exempleCode('DIR'), nom: exempleNomDirection() })} />
        </div>
        <form onSubmit={addDirection} className="flex flex-wrap gap-2">
          <input aria-label="Code de la direction" className="input w-28" placeholder="Code" required value={dir.code} onChange={(e) => setDir({ ...dir, code: e.target.value })} />
          <input aria-label="Nom de la direction" className="input min-w-0 flex-1" placeholder="Nom de la direction" required value={dir.nom} onChange={(e) => setDir({ ...dir, nom: e.target.value })} />
          <button className="btn">Ajouter</button>
        </form>
        <ul className="divide-y divide-slate-200">
          {(directions.data ?? []).map((d) => (
            <li key={d.id} className="flex items-center justify-between gap-2 py-2 text-sm">
              <span><span className="mr-2 text-xs text-navy-600">{d.code}</span>{d.nom}</span>
              <button className={d.actif ? 'btn-ghost' : 'btn-danger'} onClick={() => void run(() => updateDirection(d.id, { actif: !d.actif }))}>{d.actif ? 'Active' : 'Inactive'}</button>
            </li>
          ))}
        </ul>
      </section>

      <section className="card space-y-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-semibold text-navy-700">Services</h2>
          <ExampleButton onFill={() => {
            setSrv({ code: exempleCode('SRV'), nom: exempleNomService() })
            setSrvDirection((directions.data ?? []).find((d) => d.actif)?.id ?? '')
          }} />
        </div>
        <form onSubmit={addService} className="flex flex-wrap gap-2">
          <input aria-label="Code du service" className="input w-28" placeholder="Code" required value={srv.code} onChange={(e) => setSrv({ ...srv, code: e.target.value })} />
          <input aria-label="Nom du service" className="input min-w-0 flex-1" placeholder="Nom du service" required value={srv.nom} onChange={(e) => setSrv({ ...srv, nom: e.target.value })} />
          <select aria-label="Direction du service" className="input w-full" required value={srvDirection} onChange={(e) => setSrvDirection(e.target.value ? Number(e.target.value) : '')}>
            <option value="">— Direction —</option>
            {(directions.data ?? []).filter((d) => d.actif).map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
          </select>
          <button className="btn">Ajouter</button>
        </form>
        <ul className="divide-y divide-slate-200">
          {(services.data ?? []).map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-2 py-2 text-sm">
              <span><span className="mr-2 text-xs text-navy-600">{s.code}</span>{s.nom}<span className="block text-xs text-slate-600">{s.direction_nom}</span></span>
              <button className={s.actif ? 'btn-ghost' : 'btn-danger'} onClick={() => void run(() => updateService(s.id, { actif: !s.actif }))}>{s.actif ? 'Actif' : 'Inactif'}</button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
