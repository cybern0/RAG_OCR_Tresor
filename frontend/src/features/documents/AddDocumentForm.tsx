// Formulaire d'ajout d'un fichier dans un dossier : fichier, titre, cases tableaux / images, aperçu avant l'envoi.
import { useState } from 'react'
import type { FormEvent } from 'react'
import { addDocument } from '../../api/documents'
import { errorMessage } from '../../api/client'
import { ErrorBox } from '../../components/ui/Feedback'
import ExampleButton from '../../components/ui/ExampleButton'
import FilePicker from '../../components/ui/FilePicker'
import { PreviewLocal } from '../../components/ui/FilePreview'
import FlagsFields from '../../components/ui/FlagsFields'
import Modal from '../../components/ui/Modal'
import { exempleFichier, exempleTitreFichier } from '../../lib/exemples'
import type { Dossier } from '../../types/dossier'

interface Props {
  dossier: Dossier
  onClose: () => void
  onDone: () => void
}

export default function AddDocumentForm({ dossier, onClose, onDone }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [titre, setTitre] = useState('')
  const [tableaux, setTableaux] = useState(false)
  const [images, setImages] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function fillExample() {
    setFile(exempleFichier())
    setTitre(exempleTitreFichier())
    setTableaux(false)
    setImages(false)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      await addDocument({ fichier: file, titre, dossierId: dossier.id, contientTableaux: tableaux, contientImages: images })
      onDone()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal title="Ajouter un fichier" onClose={onClose} wide>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-cream-300">Dossier : <span className="font-medium text-gold-300">{dossier.nom}</span></p>
          <ExampleButton onFill={fillExample} />
        </div>
        <div>
          <label className="label" htmlFor="doc-file">Fichier</label>
          <FilePicker id="doc-file" file={file} onChange={setFile} required />
          <p className="mt-1 text-xs text-cream-300">PDF, Word, PowerPoint, Excel, CSV, texte, images (scans). Maximum 50 Mo.</p>
        </div>
        <div>
          <label className="label" htmlFor="doc-title">Titre</label>
          <input id="doc-title" className="input" maxLength={250} placeholder="Par défaut : nom du fichier" value={titre} onChange={(e) => setTitre(e.target.value)} />
        </div>
        <FlagsFields idPrefix="add" fileName={file?.name ?? null} tableaux={tableaux} images={images} onTableaux={setTableaux} onImages={setImages} />
        {file && (
          <details className="rounded-lg border border-gold-500/30 p-3">
            <summary className="cursor-pointer text-sm text-gold-400">Aperçu du fichier avant l’envoi</summary>
            <div className="mt-3"><PreviewLocal file={file} /></div>
          </details>
        )}
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={busy || !file}>{busy ? 'Envoi…' : 'Ajouter'}</button>
        </div>
      </form>
    </Modal>
  )
}
