// Gestion des dossiers (ADMIN) : création, renommage, archivage, suppression (si vide) et attribution des accès.
import { useState } from 'react'
import { errorMessage } from '../../api/client'
import { deleteDossier, listDossiers, updateDossier } from '../../api/dossiers'
import { ErrorBox, Loading } from '../../components/ui/Feedback'
import { useLoad } from '../../hooks/useLoad'
import type { Dossier } from '../../types/dossier'
import AccesDossierModal from './AccesDossierModal'
import DossierFormModal from './DossierFormModal'

export default function DossiersPanel() {
  const dossiers = useLoad(listDossiers)
  const [form, setForm] = useState<Dossier | 'new' | null>(null)
  const [access, setAccess] = useState<Dossier | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
      await dossiers.reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  function remove(d: Dossier) {
    if (window.confirm(`Supprimer le dossier « ${d.nom} » ? Il doit être vide.`)) void run(() => deleteDossier(d.id))
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-cream-300">Les dossiers sont plats et isolés : chacun a ses propres accès, indépendants des directions et des services.</p>
        <button className="btn" onClick={() => setForm('new')}>+ Nouveau dossier</button>
      </div>
      <ErrorBox message={error ?? dossiers.error} />
      {dossiers.loading ? <Loading /> : (
        <div className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead><tr><th className="th">Dossier</th><th className="th">Fichiers</th><th className="th">État</th><th className="th text-right">Actions</th></tr></thead>
            <tbody>
              {(dossiers.data ?? []).map((d) => (
                <tr key={d.id}>
                  <td className="td"><p className="font-medium">{d.nom}</p>{d.description && <p className="text-xs text-cream-300">{d.description}</p>}</td>
                  <td className="td text-sm">{d.nb_fichiers}</td>
                  <td className="td text-sm">{d.archive ? <span className="badge border-cream-300/60 text-cream-100">Archivé</span> : <span className="badge border-emerald-300/70 bg-emerald-400/15 text-emerald-100">Actif</span>}</td>
                  <td className="td">
                    <div className="flex flex-wrap justify-end gap-2">
                      <button className="btn" onClick={() => setAccess(d)}>Accès</button>
                      <button className="btn-ghost" onClick={() => setForm(d)}>Renommer</button>
                      <button className="btn-ghost" onClick={() => void run(() => updateDossier(d.id, { archive: !d.archive }))}>{d.archive ? 'Désarchiver' : 'Archiver'}</button>
                      <button className="btn-danger" onClick={() => remove(d)}>Supprimer</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {form && <DossierFormModal dossier={form === 'new' ? null : form} onClose={() => setForm(null)} onDone={() => { setForm(null); void dossiers.reload() }} />}
      {access && <AccesDossierModal dossier={access} onClose={() => { setAccess(null); void dossiers.reload() }} />}
    </div>
  )
}
