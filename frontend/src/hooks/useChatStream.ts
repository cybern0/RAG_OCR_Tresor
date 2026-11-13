// Hook de chat : envoie la question, reçoit la réponse en streaming et garde les messages affichés.
import { useCallback, useRef, useState } from 'react'
import { errorMessage } from '../api/client'
import type { Source } from '../api/chat'
import { getConversation, streamChat } from '../api/chat'

export interface ChatMessage {
  id: string
  role: 'utilisateur' | 'assistant'
  text: string
  sources: Source[]
  masque?: boolean // réponse masquée : accès perdu à l'un des dossiers cités
}

const newId = () => crypto.randomUUID()

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abort = useRef<AbortController | null>(null)

  const send = useCallback(
    async (question: string, onConversationCreated?: () => void) => {
      const assistantId = newId()
      setError(null)
      setBusy(true)
      setMessages((m) => [
        ...m,
        { id: newId(), role: 'utilisateur', text: question, sources: [] },
        { id: assistantId, role: 'assistant', text: '', sources: [] },
      ])
      const patchAssistant = (patch: (msg: ChatMessage) => ChatMessage) =>
        setMessages((all) => all.map((msg) => (msg.id === assistantId ? patch(msg) : msg)))

      const controller = new AbortController()
      abort.current = controller
      try {
        await streamChat(
          question,
          conversationId,
          {
            onMeta: (id) => {
              if (conversationId === null) {
                setConversationId(id)
                onConversationCreated?.()
              }
            },
            onSources: (sources) => patchAssistant((msg) => ({ ...msg, sources })),
            onToken: (token) => patchAssistant((msg) => ({ ...msg, text: msg.text + token })),
            onError: (detail) => setError(detail),
          },
          controller.signal,
        )
      } catch (e) {
        if (!(e instanceof DOMException && e.name === 'AbortError')) setError(errorMessage(e))
      } finally {
        setBusy(false)
        abort.current = null
      }
    },
    [conversationId],
  )

  const stop = useCallback(() => abort.current?.abort(), [])

  const reset = useCallback(() => {
    abort.current?.abort()
    setMessages([])
    setConversationId(null)
    setError(null)
  }, [])

  const load = useCallback(async (id: number) => {
    abort.current?.abort()
    setError(null)
    try {
      const stored = await getConversation(id)
      setConversationId(id)
      setMessages(stored.map((s) => ({ id: newId(), role: s.emetteur, text: s.contenu, sources: s.sources, masque: s.masque })))
    } catch (e) {
      setError(errorMessage(e))
    }
  }, [])

  return { messages, conversationId, busy, error, send, stop, reset, load }
}
