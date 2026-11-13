// Client HTTP de base : URL de l'API, en-tête d'authentification, gestion des erreurs.

const API_URL: string = import.meta.env.VITE_API_URL ?? '/api'
const TOKEN_KEY = 'rag_tresor_token'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export const tokenStore = {
  get: (): string | null => {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set: (token: string): void => {
    try {
      localStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* stockage indisponible : la session durera le temps de la page */
    }
  },
  clear: (): void => {
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* rien à faire */
    }
  },
}

let onUnauthorized: (() => void) | null = null

/** Appelé quand le serveur répond 401 sur une requête authentifiée (session expirée, compte désactivé). */
export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

function detailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : ''))
      .filter(Boolean)
    if (messages.length) return messages.join(' ; ').replace(/Value error, /g, '')
  }
  return fallback
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof DOMException && error.name === 'AbortError') return 'Opération annulée.'
  return 'Le serveur est injoignable. Vérifier que le backend est démarré.'
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  json?: unknown
  form?: FormData
  signal?: AbortSignal
  /** true pour la connexion : un 401 y signifie « identifiants incorrects », pas « session expirée » */
  anonymous?: boolean
}

export function buildHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = tokenStore.get()
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

export async function rawFetch(path: string, options: RequestOptions = {}): Promise<Response> {
  const headers = options.json !== undefined ? buildHeaders({ 'Content-Type': 'application/json' }) : buildHeaders()
  const response = await fetch(`${API_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.form ?? (options.json !== undefined ? JSON.stringify(options.json) : undefined),
    signal: options.signal,
  })
  if (!response.ok) {
    if (response.status === 401 && !options.anonymous) onUnauthorized?.()
    let detail: unknown
    try {
      detail = (await response.json()).detail
    } catch {
      /* corps non JSON */
    }
    throw new ApiError(response.status, detailToMessage(detail, `Erreur ${response.status}`))
  }
  return response
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await rawFetch(path, options)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
