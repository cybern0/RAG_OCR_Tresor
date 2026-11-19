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
import { useDocumentMutations } from '../queries'

/** Dépose un fichier directement dans une division (plus de dossiers), sans classement : l'accès des
 * autres agents se décide ensuite par l'affectation manuelle du chef (page Fichiers ou Rôles).
 * divisions : là où le compte peut déposer (une seule -> champ fixe, plusieurs -> sélecteur). */
export default function AddDocumentModal({ divisions, onClose }: { divisions: { id: number; nom: string }[]; onClose: () => void }) {
  const { add } = useDocumentMutations()
  const toast = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [titre, setTitre] = useState('')
  const [tableaux, setTableaux] = useState(false)
  const [images, setImages] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [divisionId, setDivisionId] = useState<number | ''>(divisions[0]?.id ?? '')
  const divisionNom = divisions.find((d) => d.id === divisionId)?.nom ?? ''

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file || divisionId === '') return
    setError(null)
    try {
      await add.mutateAsync({ fichier: file, titre, divisionId, contientTableaux: tableaux, contientImages: images })
      toast.success('Fichier ajouté : il attend son affectation par le chef ; indexation en cours.')
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Modal title="Ajouter un fichier" onClose={onClose} size="lg">
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          {divisions.length > 1 ? (
            <label className="flex flex-1 items-center gap-2 text-sm text-cream-300">Division
              <select className="input w-auto" aria-label="Division de dépôt" value={divisionId} onChange={(e) => setDivisionId(e.target.value ? Number(e.target.value) : '')}>
                {divisions.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
              </select>
            </label>
          ) : (
            <p className="text-sm text-cream-300">Division : <span className="font-medium text-gold-300">{divisionNom}</span></p>
          )}
          <ExampleButton onFill={() => { setFile(exempleFichier()); setTitre(exempleTitreFichier()); setTableaux(false); setImages(false) }} />
        </div>
        <Field label="Fichier" hint="PDF, Word, PowerPoint, Excel, CSV, texte, images (scans). Maximum 50 Mo.">
          {(id) => <FilePicker id={id} file={file} onChange={setFile} required />}
        </Field>
        <Field label="Titre">
          {(id) => <input id={id} className="input" maxLength={250} placeholder="Par défaut : nom du fichier" value={titre} onChange={(e) => setTitre(e.target.value)} />}
        </Field>
        <FlagsFields idPrefix="add" fileName={file?.name ?? null} tableaux={tableaux} images={images} onTableaux={setTableaux} onImages={setImages} />
        <p className="text-xs text-cream-300">Vous (et les chefs de la division) verrez toujours ce fichier. Pour donner l'accès à d'autres agents, le chef utilise « Affecter » sur la fiche du fichier.</p>
        {file && (
          <details className="rounded-lg border border-gold-500/30 p-3">
            <summary className="cursor-pointer text-sm text-gold-400">Aperçu du fichier avant l'envoi</summary>
            <div className="mt-3"><PreviewLocal file={file} /></div>
          </details>
        )}
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={add.isPending || !file || divisionId === ''}>{add.isPending ? 'Envoi…' : 'Ajouter'}</button>
        </div>
      </form>
    </Modal>
  )
}
