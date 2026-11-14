import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { formatDate } from '../../../shared/lib/format'
import { ErrorBox, Loading } from '../../../shared/ui/Feedback'
import { addComment } from '../api'
import { docKeys, useComments } from '../queries'

/** Commentaires d'un fichier (visibles et rédigés par les contributeurs et plus). */
export function CommentsPanel({ documentId }: { documentId: number }) {
  const qc = useQueryClient()
  const comments = useComments(documentId, true)
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const post = useMutation({ mutationFn: (contenu: string) => addComment(documentId, contenu), onSuccess: () => qc.invalidateQueries({ queryKey: docKeys.comments(documentId) }) })

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    setError(null)
    try { await post.mutateAsync(text.trim()); setText('') } catch (err) { setError(errorMessage(err)) }
  }

  return (
    <div className="space-y-3">
      {comments.isPending ? <Loading className="py-3" /> : (comments.data ?? []).length === 0 ? <p className="text-sm text-cream-300">Aucun commentaire.</p> : (
        <ul className="space-y-2">
          {(comments.data ?? []).map((c, i) => (
            <li key={i} className="rounded-lg border border-gold-500/25 bg-leaf-950/40 p-2.5 text-sm">
              <p className="text-xs text-cream-300"><span className="font-medium text-gold-300">{c.author_name ?? `Utilisateur ${c.author_id}`}</span> · {formatDate(c.created_at)}</p>
              <p className="mt-1 whitespace-pre-wrap">{c.content}</p>
            </li>
          ))}
        </ul>
      )}
      <ErrorBox message={error ?? (comments.error ? errorMessage(comments.error) : null)} />
      <form onSubmit={(e) => void submit(e)} className="flex gap-2">
        <input className="input" aria-label="Nouveau commentaire" placeholder="Ajouter un commentaire…" maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} />
        <button className="btn" disabled={!text.trim() || post.isPending}>Publier</button>
      </form>
    </div>
  )
}
