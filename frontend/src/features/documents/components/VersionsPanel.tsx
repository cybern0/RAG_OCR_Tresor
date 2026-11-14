// Historique des versions : date, auteur, état d'indexation ; sélection pour l'aperçu, téléchargement, suppression
// (suppression réservée au gestionnaire de contenu). La version « qui fait foi » est la plus récente prête.
import { Download, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { formatDate, formatSize } from '../../../shared/lib/format'
import Badge from '../../../shared/ui/Badge'
import ConfirmDialog from '../../../shared/ui/ConfirmDialog'
import { cn } from '../../../shared/lib/cn'
import { useToast } from '../../../shared/hooks/useToast'
import { downloadVersion } from '../api'
import { useDocumentMutations } from '../queries'
import type { VersionMeta } from '../types'
import { StatusBadge } from './StatusBadge'

interface Props { documentId: number; versions: VersionMeta[]; selected: number; onSelect: (n: number) => void; canDelete: boolean }

export function VersionsPanel({ documentId, versions, selected, onSelect, canDelete }: Props) {
  const toast = useToast()
  const { removeVersion } = useDocumentMutations()
  const [toDelete, setToDelete] = useState<number | null>(null)

  return (
    <>
      <ul className="space-y-2">
        {versions.map((v) => (
          <li key={v.numero} className={cn('rounded-lg border p-2.5', selected === v.numero ? 'border-gold-400 bg-gold-500/10' : 'border-gold-500/25')}>
            <button className="block w-full text-left" onClick={() => onSelect(v.numero)} aria-pressed={selected === v.numero}>
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-gold-300">v{v.numero}</span>
                {v.est_courante && <Badge tone="green">fait foi</Badge>}
                <StatusBadge statut={v.statut} />
              </span>
              <span className="mt-1 block truncate text-sm">{v.nom_fichier}</span>
              <span className="block text-xs text-cream-300">{formatDate(v.cree_le)} · {v.cree_par_nom ?? 'auteur inconnu'} · {formatSize(v.taille_octets)}{v.nb_pages ? ` · ${v.nb_pages} p.` : ''}{v.ocr_utilise ? ' · OCR' : ''}</span>
            </button>
            {v.statut === 'error' && v.message_erreur && <p className="mt-1 text-xs text-red-200">{v.message_erreur}</p>}
            <div className="mt-1 flex justify-end gap-1">
              <button className="btn-icon" title="Télécharger" aria-label={`Télécharger la version ${v.numero}`}
                onClick={() => void downloadVersion(documentId, v.numero, v.nom_fichier).catch((e) => toast.error(errorMessage(e)))}><Download className="h-4 w-4" /></button>
              {canDelete && versions.length > 1 && (
                <button className="btn-icon text-red-300" disabled={v.statut === 'processing'} title="Supprimer cette version" aria-label={`Supprimer la version ${v.numero}`} onClick={() => setToDelete(v.numero)}><Trash2 className="h-4 w-4" /></button>
              )}
            </div>
          </li>
        ))}
      </ul>
      {toDelete !== null && (
        <ConfirmDialog title={`Supprimer la version ${toDelete}`} confirmLabel="Supprimer la version" onClose={() => setToDelete(null)}
          onConfirm={async () => { await removeVersion.mutateAsync({ id: documentId, numero: toDelete }); toast.success(`Version ${toDelete} supprimée.`); if (selected === toDelete) onSelect(versions.find((v) => v.numero !== toDelete)!.numero) }}>
          Supprimer définitivement la version {toDelete} et ses passages indexés ?
        </ConfirmDialog>
      )}
    </>
  )
}
