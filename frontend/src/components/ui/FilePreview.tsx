// Aperçu d'un contenu : PDF, image, texte, CSV. Sert à l'aperçu local d'un fichier avant l'envoi (PreviewLocal) et à
// l'aperçu d'une version déjà enregistrée, récupéré via l'API (PreviewStored).
// Un PDF s'affiche dans un cadre du navigateur à partir d'un Blob créé ici avec le type imposé ; texte et CSV sont
// affichés comme du texte, jamais comme du HTML.
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/client'
import { fetchPreview } from '../../api/documents'
import type { ApercuMode } from '../../types/document'
import { localPreviewKind, parseCsv } from '../../lib/fichiers'
import type { PreviewKind } from '../../lib/fichiers'
import { ErrorBox, Loading } from './Feedback'

const MAX_TEXT = 60_000

function Content({ kind, blob }: { kind: PreviewKind; blob: Blob }) {
  const [url, setUrl] = useState<string | null>(null)
  const [text, setText] = useState<string | null>(null)

  useEffect(() => {
    let revoked: string | null = null
    let cancelled = false
    if (kind === 'pdf' || kind === 'image') {
      // l'URL est créée dans un callback (et révoquée au nettoyage) : pas de setState synchrone dans l'effet
      void Promise.resolve().then(() => {
        if (cancelled) return
        revoked = URL.createObjectURL(kind === 'pdf' ? new Blob([blob], { type: 'application/pdf' }) : blob)
        setUrl(revoked)
      })
    } else if (kind === 'texte' || kind === 'csv') {
      void blob.slice(0, MAX_TEXT).text().then((t) => { if (!cancelled) setText(t) })
    }
    return () => {
      cancelled = true
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [kind, blob])

  if (kind === 'pdf' && url) return <iframe title="Aperçu du fichier" src={url} className="h-[60svh] w-full rounded-lg border border-line bg-white" />
  if (kind === 'image' && url) return <img src={url} alt="Aperçu du fichier" className="mx-auto max-h-[60svh] max-w-full rounded-lg" />
  if (kind === 'csv' && text !== null) {
    const rows = parseCsv(text)
    return (
      <div className="max-h-[60svh] overflow-auto rounded-lg border border-line">
        <table className="w-full border-collapse text-xs">
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className={i === 0 ? 'bg-slate-100 font-semibold text-navy-600' : ''}>
                {r.map((c, j) => <td key={j} className="border border-slate-200 px-2 py-1">{c}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  if (kind === 'texte' && text !== null) {
    return <pre className="max-h-[60svh] overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-slate-50 p-3 text-xs">{text}</pre>
  }
  return <Loading />
}

const NO_PREVIEW = 'Pas d’aperçu pour ce type de fichier ici : le télécharger pour le lire.'

/** Aperçu d'un fichier choisi sur l'ordinateur, avant l'envoi. */
export function PreviewLocal({ file }: { file: File }) {
  const kind = localPreviewKind(file.name)
  if (kind === 'aucun') {
    return <p className="rounded-lg border border-line p-3 text-xs text-slate-600">Aperçu disponible après l’envoi (le serveur convertit Word, PowerPoint et OpenDocument en PDF).</p>
  }
  return <Content kind={kind} blob={file} />
}

/** Aperçu d'une version enregistrée : le serveur renvoie le fichier (ou son PDF converti), selon le rôle de dossier. */
export function PreviewStored({ documentId, numero, mode }: { documentId: number; numero: number; mode: ApercuMode }) {
  const [state, setState] = useState<{ blob: Blob | null; error: string | null }>({ blob: null, error: null })

  useEffect(() => {
    if (mode === 'aucun') return
    let cancelled = false
    fetchPreview(documentId, numero)
      .then((blob) => { if (!cancelled) setState({ blob, error: null }) })
      .catch((e: unknown) => { if (!cancelled) setState({ blob: null, error: errorMessage(e) }) })
    return () => { cancelled = true }
  }, [documentId, numero, mode])

  if (mode === 'aucun') return <p className="text-sm text-slate-600">{NO_PREVIEW}</p>
  if (state.error) return <ErrorBox message={state.error} />
  if (!state.blob) return <Loading label={mode === 'pdf_converti' ? 'Conversion en PDF…' : 'Chargement…'} />
  return <Content kind={mode === 'pdf_converti' ? 'pdf' : mode} blob={state.blob} />
}
