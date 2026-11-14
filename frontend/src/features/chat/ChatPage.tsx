// Assistant : historique des conversations (dans l'URL), réponses en streaming, sources citées (avec version et date).
// Mémoire dans une session : obligatoire (la conversation est relue côté serveur) ; deux options personnelles :
// mémoire entre sessions, dernière version seulement.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, Plus, Send, Settings2, Square, Trash2, User } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { errorMessage } from '../../shared/api/client'
import { cn } from '../../shared/lib/cn'
import { exempleQuestion } from '../../shared/lib/exemples'
import { formatDay } from '../../shared/lib/format'
import ConfirmDialog from '../../shared/ui/ConfirmDialog'
import ExampleButton from '../../shared/ui/ExampleButton'
import { ErrorBox } from '../../shared/ui/Feedback'
import { deleteConversation, getPreferences, listConversations, setPreferences } from './api'
import type { ChatPreferences, ConversationItem } from './api'
import { useChatStream } from './useChatStream'
import type { ChatMessage } from './useChatStream'

const keys = { conversations: ['chat', 'conversations'] as const, preferences: ['chat', 'preferences'] as const }

function Sources({ message }: { message: ChatMessage }) {
  if (message.sources.length === 0) return null
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-gold-400 hover:text-gold-300">Sources ({message.sources.length})</summary>
      <ul className="mt-2 space-y-2">
        {message.sources.map((s) => (
          <li key={s.ref} className="rounded-lg border border-gold-500/30 bg-leaf-950/50 p-2.5">
            <p className="font-medium text-gold-300">
              [{s.ref}]{' '}
              {s.dossier_id ? <Link className="underline decoration-dotted underline-offset-2" to={`/dossiers/${s.dossier_id}/fichiers/${s.document_id}`}>{s.titre}</Link> : s.titre}
              {s.version ? <span className="text-cream-300"> · version {s.version}{s.date ? ` du ${formatDay(s.date)}` : ''}</span> : null}
              {s.page ? <span className="text-cream-300"> · page {s.page}</span> : null}
            </p>
            <p className="mt-1 text-xs text-cream-300">{s.extrait}…</p>
          </li>
        ))}
      </ul>
    </details>
  )
}

function Options() {
  const qc = useQueryClient()
  const prefs = useQuery({ queryKey: keys.preferences, queryFn: getPreferences })
  const change = useMutation({ mutationFn: (patch: Partial<ChatPreferences>) => setPreferences(patch), onSuccess: (data) => qc.setQueryData(keys.preferences, data) })
  if (!prefs.data) return <ErrorBox message={prefs.error ? errorMessage(prefs.error) : null} />
  return (
    <div className="space-y-2 rounded-lg border border-gold-500/30 p-3 text-sm">
      <ErrorBox message={change.error ? errorMessage(change.error) : null} />
      <label className="flex items-start gap-2">
        <input type="checkbox" className="mt-0.5 h-4 w-4 accent-gold-500" checked={prefs.data.derniere_version_seulement} onChange={(e) => change.mutate({ derniere_version_seulement: e.target.checked })} />
        <span>Dernière version seulement<span className="block text-xs text-cream-300">Ignorer les anciennes versions des fichiers dans les réponses.</span></span>
      </label>
      <label className="flex items-start gap-2">
        <input type="checkbox" className="mt-0.5 h-4 w-4 accent-gold-500" checked={prefs.data.memoire_inter_sessions} onChange={(e) => change.mutate({ memoire_inter_sessions: e.target.checked })} />
        <span>Mémoire entre sessions<span className="block text-xs text-cream-300">Retenir le résultat de mes échanges pour enrichir mes prochaines conversations.</span></span>
      </label>
    </div>
  )
}

