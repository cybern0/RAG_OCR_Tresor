// Métadonnées documentaires d'un ou de plusieurs fichiers : catégorie, type, confidentialité, étiquettes.
// Seuls les champs renseignés sont modifiés ; un classement manuel n'est plus écrasé par les règles automatiques.
// (N'a rien à voir avec l'accès : celui-ci se décide par l'affectation manuelle du chef — AffectationModal.)
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { plural } from '../../../shared/lib/format'
import Field from '../../../shared/ui/Field'
import { ErrorBox, Loading } from '../../../shared/ui/Feedback'
import Modal from '../../../shared/ui/Modal'
import { useToast } from '../../../shared/hooks/useToast'
import { useDocumentMutations, useReferentiel } from '../queries'
import type { DocumentMeta } from '../types'

export default function ClassifyModal({ docs, onClose, onDone }: { docs: DocumentMeta[]; onClose: () => void; onDone?: () => void }) {
  const ref = useReferentiel()
  const { classer } = useDocumentMutations()
  const toast = useToast()
  const single = docs.length === 1 ? docs[0] : null
  const [categorie, setCategorie] = useState<number | ''>(single?.categorie_id ?? '')
  const [type, setType] = useState<number | ''>(single?.type_document_id ?? '')
  const [conf, setConf] = useState<string>(single?.confidentialite ?? '')
  const [tags, setTags] = useState(single ? single.tags.join(', ') : '')
  const [replaceTags, setReplaceTags] = useState(!!single)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const result = await classer.mutateAsync({
        ids: docs.map((d) => d.id),
        categorie_id: categorie || undefined,
        type_document_id: type || undefined,
        confidentialite: conf || undefined,
        tags: replaceTags ? tags.split(/[;,\n]+/).map((t) => t.trim()).filter(Boolean) : undefined,
      })
      if (result.forbidden.length) toast.error(`${plural(result.forbidden.length, 'fichier')} non modifié(s) : droits insuffisants.`)
      if (result.ok.length) toast.success(`${plural(result.ok.length, 'fichier mis à jour', 'fichiers mis à jour')}.`)
      onDone?.()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Modal title={single ? `Métadonnées de « ${single.titre} »` : `Métadonnées de ${plural(docs.length, 'fichier')}`} onClose={onClose}>
      {ref.isPending ? <Loading /> : (
        <form onSubmit={(e) => void submit(e)} className="space-y-4">
          {!single && <p className="text-xs text-slate-600">Seuls les champs renseignés sont appliqués aux fichiers sélectionnés.</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Catégorie">
              {(id) => (
                <select id={id} className="input" value={categorie} onChange={(e) => setCategorie(e.target.value ? Number(e.target.value) : '')}>
                  <option value="">{single ? '— Aucune —' : '— Ne pas modifier —'}</option>
                  {ref.data?.categories.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
                </select>
              )}
            </Field>
            <Field label="Type de document">
              {(id) => (
                <select id={id} className="input" value={type} onChange={(e) => setType(e.target.value ? Number(e.target.value) : '')}>
                  <option value="">{single ? '— Aucun —' : '— Ne pas modifier —'}</option>
                  {ref.data?.types.map((t) => <option key={t.id} value={t.id}>{t.nom}</option>)}
                </select>
              )}
            </Field>
          </div>
          <Field label="Confidentialité">
            {(id) => (
              <select id={id} className="input" value={conf} onChange={(e) => setConf(e.target.value)}>
                {!single && <option value="">— Ne pas modifier —</option>}
                {ref.data?.confidentialites.map((c) => <option key={c} value={c}>{c.charAt(0) + c.slice(1).toLowerCase()}</option>)}
              </select>
            )}
          </Field>
          <Field label="Étiquettes" hint="Séparées par des virgules. Les étiquettes inconnues sont créées.">
            {(id) => (
              <>
                {!single && (
                  <label className="mb-2 flex items-center gap-2 text-sm">
                    <input type="checkbox" className="h-4 w-4 accent-navy-700" checked={replaceTags} onChange={(e) => setReplaceTags(e.target.checked)} /> Remplacer les étiquettes manuelles
                  </label>
                )}
                <input id={id} className="input" list="tags-connus" disabled={!replaceTags} placeholder="finance, rh" value={tags} onChange={(e) => setTags(e.target.value)} />
                <datalist id="tags-connus">{ref.data?.tags.map((t) => <option key={t.id} value={t.nom} />)}</datalist>
              </>
            )}
          </Field>
          <ErrorBox message={error} />
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
            <button className="btn" disabled={classer.isPending}>{classer.isPending ? 'Enregistrement…' : 'Enregistrer'}</button>
          </div>
        </form>
      )}
    </Modal>
  )
}
