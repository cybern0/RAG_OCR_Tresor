// Confirmation de suppression d'un fichier entier (toutes ses versions, leurs passages indexés et les fichiers).
import { useState } from 'react'
import { deleteDocument } from '../../api/documents'
import { errorMessage } from '../../api/client'
import Modal from '../../components/ui/Modal'
import { ErrorBox } from '../../components/ui/Feedback'
import type { DocumentMeta } from '../../types/document'

interface Props {
  doc: DocumentMeta
  onClose: () => void
  onDone: () => void
}

export default function DeleteDocumentDialog({ doc, onClose, onDone }: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      await deleteDocument(doc.id)
      onDone()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal title="Supprimer le fichier" onClose={onClose}>
      <p className="text-sm">
        Mettre <span className="font-semibold text-navy-600">« {doc.titre} »</span> dans la corbeille ?
        Il restera accessible depuis l’administration locale pour restauration, mais il ne sera plus visible dans le dossier actif ni par l'assistant.
      </p>
      <div className="mt-4"><ErrorBox message={error} /></div>
      <div className="mt-5 flex justify-end gap-2">
        <button className="btn-ghost" onClick={onClose}>Annuler</button>
        <button className="btn-danger" disabled={busy} onClick={() => void confirm()}>{busy ? 'Déplacement…' : 'Mettre dans la corbeille'}</button>
      </div>
    </Modal>
  )
}
