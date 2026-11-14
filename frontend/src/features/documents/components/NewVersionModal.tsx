import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { exempleFichier } from '../../../shared/lib/exemples'
import ExampleButton from '../../../shared/ui/ExampleButton'
import Field from '../../../shared/ui/Field'
import { ErrorBox } from '../../../shared/ui/Feedback'
import FilePicker from '../../../shared/ui/FilePicker'
import { PreviewLocal } from '../../../shared/ui/FilePreview'
import FlagsFields from '../../../shared/ui/FlagsFields'
import Modal from '../../../shared/ui/Modal'
import { useToast } from '../../../shared/hooks/useToast'
import { useDocumentMutations } from '../queries'
import type { DocumentMeta } from '../types'

/** Dépôt d'une nouvelle version : la version précédente est conservée (indexée, téléchargeable, interrogeable). */
export default function NewVersionModal({ doc, onClose }: { doc: DocumentMeta; onClose: () => void }) {
  const { addVersion } = useDocumentMutations()
  const toast = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [tableaux, setTableaux] = useState(doc.has_tabular)
  const [images, setImages] = useState(doc.has_image)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    setError(null)
    try {
      await addVersion.mutateAsync({ id: doc.id, fichier: file, contientTableaux: tableaux, contientImages: images })
      toast.success(`Version ${doc.nb_versions + 1} ajoutée : indexation en cours.`)
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Modal title={`Nouvelle version de « ${doc.titre} »`} onClose={onClose} size="lg">
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm text-cream-300">
            Version actuelle : <span className="font-medium text-gold-300">v{doc.version.numero}</span>. La nouvelle version s’ajoute : l’ancienne reste consultable, téléchargeable et interrogeable par l’assistant.
          </p>
          <ExampleButton className="shrink-0" onFill={() => { setFile(exempleFichier()); setTableaux(false); setImages(false) }} />
        </div>
        <Field label="Fichier">{(id) => <FilePicker id={id} file={file} onChange={setFile} required />}</Field>
        <FlagsFields idPrefix="nv" fileName={file?.name ?? null} tableaux={tableaux} images={images} onTableaux={setTableaux} onImages={setImages} />
        {file && (
          <details className="rounded-lg border border-gold-500/30 p-3">
            <summary className="cursor-pointer text-sm text-gold-400">Aperçu du fichier avant l’envoi</summary>
            <div className="mt-3"><PreviewLocal file={file} /></div>
          </details>
        )}
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={addVersion.isPending || !file}>{addVersion.isPending ? 'Envoi…' : 'Ajouter la version'}</button>
        </div>
      </form>
    </Modal>
  )
}
