// Interface de chat : historique des conversations, réponses en streaming, sources citées (avec version et date).
// Mémoire dans une session : obligatoire (la conversation est relue côté serveur) ; la dernière conversation se rouvre
// toute seule après une reconnexion. Deux options personnelles : mémoire entre sessions, dernière version seulement.
import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { deleteConversation, getPreferences, listConversations, setPreferences } from '../../api/chat'
import type { ChatPreferences } from '../../api/chat'
import { errorMessage } from '../../api/client'
import ExampleButton from '../../components/ui/ExampleButton'
import { ErrorBox } from '../../components/ui/Feedback'
import { useChatStream } from '../../hooks/useChatStream'
import type { ChatMessage } from '../../hooks/useChatStream'
import { useLoad } from '../../hooks/useLoad'
import { formatDay } from '../../lib/fichiers'
import { exempleQuestion } from '../../lib/exemples'

function Sources({ message }: { message: ChatMessage }) {
  if (message.sources.length === 0) return null
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-gold-400 hover:text-gold-300">
        Sources ({message.sources.length})
      </summary>
      <ul className="mt-2 space-y-2">
        {message.sources.map((s) => (
          <li key={s.ref} className="rounded-lg border border-gold-500/30 bg-leaf-950/50 p-2.5">
            <p className="font-medium text-gold-300">
              [{s.ref}] {s.titre}
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
  const prefs = useLoad(getPreferences)
  const [error, setError] = useState<string | null>(null)
  const reload = prefs.reload

  async function change(patch: Partial<ChatPreferences>) {
    setError(null)
    try {
      await setPreferences(patch)
      await reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  if (!prefs.data) return <ErrorBox message={prefs.error} />
  return (
    <div className="space-y-1 rounded-lg border border-gold-500/30 p-2.5 text-sm">
      <ErrorBox message={error} />
      <label className="flex items-start gap-2">
        <input type="checkbox" className="mt-0.5 h-4 w-4 accent-gold-500" checked={prefs.data.derniere_version_seulement}
          onChange={(e) => void change({ derniere_version_seulement: e.target.checked })} />
        <span>Dernière version seulement<span className="block text-xs text-cream-300">Ignorer les anciennes versions des fichiers dans les réponses.</span></span>
      </label>
      <label className="flex items-start gap-2">
        <input type="checkbox" className="mt-0.5 h-4 w-4 accent-gold-500" checked={prefs.data.memoire_inter_sessions}
          onChange={(e) => void change({ memoire_inter_sessions: e.target.checked })} />
        <span>Mémoire entre sessions<span className="block text-xs text-cream-300">Retenir le résultat de mes échanges pour enrichir mes prochaines conversations.</span></span>
      </label>
    </div>
  )
}

export default function Chatbot() {
  const chat = useChatStream()
  const [question, setQuestion] = useState('')
  const bottom = useRef<HTMLDivElement>(null)
  const history = useLoad(listConversations)
  const autoOpened = useRef(false)

  // Après une (re)connexion, on rouvre la dernière conversation : l'historique est rechargé depuis le serveur
  const firstConversation = history.data?.[0]?.id ?? null
  const loadConversation = chat.load
  useEffect(() => {
    if (autoOpened.current || history.data === null) return
    autoOpened.current = true
    if (firstConversation !== null) void loadConversation(firstConversation)
  }, [history.data, firstConversation, loadConversation])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat.messages])

  const reloadHistory = history.reload
  const submit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault()
      const text = question.trim()
      if (!text || chat.busy) return
      setQuestion('')
      await chat.send(text, () => void reloadHistory())
    },
    [question, chat, reloadHistory],
  )

  async function remove(id: number) {
    await deleteConversation(id)
    if (chat.conversationId === id) chat.reset()
    await reloadHistory()
  }

  return (
    <div className="grid gap-4 md:grid-cols-[16rem_1fr]">
      <aside className="card flex max-h-[70svh] flex-col p-3">
        <button className="btn mb-3" onClick={chat.reset}>+ Nouvelle conversation</button>
        <ul className="space-y-1 overflow-y-auto">
          {(history.data ?? []).map((c) => (
            <li key={c.id} className="group flex items-center gap-1">
              <button
                onClick={() => void chat.load(c.id)}
                className={`flex-1 truncate rounded-lg px-2 py-1.5 text-left text-sm hover:bg-gold-500/15 ${
                  chat.conversationId === c.id ? 'bg-gold-500/20 text-gold-300' : 'text-cream-100'
                }`}
                title={c.titre ?? ''}
              >
                {c.titre || 'Conversation'}
              </button>
              <button onClick={() => void remove(c.id)} aria-label="Supprimer la conversation" className="px-1 text-cream-300 hover:text-red-300">×</button>
            </li>
          ))}
          {history.data?.length === 0 && <li className="px-2 text-sm text-cream-300">Aucune conversation.</li>}
        </ul>
      </aside>

      <section className="card flex min-h-[60svh] flex-col p-4">
        <div className="flex-1 space-y-4 overflow-y-auto pr-1">
          {chat.messages.length === 0 && (
            <p className="py-16 text-center text-cream-300">
              Posez une question : la réponse s'appuie uniquement sur les fichiers des dossiers auxquels vous avez accès.
              La conversation est mémorisée et retrouvée après une reconnexion.
            </p>
          )}
          {chat.messages.map((m) => (
            <div key={m.id} className={m.role === 'utilisateur' ? 'flex justify-end' : 'flex justify-start'}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                  m.role === 'utilisateur'
                    ? 'bg-gold-500 text-leaf-950'
                    : 'border border-gold-500/30 bg-leaf-900 text-cream-50'
                }`}
              >
                <p className={`whitespace-pre-wrap text-sm leading-relaxed ${m.masque ? 'italic text-cream-300' : ''}`}>
                  {m.text || (m.role === 'assistant' && chat.busy ? 'Recherche dans les documents…' : '')}
                </p>
                {m.role === 'assistant' && <Sources message={m} />}
              </div>
            </div>
          ))}
          <div ref={bottom} />
        </div>

        <div className="mt-3 space-y-2">
          <Options />
          <ErrorBox message={chat.error} />
          <div className="flex justify-end"><ExampleButton onFill={() => setQuestion(exempleQuestion())} /></div>
          <form onSubmit={(e) => void submit(e)} className="flex gap-2">
            <input
              className="input"
              placeholder="Votre question…"
              maxLength={2000}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              aria-label="Votre question"
            />
            {chat.busy ? (
              <button type="button" className="btn-ghost" onClick={chat.stop}>Arrêter</button>
            ) : (
              <button className="btn" disabled={!question.trim()}>Envoyer</button>
            )}
          </form>
        </div>
      </section>
    </div>
  )
}
