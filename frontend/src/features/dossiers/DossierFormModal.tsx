// Création ou renommage d'un dossier (ADMIN). Les dossiers sont plats : pas de sous-dossier.
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../api/client'
import { createDossier, updateDossier } from '../../api/dossiers'
import ExampleButton from '../../components/ui/ExampleButton'
import { ErrorBox } from '../../components/ui/Feedback'
import Modal from '../../components/ui/Modal'
import { exempleDescription, exempleNomDossier } from '../../lib/exemples'
import type { Dossier } from '../../types/dossier'

interface Props {
  dossier: Dossier | null // null : création
  onClose: () => void
  onDone: () => void
}

export default function DossierFormModal({ dossier, onClose, onDone }: Props) {
  const [nom, setNom] = useState(dossier?.nom ?? '')
  const [description, setDescription] = useState(dossier?.description ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (dossier) await updateDossier(dossier.id, { nom, description })
      else await createDossier({ nom, description: description || null })
      onDone()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal title={dossier ? 'Modifier le dossier' : 'Nouveau dossier'} onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end">
          <ExampleButton onFill={() => { setNom(exempleNomDossier()); setDescription(exempleDescription()) }} />
        </div>
        <div>
          <label className="label" htmlFor="dos-nom">Nom</label>
          <input id="dos-nom" className="input" required maxLength={150} value={nom} onChange={(e) => setNom(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="dos-desc">Description (facultatif)</label>
          <textarea id="dos-desc" className="input min-h-20" maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={busy}>{busy ? 'Enregistrement…' : dossier ? 'Enregistrer' : 'Créer'}</button>
        </div>
      </form>
    </Modal>
  )
}
