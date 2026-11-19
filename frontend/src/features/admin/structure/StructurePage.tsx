// Directions, services et divisions : CRUD complet (création, modification d'état, suppression gardée).
// Une division appartient à un service et un service à une direction ; la suppression est refusée tant que
// des éléments dépendent encore de l'objet (409 expliqué dans la fenêtre de confirmation).
import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { exempleCode, exempleNomDirection, exempleNomService } from '../../../shared/lib/exemples'
import Badge from '../../../shared/ui/Badge'
import ConfirmDialog from '../../../shared/ui/ConfirmDialog'
import ExampleButton from '../../../shared/ui/ExampleButton'
import Field from '../../../shared/ui/Field'
import { ErrorBox, Loading } from '../../../shared/ui/Feedback'
import Modal from '../../../shared/ui/Modal'
import PageHeader from '../../../shared/ui/PageHeader'
import { useToast } from '../../../shared/hooks/useToast'
import { createDirection, createDivision, createService, deleteDirection, deleteDivision, deleteService, listDivisionsAdmin, updateDirection, updateDivision, updateService } from '../api'
import { adminKeys, useAdminMutation, useDirections, useServices } from '../queries'

function DirectionModal({ onClose }: { onClose: () => void }) {
  const toast = useToast()
  const [code, setCode] = useState('')
  const [nom, setNom] = useState('')
  const [error, setError] = useState<string | null>(null)
  const save = useAdminMutation(() => createDirection({ code, nom }), [adminKeys.directions])
  async function submit(e: FormEvent) { e.preventDefault(); setError(null); try { await save.mutateAsync(undefined); toast.success('Direction créée.'); onClose() } catch (err) { setError(errorMessage(err)) } }
  return (
    <Modal title="Nouvelle direction" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end"><ExampleButton onFill={() => { setCode(exempleCode('DIR')); setNom(exempleNomDirection()) }} /></div>
        <Field label="Code" hint="Court et unique (ex. DGT).">{(id) => <input id={id} className="input" required maxLength={20} value={code} onChange={(e) => setCode(e.target.value)} />}</Field>
        <Field label="Nom">{(id) => <input id={id} className="input" required value={nom} onChange={(e) => setNom(e.target.value)} />}</Field>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={onClose}>Annuler</button><button className="btn" disabled={save.isPending}>Créer</button></div>
      </form>
    </Modal>
  )
}

function ServiceModal({ onClose }: { onClose: () => void }) {
  const toast = useToast()
  const directions = useDirections()
  const [directionId, setDirectionId] = useState<number | ''>('')
  const [code, setCode] = useState('')
  const [nom, setNom] = useState('')
  const [site, setSite] = useState('')
  const [error, setError] = useState<string | null>(null)
  const active = (directions.data ?? []).filter((d) => d.actif)
  const save = useAdminMutation(() => createService({ direction_id: Number(directionId), code, nom, site: site || null }), [adminKeys.services])
  async function submit(e: FormEvent) { e.preventDefault(); setError(null); try { await save.mutateAsync(undefined); toast.success('Service créé.'); onClose() } catch (err) { setError(errorMessage(err)) } }
  return (
    <Modal title="Nouveau service" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end"><ExampleButton onFill={() => { setDirectionId(active[0]?.id ?? ''); setCode(exempleCode('SRV')); setNom(exempleNomService()); setSite('Fianarantsoa') }} /></div>
        <Field label="Direction">
          {(id) => <select id={id} className="input" required value={directionId} onChange={(e) => setDirectionId(e.target.value ? Number(e.target.value) : '')}><option value="">— Choisir —</option>{active.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}</select>}
        </Field>
        <Field label="Code">{(id) => <input id={id} className="input" required maxLength={20} value={code} onChange={(e) => setCode(e.target.value)} />}</Field>
        <Field label="Nom">{(id) => <input id={id} className="input" required value={nom} onChange={(e) => setNom(e.target.value)} />}</Field>
        <Field label="Site (facultatif)">{(id) => <input id={id} className="input" value={site} onChange={(e) => setSite(e.target.value)} />}</Field>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={onClose}>Annuler</button><button className="btn" disabled={save.isPending}>Créer</button></div>
      </form>
    </Modal>
  )
}