export function Component() {
  const params = useParams()
  const [search] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const conversationId = params.conversationId ? Number(params.conversationId) : null
  const wantsNew = search.has('nouveau')

  const history = useQuery({ queryKey: keys.conversations, queryFn: listConversations })
  const onCreated = useCallback((id: number) => {
    void qc.invalidateQueries({ queryKey: keys.conversations })
    navigate(`/chat/${id}`, { replace: true })
  }, [qc, navigate])
  const chat = useChatStream(conversationId, onCreated)

  const [question, setQuestion] = useState('')
  const [showOptions, setShowOptions] = useState(false)
  const [toDelete, setToDelete] = useState<ConversationItem | null>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const autoOpened = useRef(false)

  // À l'arrivée sur /chat, on rouvre la dernière conversation (l'historique est relu côté serveur)
  const latest = history.data?.[0]?.id ?? null
  useEffect(() => {
    if (autoOpened.current || history.data === undefined || conversationId !== null || wantsNew) return
    autoOpened.current = true
    if (latest !== null) navigate(`/chat/${latest}`, { replace: true })
  }, [history.data, latest, conversationId, wantsNew, navigate])

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [chat.messages])

  async function submit(e: FormEvent) {
    e.preventDefault()
    const text = question.trim()
    if (!text || chat.busy) return
    setQuestion('')
    await chat.send(text)
  }

  return (
    <div className="grid h-[calc(100svh-6rem)] min-h-[32rem] gap-4 lg:h-[calc(100svh-4rem)] lg:grid-cols-[17rem_1fr]">
      <aside className="card flex min-h-0 flex-col p-3 max-lg:hidden">
        <Link className="btn mb-3" to="/chat?nouveau"><Plus className="h-4 w-4" /> Nouvelle conversation</Link>
        <ul className="space-y-1 overflow-y-auto">
          {(history.data ?? []).map((c) => (
            <li key={c.id} className="group flex items-center gap-1">
              <Link to={`/chat/${c.id}`} title={c.titre ?? ''}
                className={cn('flex-1 truncate rounded-lg px-2 py-1.5 text-sm hover:bg-gold-500/15', conversationId === c.id ? 'bg-gold-500/20 text-gold-300' : 'text-cream-100')}>
                {c.titre || 'Conversation'}
              </Link>
              <button onClick={() => setToDelete(c)} aria-label="Supprimer la conversation" className="btn-icon opacity-0 focus:opacity-100 group-hover:opacity-100"><Trash2 className="h-4 w-4" /></button>
            </li>
          ))}
          {history.data?.length === 0 && <li className="px-2 text-sm text-cream-300">Aucune conversation.</li>}
        </ul>
      </aside>

      <section className="card flex min-h-0 flex-col p-4">
        <div className="mb-2 flex items-center justify-between gap-2 lg:hidden">
          <Link className="btn-ghost" to="/chat?nouveau"><Plus className="h-4 w-4" /> Nouvelle</Link>
          {(history.data ?? []).length > 0 && (
            <select className="input w-auto max-w-[60%]" aria-label="Conversations" value={conversationId ?? ''} onChange={(e) => navigate(e.target.value ? `/chat/${e.target.value}` : '/chat?nouveau')}>
              <option value="">Nouvelle conversation</option>
              {history.data?.map((c) => <option key={c.id} value={c.id}>{c.titre || 'Conversation'}</option>)}
            </select>
          )}
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto pr-1" aria-live="polite">
          {chat.messages.length === 0 && !chat.loading && (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-cream-300">
              <Bot className="h-10 w-10 text-gold-400" aria-hidden />
              <p className="max-w-md">Posez une question : la réponse s’appuie uniquement sur les fichiers des dossiers auxquels vous avez accès. La conversation est mémorisée et retrouvée après une reconnexion.</p>
            </div>
          )}
          {chat.messages.map((m) => (
            <div key={m.id} className={cn('flex gap-2', m.role === 'utilisateur' ? 'justify-end' : 'justify-start')}>
              {m.role === 'assistant' && <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gold-500/20 text-gold-400"><Bot className="h-4 w-4" /></span>}
              <div className={cn('max-w-[85%] rounded-2xl px-4 py-3', m.role === 'utilisateur' ? 'bg-gold-500 text-leaf-950' : 'border border-gold-500/30 bg-leaf-900 text-cream-50')}>
                <p className={cn('whitespace-pre-wrap text-sm leading-relaxed', m.masque && 'italic text-cream-300')}>
                  {m.text || (m.role === 'assistant' && chat.busy ? 'Recherche dans les documents…' : '')}
                </p>
                {m.role === 'assistant' && <Sources message={m} />}
              </div>
              {m.role === 'utilisateur' && <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gold-500/20 text-gold-400"><User className="h-4 w-4" /></span>}
            </div>
          ))}
          <div ref={bottom} />
        </div>

        <div className="mt-3 space-y-2">
          {showOptions && <Options />}
          <ErrorBox message={chat.error} />
          <div className="flex items-center justify-between">
            <button type="button" className="inline-flex items-center gap-1.5 text-xs text-cream-300 hover:text-gold-300" onClick={() => setShowOptions((v) => !v)} aria-expanded={showOptions}><Settings2 className="h-3.5 w-3.5" /> Options</button>
            <ExampleButton onFill={() => setQuestion(exempleQuestion())} />
          </div>
          <form onSubmit={(e) => void submit(e)} className="flex gap-2">
            <input className="input" placeholder="Votre question…" maxLength={2000} value={question} onChange={(e) => setQuestion(e.target.value)} aria-label="Votre question" />
            {chat.busy
              ? <button type="button" className="btn-ghost" onClick={chat.stop}><Square className="h-4 w-4" /> Arrêter</button>
              : <button className="btn" disabled={!question.trim()}><Send className="h-4 w-4" /> Envoyer</button>}
          </form>
        </div>
      </section>

      {toDelete && (
        <ConfirmDialog title="Supprimer la conversation" confirmLabel="Supprimer" onClose={() => setToDelete(null)}
          onConfirm={async () => {
            await deleteConversation(toDelete.id)
            await qc.invalidateQueries({ queryKey: keys.conversations })
            if (conversationId === toDelete.id) navigate('/chat?nouveau', { replace: true })
          }}>
          Supprimer définitivement « {toDelete.titre || 'Conversation'} » ?
        </ConfirmDialog>
      )}
    </div>
  )
}
