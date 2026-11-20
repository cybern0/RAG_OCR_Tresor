// Aperçu d'une version enregistrée : le serveur renvoie le fichier (ou son PDF converti), selon les rôles du fichier.
import { useQuery } from '@tanstack/react-query'
import { errorMessage } from '../../../shared/api/client'
import { ErrorBox, Loading } from '../../../shared/ui/Feedback'
import { BlobPreview } from '../../../shared/ui/FilePreview'
import { fetchPreview } from '../api'
import type { ApercuMode } from '../types'

export function PreviewStored({ documentId, numero, mode, tall }: { documentId: number; numero: number; mode: ApercuMode; tall?: boolean }) {
  const preview = useQuery({
    queryKey: ['documents', 'one', documentId, 'apercu', numero],
    queryFn: () => fetchPreview(documentId, numero),
    enabled: mode !== 'aucun',
    staleTime: Infinity,
    gcTime: 60_000,
    retry: false,
  })

  if (mode === 'aucun') return <p className="rounded-lg border border-line p-4 text-sm text-slate-600">Pas d’aperçu pour ce type de fichier ici : le télécharger pour le lire.</p>
  if (preview.error) return <ErrorBox message={errorMessage(preview.error)} />
  if (!preview.data) return <Loading label="Chargement de l’aperçu…" />
  return <BlobPreview kind={mode === 'pdf_converti' ? 'pdf' : mode} blob={preview.data} tall={tall} />
}
