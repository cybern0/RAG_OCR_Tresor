import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { exempleFichier, exempleTitreFichier } from '../../../shared/lib/exemples'
import ExampleButton from '../../../shared/ui/ExampleButton'
import Field from '../../../shared/ui/Field'
import { ErrorBox } from '../../../shared/ui/Feedback'
import FilePicker from '../../../shared/ui/FilePicker'
import { PreviewLocal } from '../../../shared/ui/FilePreview'
import FlagsFields from '../../../shared/ui/FlagsFields'
import Modal from '../../../shared/ui/Modal'
import { useToast } from '../../../shared/hooks/useToast'
import type { Dossier } from '../../dossiers/types'
import { useDocumentMutations } from '../queries'

export default function AddDocumentModal({ dossier, onClose }: { dossier: Dossier; onClose: () => void }) {
  const { add } = useDocumentMutations()
  const toast = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [titre, setTitre] = useState('')
  const [tableaux, setTableaux] = useState(false)
  const [images, setImages] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    setError(null)
    try {
      await add.mutateAsync({ fichier: file, titre, dossierId: dossier.id, contientTableaux: tableaux, contientImages: images })
      toast.success('Fichier ajouté : indexation en cours.')
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Modal title="Ajouter un fichier" onClose={onClose} size="lg">
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-cream-300">Dossier : <span className="font-medium text-gold-300">{dossier.nom}</span></p>
          <ExampleButton onFill={() => { setFile(exempleFichier()); setTitre(exempleTitreFichier()); setTableaux(false); setImages(false) }} />
        </div>
        <Field label="Fichier" hint="PDF, Word, PowerPoint, Excel, CSV, texte, images (scans). Maximum 50 Mo.">
          {(id) => <FilePicker id={id} file={file} onChange={setFile} required />}
        </Field>
        <Field label="Titre">
          {(id) => <input id={id} className="input" maxLength={250} placeholder="Par défaut : nom du fichier" value={titre} onChange={(e) => setTitre(e.target.value)} />}
        </Field>
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
          <button className="btn" disabled={add.isPending || !file}>{add.isPending ? 'Envoi…' : 'Ajouter'}</button>
        </div>
      </form>
    </Modal>
  )
}
