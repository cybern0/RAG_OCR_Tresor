// Appels du chat : question en streaming (SSE) et historique des conversations.
import { api, rawFetch } from './client'

export interface Source {
  ref: number
  document_id: number
  titre: string
  page: number | null
  extrait: string
}

export interface ConversationItem {
  id: number
  titre: string | null
  cree_le: string
}

export interface StoredMessage {
  id: number
  emetteur: 'utilisateur' | 'assistant'
  contenu: string
  sources: Source[]
  cree_le: string
}

export interface StreamHandlers {
  onMeta: (conversationId: number) => void
  onSources: (sources: Source[]) => void
  onToken: (token: string) => void
  onError: (detail: string) => void
}

/** Envoie la question et lit la réponse au fil de l'eau (événements meta, sources, token, done, error). */
export async function streamChat(
  question: string,
  conversationId: number | null,
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  const response = await rawFetch('/chat', {
    method: 'POST',
    json: { question, conversation_id: conversationId },
    signal,
  })
  if (!response.body) throw new Error('Flux indisponible')
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''

  const dispatch = (block: string) => {
    const lines = block.split('\n')
    const event = lines.find((l) => l.startsWith('event: '))?.slice(7)
    const data = lines.find((l) => l.startsWith('data: '))?.slice(6)
    if (!event || data === undefined) return
    const payload = JSON.parse(data)
    if (event === 'meta') handlers.onMeta(payload.conversation_id)
    else if (event === 'sources') handlers.onSources(payload)
    else if (event === 'token') handlers.onToken(payload.t)
    else if (event === 'error') handlers.onError(payload.detail)
  }

  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let sep = buffer.indexOf('\n\n')
    while (sep !== -1) {
      dispatch(buffer.slice(0, sep))
      buffer = buffer.slice(sep + 2)
      sep = buffer.indexOf('\n\n')
    }
  }
}

export const listConversations = () => api<ConversationItem[]>('/chat/conversations')
export const getConversation = (id: number) => api<StoredMessage[]>(`/chat/conversations/${id}`)
export const deleteConversation = (id: number) => api<void>(`/chat/conversations/${id}`, { method: 'DELETE' })
