// Formulaire d'ajout de document (fichier, titre, service, option « contient des tableaux »).
// L'ADMIN choisit le service ; l'UTILISATEUR dépose toujours dans le sien.
import { useState } from 'react'
import type { FormEvent } from 'react'
import { addDocument } from '../../api/documents'
import { errorMessage } from '../../api/client'
import Modal from '../../components/ui/Modal'
import { ErrorBox } from '../../components/ui/Feedback'
import type { ServiceItem } from '../../types/structure'

export const ACCEPTED_FILES =
  '.pdf,.docx,.doc,.pptx,.ppt,.odt,.ods,.odp,.rtf,.xlsx,.xls,.csv,.txt,.md,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp'

interface Props {
  isAdmin: boolean
  ownServiceName: string | null
  services: ServiceItem[]
  defaultServiceId: number | null
  onClose: () => void
  onDone: () => void
}

export default function AddDocumentForm({ isAdmin, ownServiceName, services, defaultServiceId, onClose, onDone }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [titre, setTitre] = useState('')
  const [serviceId, setServiceId] = useState<number | ''>(defaultServiceId ?? '')
  const [tableaux, setTableaux] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      await addDocument({ fichier: file, titre, serviceId: isAdmin ? serviceId || null : null, contientTableaux: tableaux })
      onDone()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal title="Ajouter un document" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div>
          <label className="label" htmlFor="doc-file">Fichier</label>
          <input id="doc-file" type="file" accept={ACCEPTED_FILES} required className="input file:mr-3 file:rounded-md file:border-0 file:bg-gold-500 file:px-3 file:py-1 file:font-semibold file:text-leaf-950"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <p className="mt-1 text-xs text-cream-300">PDF, Word, PowerPoint, Excel, CSV, texte, images (scans). Maximum 50 Mo.</p>
        </div>
        <div>
          <label className="label" htmlFor="doc-title">Titre</label>
          <input id="doc-title" className="input" maxLength={250} placeholder="Par défaut : nom du fichier" value={titre} onChange={(e) => setTitre(e.target.value)} />
        </div>
        {isAdmin ? (
          <div>
            <label className="label" htmlFor="doc-service">Service</label>
            <select id="doc-service" className="input" required value={serviceId} onChange={(e) => setServiceId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">— Choisir —</option>
              {services.filter((s) => s.actif).map((s) => (
                <option key={s.id} value={s.id}>{s.nom} ({s.direction_nom})</option>
              ))}
            </select>
          </div>
        ) : (
          <p className="text-sm text-cream-300">Service : <span className="font-medium text-gold-300">{ownServiceName}</span></p>
        )}
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-gold-500" checked={tableaux} onChange={(e) => setTableaux(e.target.checked)} />
          Ce document contient des tableaux
        </label>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={busy || !file}>{busy ? 'Envoi…' : 'Ajouter'}</button>
        </div>
      </form>
    </Modal>
  )
}
