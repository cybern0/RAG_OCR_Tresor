// Modification d'un fichier : titre et cases tableaux / images. Le contenu ne se remplace pas ici : on ajoute une version.
// Un changement de case relance la lecture de la version la plus récente (les autres gardent leur index).
import { useState } from 'react'
import type { FormEvent } from 'react'
import { updateDocument } from '../../api/documents'
import { errorMessage } from '../../api/client'
import { ErrorBox } from '../../components/ui/Feedback'
import ExampleButton from '../../components/ui/ExampleButton'
import FlagsFields from '../../components/ui/FlagsFields'
import Modal from '../../components/ui/Modal'
import { exempleTitreFichier } from '../../lib/exemples'
import type { DocumentMeta } from '../../types/document'

interface Props {
  doc: DocumentMeta
  onClose: () => void
  onDone: () => void
}

export default function UpdateDocumentForm({ doc, onClose, onDone }: Props) {
  const [titre, setTitre] = useState(doc.titre)
  const [tableaux, setTableaux] = useState(doc.has_tabular)
  const [images, setImages] = useState(doc.has_image)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const flagsChanged = tableaux !== doc.has_tabular || images !== doc.has_image

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await updateDocument(doc.id, {
        titre: titre !== doc.titre ? titre : undefined,
        contientTableaux: tableaux !== doc.has_tabular ? tableaux : undefined,
        contientImages: images !== doc.has_image ? images : undefined,
      })
      onDone()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal title="Modifier le fichier" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="flex justify-end"><ExampleButton onFill={() => setTitre(exempleTitreFichier())} /></div>
        <div>
          <label className="label" htmlFor="up-title">Titre</label>
          <input id="up-title" className="input" required maxLength={250} value={titre} onChange={(e) => setTitre(e.target.value)} />
        </div>
        <FlagsFields idPrefix="up" fileName={doc.version.nom_fichier} tableaux={tableaux} images={images} onTableaux={setTableaux} onImages={setImages} />
        {flagsChanged && <p className="text-xs text-gold-300">La version la plus récente sera relue et réindexée avec ces options.</p>}
        <p className="text-xs text-cream-300">Pour changer le contenu, ajouter une nouvelle version : l’ancienne est conservée.</p>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={busy}>{busy ? 'Enregistrement…' : 'Enregistrer'}</button>
        </div>
      </form>
    </Modal>
  )
}
