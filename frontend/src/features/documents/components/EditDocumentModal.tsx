// Modification d'un fichier : titre et cases tableaux / images. Le contenu ne se remplace pas ici : on ajoute une version.
// Un changement de case relance la lecture de la version la plus récente (les autres gardent leur index).
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { exempleTitreFichier } from '../../../shared/lib/exemples'
import ExampleButton from '../../../shared/ui/ExampleButton'
import Field from '../../../shared/ui/Field'
import { ErrorBox } from '../../../shared/ui/Feedback'
import FlagsFields from '../../../shared/ui/FlagsFields'
import Modal from '../../../shared/ui/Modal'
import { useToast } from '../../../shared/hooks/useToast'
import { useDocumentMutations } from '../queries'
import type { DocumentMeta } from '../types'

export default function EditDocumentModal({ doc, onClose }: { doc: DocumentMeta; onClose: () => void }) {
  const { update } = useDocumentMutations()
  const toast = useToast()
  const [titre, setTitre] = useState(doc.titre)
  const [tableaux, setTableaux] = useState(doc.has_tabular)
  const [images, setImages] = useState(doc.has_image)
  const [error, setError] = useState<string | null>(null)
  const flagsChanged = tableaux !== doc.has_tabular || images !== doc.has_image

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await update.mutateAsync({
        id: doc.id,
        titre: titre !== doc.titre ? titre : undefined,
        contientTableaux: tableaux !== doc.has_tabular ? tableaux : undefined,
        contientImages: images !== doc.has_image ? images : undefined,
      })
      toast.success('Fichier modifié.')
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Modal title="Modifier le fichier" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end"><ExampleButton onFill={() => setTitre(exempleTitreFichier())} /></div>
        <Field label="Titre">{(id) => <input id={id} className="input" required maxLength={250} value={titre} onChange={(e) => setTitre(e.target.value)} />}</Field>
        <FlagsFields idPrefix="up" fileName={doc.version.nom_fichier} tableaux={tableaux} images={images} onTableaux={setTableaux} onImages={setImages} />
        {flagsChanged && <p className="text-xs text-navy-600">La version la plus récente sera relue et réindexée avec ces options.</p>}
        <p className="text-xs text-slate-600">Pour changer le contenu, ajouter une nouvelle version : l’ancienne est conservée.</p>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={update.isPending}>{update.isPending ? 'Enregistrement…' : 'Enregistrer'}</button>
        </div>
      </form>
    </Modal>
  )
}
