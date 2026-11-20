// Dépôt d'une nouvelle version d'un fichier : la version précédente est conservée (indexée, téléchargeable).
import { useState } from 'react'
import type { FormEvent } from 'react'
import { addVersion } from '../../api/documents'
import { errorMessage } from '../../api/client'
import { ErrorBox } from '../../components/ui/Feedback'
import ExampleButton from '../../components/ui/ExampleButton'
import FilePicker from '../../components/ui/FilePicker'
import { PreviewLocal } from '../../components/ui/FilePreview'
import FlagsFields from '../../components/ui/FlagsFields'
import Modal from '../../components/ui/Modal'
import { exempleFichier } from '../../lib/exemples'
import type { DocumentMeta } from '../../types/document'

interface Props {
  doc: DocumentMeta
  onClose: () => void
  onDone: () => void
}

export default function NewVersionForm({ doc, onClose, onDone }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [tableaux, setTableaux] = useState(doc.has_tabular)
  const [images, setImages] = useState(doc.has_image)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      await addVersion(doc.id, { fichier: file, contientTableaux: tableaux, contientImages: images })
      onDone()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal title={`Nouvelle version de « ${doc.titre} »`} onClose={onClose} wide>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm text-slate-600">
            Version actuelle : <span className="font-medium text-navy-600">v{doc.version.numero}</span>. La nouvelle version s’ajoute :
            l’ancienne reste consultable, téléchargeable et interrogeable par l'assistant.
          </p>
          <ExampleButton className="shrink-0" onFill={() => { setFile(exempleFichier()); setTableaux(false); setImages(false) }} />
        </div>
        <div>
          <label className="label" htmlFor="nv-file">Fichier</label>
          <FilePicker id="nv-file" file={file} onChange={setFile} required />
        </div>
        <FlagsFields idPrefix="nv" fileName={file?.name ?? null} tableaux={tableaux} images={images} onTableaux={setTableaux} onImages={setImages} />
        {file && (
          <details className="rounded-lg border border-line p-3">
            <summary className="cursor-pointer text-sm text-navy-700">Aperçu du fichier avant l’envoi</summary>
            <div className="mt-3"><PreviewLocal file={file} /></div>
          </details>
        )}
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={busy || !file}>{busy ? 'Envoi…' : 'Ajouter la version'}</button>
        </div>
      </form>
    </Modal>
  )
}
