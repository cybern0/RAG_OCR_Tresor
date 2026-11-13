// Cases « contient des tableaux » et « contient des images ». Si le type du fichier l'impose (tableur, image), la case
// est cochée et non modifiable ; sinon elle est libre. Même composant à la création, à la nouvelle version et à la modification.
import { forcedFlags } from '../../lib/fichiers'

interface Props {
  fileName: string | null // nom du fichier concerné (null : aucun fichier choisi encore)
  tableaux: boolean
  images: boolean
  onTableaux: (v: boolean) => void
  onImages: (v: boolean) => void
  idPrefix: string
}

export default function FlagsFields({ fileName, tableaux, images, onTableaux, onImages, idPrefix }: Props) {
  const forced = fileName ? forcedFlags(fileName) : { tableaux: false, images: false }
  const rows = [
    { id: 'tab', label: 'Ce fichier contient des tableaux', value: tableaux || forced.tableaux, locked: forced.tableaux, set: onTableaux,
      aide: 'Les tableaux sont lus et indexés avec leur en-tête.', imposeAide: 'Imposé : un tableur est toujours lu comme un tableau.' },
    { id: 'img', label: 'Ce fichier contient des images', value: images || forced.images, locked: forced.images, set: onImages,
      aide: 'Le texte des images est lu par OCR, en plus du texte normal.', imposeAide: 'Imposé : une image est toujours lue par OCR.' },
  ]
  return (
    <fieldset className="space-y-2">
      <legend className="sr-only">Contenu du fichier</legend>
      {rows.map((r) => (
        <div key={r.id}>
          <label className="flex items-center gap-2 text-sm">
            <input id={`${idPrefix}-${r.id}`} type="checkbox" className="h-4 w-4 accent-gold-500" checked={r.value} disabled={r.locked}
              onChange={(e) => r.set(e.target.checked)} />
            {r.label}
          </label>
          <p className="ml-6 text-xs text-cream-300">{r.locked ? r.imposeAide : r.aide}</p>
        </div>
      ))}
    </fieldset>
  )
}
