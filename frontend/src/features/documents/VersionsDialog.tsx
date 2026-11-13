// Historique des versions d'un fichier : date, auteur, état d'indexation ; aperçu, téléchargement et suppression
// (la suppression est réservée au gestionnaire de contenu). La version « qui fait foi » est la plus récente prête.
import { useCallback, useEffect, useState } from 'react'
import { deleteVersion, downloadVersion, listVersions } from '../../api/documents'
import { errorMessage } from '../../api/client'
import { ErrorBox, Loading } from '../../components/ui/Feedback'
import { PreviewStored } from '../../components/ui/FilePreview'
import Modal from '../../components/ui/Modal'
import { useLoad } from '../../hooks/useLoad'
import { formatDate, formatSize } from '../../lib/fichiers'
import type { DocumentMeta, Statut } from '../../types/document'
import { StatusBadge } from './StatusBadge'

interface Props {
  doc: DocumentMeta
  canDelete: boolean
  onClose: () => void
  onChanged: () => void
}

export default function VersionsDialog({ doc, canDelete, onClose, onChanged }: Props) {
  const versions = useLoad(useCallback(() => listVersions(doc.id), [doc.id]))
  const [selected, setSelected] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const list = versions.data ?? []
  const current = list.find((v) => v.numero === selected) ?? list[0] ?? null

  // tant qu'une version s'indexe, on actualise
  const pending = list.some((v) => (['pending', 'processing'] as Statut[]).includes(v.statut))
  const reload = versions.reload
  useEffect(() => {
    if (!pending) return
    const timer = setInterval(() => void reload(), 3000)
    return () => clearInterval(timer)
  }, [pending, reload])

  async function download(numero: number, nom: string) {
    setError(null)
    try {
      await downloadVersion(doc.id, numero, nom)
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function remove(numero: number) {
    if (!window.confirm(`Supprimer définitivement la version ${numero} ?`)) return
    setBusy(true)
    setError(null)
    try {
      await deleteVersion(doc.id, numero)
      setSelected(null)
      await reload()
      onChanged()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={`Versions de « ${doc.titre} »`} onClose={onClose} wide>
      <div className="space-y-4">
        <ErrorBox message={versions.error ?? error} />
        {versions.loading ? <Loading /> : (
          <ul className="max-h-56 space-y-2 overflow-y-auto">
            {list.map((v) => (
              <li key={v.numero}
                className={`rounded-lg border p-2.5 ${current?.numero === v.numero ? 'border-gold-400 bg-gold-500/10' : 'border-gold-500/30'}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <button className="text-left" onClick={() => setSelected(v.numero)} aria-label={`Afficher la version ${v.numero}`}>
                    <span className="font-semibold text-gold-300">v{v.numero}</span>
                    {v.est_courante && <span className="ml-2 badge border-emerald-300/70 bg-emerald-400/15 text-emerald-100">version qui fait foi</span>}
                    <span className="ml-2 text-sm">{v.nom_fichier}</span>
                    <span className="block text-xs text-cream-300">
                      {formatDate(v.cree_le)} · {v.cree_par_nom ?? 'auteur inconnu'} · {formatSize(v.taille_octets)}
                      {v.nb_pages ? ` · ${v.nb_pages} p.` : ''}{v.ocr_utilise ? ' · OCR' : ''}
                    </span>
                  </button>
                  <div className="flex items-center gap-2">
                    <StatusBadge statut={v.statut} />
                    <button className="btn-ghost" onClick={() => void download(v.numero, v.nom_fichier)}>Télécharger</button>
                    {canDelete && list.length > 1 && (
                      <button className="btn-danger" disabled={busy || v.statut === 'processing'} onClick={() => void remove(v.numero)}>Supprimer</button>
                    )}
                  </div>
                </div>
                {v.statut === 'error' && v.message_erreur && <p className="mt-1 text-xs text-red-200">{v.message_erreur}</p>}
              </li>
            ))}
          </ul>
        )}
        {current && (
          <div>
            <p className="mb-2 text-sm font-medium text-gold-400">Aperçu de la version {current.numero}</p>
            <PreviewStored key={`${doc.id}-${current.numero}`} documentId={doc.id} numero={current.numero} mode={current.apercu} />
          </div>
        )}
      </div>
    </Modal>
  )
}