function DivisionModal({ onClose }: { onClose: () => void }) {
  const toast = useToast()
  const services = useServices()
  const [serviceId, setServiceId] = useState<number | ''>('')
  const [code, setCode] = useState('')
  const [nom, setNom] = useState('')
  const [error, setError] = useState<string | null>(null)
  const activeServices = (services.data ?? []).filter((s) => s.actif)
  const save = useAdminMutation(() => createDivision({ service_id: Number(serviceId), code: code || null, nom }), [adminKeys.services])
  async function submit(e: FormEvent) { e.preventDefault(); setError(null); try { await save.mutateAsync(undefined); toast.success('Division créée.'); onClose() } catch (err) { setError(errorMessage(err)) } }
  return (
    <Modal title="Nouvelle division" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end"><ExampleButton onFill={() => { setServiceId(activeServices[0]?.id ?? ''); setCode(exempleCode('DIV')); setNom('Finances / Courrier') }} /></div>
        <Field label="Service">
          {(id) => <select id={id} className="input" required value={serviceId} onChange={(e) => setServiceId(e.target.value ? Number(e.target.value) : '')}><option value="">— Choisir —</option>{activeServices.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select>}
        </Field>
        <Field label="Code (facultatif)">{(id) => <input id={id} className="input" maxLength={20} value={code} onChange={(e) => setCode(e.target.value)} />}</Field>
        <Field label="Nom">{(id) => <input id={id} className="input" required value={nom} onChange={(e) => setNom(e.target.value)} />}</Field>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={onClose}>Annuler</button><button className="btn" disabled={save.isPending}>Créer</button></div>
      </form>
    </Modal>
  )
}

export function Component() {
  const toast = useToast()
  const directions = useDirections()
  const services = useServices()
  const divisions = useQuery({ queryKey: ['admin', 'divisions'], queryFn: listDivisionsAdmin })
  const [modal, setModal] = useState<'direction' | 'service' | 'division' | null>(null)
  const [confirm, setConfirm] = useState<{ kind: 'direction' | 'service' | 'division'; id: number; nom: string } | null>(null)
  const toggleDirection = useAdminMutation((v: { id: number; actif: boolean }) => updateDirection(v.id, { actif: v.actif }), [adminKeys.directions, adminKeys.services])
  const toggleService = useAdminMutation((v: { id: number; actif: boolean }) => updateService(v.id, { actif: v.actif }), [adminKeys.services])
  const toggleDivision = useAdminMutation((v: { id: number; actif: boolean }) => updateDivision(v.id, { actif: v.actif }), [['admin', 'divisions'] as const])
  const supprDirection = useAdminMutation((id: number) => deleteDirection(id), [adminKeys.directions, adminKeys.services])
  const supprService = useAdminMutation((id: number) => deleteService(id), [adminKeys.services, ['admin', 'divisions'] as const])
  const supprDivision = useAdminMutation((id: number) => deleteDivision(id), [['admin', 'divisions'] as const])
  const fail = (e: unknown) => toast.error(errorMessage(e))

  return (
    <>
      <PageHeader title="Directions, services et divisions" description="La hiérarchie de la structure. Les agents appartiennent à un service et à une division, les fichiers sont déposés directement dans la division, et les rôles métier vivent au niveau division." />
      <ErrorBox message={directions.error ? errorMessage(directions.error) : services.error ? errorMessage(services.error) : divisions.error ? errorMessage(divisions.error) : null} />
      <div className="grid gap-5 xl:grid-cols-3">
        <section>
          <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold text-gold-400">Directions</h2><button className="btn-ghost" onClick={() => setModal('direction')}><Plus className="h-4 w-4" /> Direction</button></div>
          {directions.isPending ? <Loading /> : (
            <div className="card overflow-x-auto"><table className="w-full border-collapse"><thead><tr><th className="th">Code</th><th className="th">Nom</th><th className="th">État</th><th className="th" /></tr></thead><tbody>
              {directions.data!.map((d) => (
                <tr key={d.id} className="hover:bg-leaf-700/40"><td className="td font-mono text-xs">{d.code}</td><td className="td">{d.nom}</td><td className="td"><Badge tone={d.actif ? 'green' : 'gray'}>{d.actif ? 'Active' : 'Désactivée'}</Badge></td>
                  <td className="td text-right"><button className="btn-ghost" onClick={() => void toggleDirection.mutateAsync({ id: d.id, actif: !d.actif }).catch(fail)}>{d.actif ? 'Désactiver' : 'Réactiver'}</button><button className="btn-ghost" onClick={() => setConfirm({ kind: 'direction', id: d.id, nom: d.nom })}>Supprimer</button></td></tr>
              ))}
            </tbody></table></div>
          )}
        </section>
        <section>
          <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold text-gold-400">Services</h2><button className="btn-ghost" onClick={() => setModal('service')}><Plus className="h-4 w-4" /> Service</button></div>
          {services.isPending ? <Loading /> : (
            <div className="card overflow-x-auto"><table className="w-full border-collapse"><thead><tr><th className="th">Service</th><th className="th">Direction</th><th className="th">État</th><th className="th" /></tr></thead><tbody>
              {services.data!.map((s) => (
                <tr key={s.id} className="hover:bg-leaf-700/40"><td className="td">{s.nom}<br /><span className="font-mono text-xs text-cream-300">{s.code}{s.site ? ` · ${s.site}` : ''}</span></td><td className="td text-sm">{s.direction_nom}</td><td className="td"><Badge tone={s.actif ? 'green' : 'gray'}>{s.actif ? 'Actif' : 'Désactivé'}</Badge></td>
                  <td className="td text-right"><button className="btn-ghost" onClick={() => void toggleService.mutateAsync({ id: s.id, actif: !s.actif }).catch(fail)}>{s.actif ? 'Désactiver' : 'Réactiver'}</button><button className="btn-ghost" onClick={() => setConfirm({ kind: 'service', id: s.id, nom: s.nom })}>Supprimer</button></td></tr>
              ))}
            </tbody></table></div>
          )}
        </section>
        <section>
          <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold text-gold-400">Divisions</h2><button className="btn-ghost" onClick={() => setModal('division')}><Plus className="h-4 w-4" /> Division</button></div>
          {divisions.isPending ? <Loading /> : (
            <div className="card overflow-x-auto"><table className="w-full border-collapse"><thead><tr><th className="th">Division</th><th className="th">Service</th><th className="th">État</th><th className="th" /></tr></thead><tbody>
              {divisions.data!.map((d) => (
                <tr key={d.id} className="hover:bg-leaf-700/40"><td className="td">{d.nom}<br /><span className="font-mono text-xs text-cream-300">{d.code ?? '—'}</span></td><td className="td text-sm">{d.service_nom ?? '—'}{d.direction_nom ? <><br /><span className="text-xs text-cream-300">{d.direction_nom}</span></> : null}</td><td className="td"><Badge tone={d.actif ? 'green' : 'gray'}>{d.actif ? 'Active' : 'Désactivée'}</Badge></td>
                  <td className="td text-right"><button className="btn-ghost" onClick={() => void toggleDivision.mutateAsync({ id: d.id, actif: !d.actif }).catch(fail)}>{d.actif ? 'Désactiver' : 'Réactiver'}</button><button className="btn-ghost" onClick={() => setConfirm({ kind: 'division', id: d.id, nom: d.nom })}>Supprimer</button></td></tr>
              ))}
            </tbody></table></div>
          )}
        </section>
      </div>
      {modal === 'direction' && <DirectionModal onClose={() => setModal(null)} />}
      {modal === 'service' && <ServiceModal onClose={() => setModal(null)} />}
      {modal === 'division' && <DivisionModal onClose={() => setModal(null)} />}
      {confirm && (
        <ConfirmDialog
          title={`Supprimer ${confirm.kind === 'direction' ? 'la direction' : confirm.kind === 'service' ? 'le service' : 'la division'} « ${confirm.nom} » ?`}
          confirmLabel="Supprimer définitivement"
          onClose={() => setConfirm(null)}
          onConfirm={async () => {
            if (confirm.kind === 'direction') { await supprDirection.mutateAsync(confirm.id); toast.success('Direction supprimée.') }
            else if (confirm.kind === 'service') { await supprService.mutateAsync(confirm.id); toast.success('Service supprimé.') }
            else { await supprDivision.mutateAsync(confirm.id); toast.success('Division supprimée.') }
          }}
        >
          {confirm.kind === 'direction' && <>La direction et son code disparaissent. Impossible tant qu'elle contient des services : déplacez-les ou supprimez-les d'abord.</>}
          {confirm.kind === 'service' && <>Le service et son code disparaissent. Impossible tant qu'il contient des divisions ou des agents.</>}
          {confirm.kind === 'division' && <>La division disparaît. Impossible si des agents, rôles, documents ou demandes d'accès l'utilisent encore.</>}
        </ConfirmDialog>
      )}
    </>
  )
}
