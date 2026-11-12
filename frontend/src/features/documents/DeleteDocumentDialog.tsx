// Confirmation de suppression d'un document (supprime aussi ses passages indexés et le fichier).
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
    <Modal title="Supprimer le document" onClose={onClose}>
      <p className="text-sm">
        Supprimer <span className="font-semibold text-gold-300">« {doc.titre} »</span> ? Le fichier et son contenu indexé seront
        effacés définitivement ; le chatbot ne pourra plus s'y référer.
      </p>
      <div className="mt-4"><ErrorBox message={error} /></div>
      <div className="mt-5 flex justify-end gap-2">
        <button className="btn-ghost" onClick={onClose}>Annuler</button>
        <button className="btn-danger" disabled={busy} onClick={() => void confirm()}>{busy ? 'Suppression…' : 'Supprimer'}</button>
      </div>
    </Modal>
  )
}
