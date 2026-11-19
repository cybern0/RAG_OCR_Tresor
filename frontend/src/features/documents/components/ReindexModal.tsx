import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { forcedFlags } from '../../../shared/lib/fichiers'
import { ErrorBox } from '../../../shared/ui/Feedback'
import FlagsFields from '../../../shared/ui/FlagsFields'
import Modal from '../../../shared/ui/Modal'
import { useToast } from '../../../shared/hooks/useToast'
import { useDocumentMutations } from '../queries'
import type { DocumentMeta, VersionMeta } from '../types'

const oui = (b: boolean) => (b ? 'oui' : 'non')

/**
 * Réindexation d'une version déjà stockée : le fichier est relu, sans nouvelle version.
 * Utile après une erreur d'indexation, ou si l'on avait oublié de signaler des tableaux ou des images.
 * Une version prête n'est relue que si une case change par rapport à sa dernière indexation (le serveur le vérifie aussi).
 */
export default function ReindexModal({ doc, version, onClose }: { doc: DocumentMeta; version: VersionMeta; onClose: () => void }) {
  const { reindex } = useDocumentMutations()
  const toast = useToast()
  const [tableaux, setTableaux] = useState(doc.has_tabular)
  const [images, setImages] = useState(doc.has_image)
  const [error, setError] = useState<string | null>(null)

  const forced = forcedFlags(version.nom_fichier)
  const demande = { tableaux: tableaux || forced.tableaux, images: images || forced.images }
  // inconnu (indexée avant la mise à jour) : on se rabat sur les cases actuelles du fichier, comme le serveur
  const deja = { tableaux: version.tableaux_indexes ?? doc.has_tabular, images: version.images_indexes ?? doc.has_image }
  const enErreur = version.statut === 'error'
  const inchange = !enErreur && demande.tableaux === deja.tableaux && demande.images === deja.images

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (inchange) return
    setError(null)
    try {
      await reindex.mutateAsync({ id: doc.id, numero: version.numero, contientTableaux: demande.tableaux, contientImages: demande.images })
      toast.success(`Réindexation de la version ${version.numero} lancée.`)
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Modal title={`${enErreur ? 'Relancer l’indexation' : 'Réindexer'} · version ${version.numero}`} onClose={onClose} size="lg">
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <p className="text-sm text-cream-300">
          Le fichier <span className="font-medium text-gold-300">{version.nom_fichier}</span> déjà enregistré est relu : <strong>aucune nouvelle version n’est créée</strong>.
          Pendant la relecture, cette version n’est pas interrogeable.
        </p>
        {enErreur && version.message_erreur && <p className="rounded-lg border border-red-300/30 p-2 text-xs text-red-200">Dernière erreur : {version.message_erreur}</p>}
        <FlagsFields idPrefix="ri" fileName={version.nom_fichier} tableaux={tableaux} images={images} onTableaux={setTableaux} onImages={setImages} />
        {inchange && (
          <p className="rounded-lg border border-amber-300/40 p-2 text-sm text-amber-100" role="status">
            Déjà indexée avec ces paramètres (tableaux : {oui(deja.tableaux)}, images : {oui(deja.images)}). Modifiez au moins une case pour relancer l’indexation.
          </p>
        )}
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn" disabled={reindex.isPending || inchange}>{reindex.isPending ? 'Lancement…' : enErreur ? 'Relancer l’indexation' : 'Réindexer'}</button>
        </div>
      </form>
    </Modal>
  )
}
