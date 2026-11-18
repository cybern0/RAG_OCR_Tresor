// Hook de chat : envoie la question, reçoit la réponse en streaming et affiche les messages.
// La conversation affichée est pilotée par l'URL (/chat/:conversationId). L'historique d'une conversation existante
// est relu côté serveur ; les messages échangés pendant la session s'y ajoutent (« live »). Une conversation créée par
// l'envoi est déjà affichée : elle n'est pas relue (sinon doublons) et l'URL est mise à jour via onCreated.
import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { errorMessage } from '../../shared/api/client'
import { getConversation, streamChat } from './api'
import type { Source } from './api'

export interface ChatMessage {
  id: string
  role: 'utilisateur' | 'assistant'
  text: string
  sources: Source[]
  masque?: boolean // réponse masquée : accès perdu à l'un des fichiers cités
}

export function useChatStream(conversationId: number | null, onCreated: (id: number) => void) {
  const [live, setLive] = useState<ChatMessage[]>([])
  const [scope, setScope] = useState<number | null>(conversationId) // conversation à laquelle « live » appartient
  const [ownId, setOwnId] = useState<number | null>(null) // conversation créée par ce flux
  const [busy, setBusy] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)
  const abort = useRef<AbortController | null>(null)
  const ownIdRef = useRef<number | null>(null)

  // Changement de conversation : on repart de zéro (sauf si c'est celle que ce flux vient de créer)
  if (scope !== conversationId) {
    setScope(conversationId)
    if (conversationId === null || conversationId !== ownId) {
      setLive([])
      setOwnId(null)
      setStreamError(null)
      setBusy(false)
    }
  }

  // Quitter une conversation interrompt son flux en cours (sauf celle que ce flux vient de créer)
  useEffect(() => {
    if (conversationId !== null && conversationId === ownIdRef.current) return
    ownIdRef.current = null
    abort.current?.abort()
  }, [conversationId])

  const isOwn = conversationId !== null && conversationId === ownId
  const stored = useQuery({
    queryKey: ['chat', 'conversation', conversationId],
    queryFn: () => getConversation(conversationId!),
    enabled: conversationId !== null && !isOwn,
    staleTime: 0,
    gcTime: 0,
  })

  const messages = useMemo<ChatMessage[]>(() => {
    const history = isOwn ? [] : (stored.data ?? []).map((s): ChatMessage => ({ id: `s${s.id}`, role: s.emetteur, text: s.contenu, sources: s.sources, masque: s.masque }))
    return [...history, ...live]
  }, [stored.data, live, isOwn])

  const send = useCallback(async (question: string) => {
    const assistantId = crypto.randomUUID()
    setStreamError(null)
    setBusy(true)
    setLive((m) => [...m, { id: crypto.randomUUID(), role: 'utilisateur', text: question, sources: [] }, { id: assistantId, role: 'assistant', text: '', sources: [] }])
    const patch = (fn: (msg: ChatMessage) => ChatMessage) => setLive((all) => all.map((msg) => (msg.id === assistantId ? fn(msg) : msg)))

    const controller = new AbortController()
    abort.current = controller
    try {
      await streamChat(question, conversationId, {
        onMeta: (id) => { if (conversationId === null) { ownIdRef.current = id; setOwnId(id); onCreated(id) } },
        onSources: (sources) => patch((msg) => ({ ...msg, sources })),
        onToken: (token) => patch((msg) => ({ ...msg, text: msg.text + token })),
        onError: (detail) => setStreamError(detail),
      }, controller.signal)
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) setStreamError(errorMessage(e))
    } finally {
      if (abort.current === controller) { abort.current = null; setBusy(false) }
    }
  }, [conversationId, onCreated])

  const stop = useCallback(() => abort.current?.abort(), [])
  const error = streamError ?? (stored.error ? errorMessage(stored.error) : null)
  return { messages, busy, loading: stored.isPending && conversationId !== null && !isOwn, error, send, stop }
}
