// Formulaire de modification : titre, service (ADMIN), remplacement du fichier (relance l'indexation).
import { useState } from 'react'
import type { FormEvent } from 'react'
import { updateDocument } from '../../api/documents'
import { errorMessage } from '../../api/client'
import Modal from '../../components/ui/Modal'
import { ErrorBox } from '../../components/ui/Feedback'
import type { DocumentMeta } from '../../types/document'
import type { ServiceItem } from '../../types/structure'
import { ACCEPTED_FILES } from './AddDocumentForm'

interface Props {
  doc: DocumentMeta
  isAdmin: boolean
  services: ServiceItem[]
  onClose: () => void
  onDone: () => void
}

export default function UpdateDocumentForm({ doc, isAdmin, services, onClose, onDone }: Props) {
  const [titre, setTitre] = useState(doc.titre)
  const [serviceId, setServiceId] = useState(doc.service_id)
  const [file, setFile] = useState<File | null>(null)
  const [tableaux, setTableaux] = useState(doc.has_tabular)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await updateDocument(doc.id, {
        titre: titre !== doc.titre ? titre : undefined,
        serviceId: isAdmin && serviceId !== doc.service_id ? serviceId : undefined,
        fichier: file,
        contientTableaux: tableaux,
      })
      onDone()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal title="Modifier le document" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div>
          <label className="label" htmlFor="up-title">Titre</label>
          <input id="up-title" className="input" required maxLength={250} value={titre} onChange={(e) => setTitre(e.target.value)} />
        </div>
        {isAdmin && (
          <div>
            <label className="label" htmlFor="up-service">Service</label>
            <select id="up-service" className="input" value={serviceId} onChange={(e) => setServiceId(Number(e.target.value))}>
              {services.map((s) => (
                <option key={s.id} value={s.id}>{s.nom} ({s.direction_nom})</option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label className="label" htmlFor="up-file">Remplacer le fichier (facultatif)</label>
          <input id="up-file" type="file" accept={ACCEPTED_FILES} className="input file:mr-3 file:rounded-md file:border-0 file:bg-gold-500 file:px-3 file:py-1 file:font-semibold file:text-leaf-950"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          {file && (
            <>
              <p className="mt-1 text-xs text-gold-300">Le nouveau fichier sera relu et réindexé ; l'ancien contenu est retiré.</p>
              <label className="mt-2 flex items-center gap-2 text-sm">
                <input type="checkbox" className="h-4 w-4 accent-gold-500" checked={tableaux} onChange={(e) => setTableaux(e.target.checked)} />
                Ce document contient des tableaux
              </label>
            </>
          )}
        </div>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={busy}>{busy ? 'Enregistrement…' : 'Enregistrer'}</button>
        </div>
      </form>
    </Modal>
  )
}
