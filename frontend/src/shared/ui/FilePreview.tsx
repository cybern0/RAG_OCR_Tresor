// Aperçu d'un contenu : PDF, image, texte, CSV. Un PDF s'affiche dans un cadre du navigateur à partir d'un Blob créé ici
// avec le type imposé ; texte et CSV sont affichés comme du texte, jamais comme du HTML.
import { useEffect, useState } from 'react'
import { localPreviewKind, parseCsv } from '../lib/fichiers'
import type { PreviewKind } from '../lib/fichiers'
import { Loading } from './Feedback'

const MAX_TEXT = 60_000

export function BlobPreview({ kind, blob, tall = false }: { kind: PreviewKind; blob: Blob; tall?: boolean }) {
  const [url, setUrl] = useState<string | null>(null)
  const [text, setText] = useState<string | null>(null)
  const height = tall ? 'h-[75svh]' : 'h-[55svh]'
  const maxHeight = tall ? 'max-h-[75svh]' : 'max-h-[55svh]'

  useEffect(() => {
    let created: string | null = null
    let cancelled = false
    if (kind === 'pdf' || kind === 'image') {
      void Promise.resolve().then(() => {
        if (cancelled) return
        created = URL.createObjectURL(kind === 'pdf' ? new Blob([blob], { type: 'application/pdf' }) : blob)
        setUrl(created)
      })
    } else if (kind === 'texte' || kind === 'csv') {
      void blob.slice(0, MAX_TEXT).text().then((t) => { if (!cancelled) setText(t) })
    }
    return () => {
      cancelled = true
      if (created) URL.revokeObjectURL(created)
    }
  }, [kind, blob])

  if (kind === 'pdf' && url) return <iframe title="Aperçu du fichier" src={url} className={`${height} w-full rounded-lg border border-gold-500/30 bg-white`} />
  if (kind === 'image' && url) return <img src={url} alt="Aperçu du fichier" className={`mx-auto ${maxHeight} max-w-full rounded-lg`} />
  if (kind === 'csv' && text !== null) {
    const rows = parseCsv(text)
    return (
      <div className={`${maxHeight} overflow-auto rounded-lg border border-gold-500/30`}>
        <table className="w-full border-collapse text-xs">
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className={i === 0 ? 'bg-leaf-900 font-semibold text-gold-300' : ''}>
                {r.map((c, j) => <td key={j} className="border border-leaf-700 px-2 py-1">{c}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  if (kind === 'texte' && text !== null) {
    return <pre className={`${maxHeight} overflow-auto whitespace-pre-wrap rounded-lg border border-gold-500/30 bg-leaf-950/60 p-3 text-xs`}>{text}</pre>
  }
  return <Loading />
}

/** Aperçu d'un fichier choisi sur l'ordinateur, avant l'envoi. */
export function PreviewLocal({ file }: { file: File }) {
  const kind = localPreviewKind(file.name)
  if (kind === 'aucun') {
    return <p className="rounded-lg border border-gold-500/30 p-3 text-xs text-cream-300">Aperçu disponible après l’envoi (le serveur convertit Word, PowerPoint et OpenDocument en PDF).</p>
  }
  return <BlobPreview kind={kind} blob={file} />
}
