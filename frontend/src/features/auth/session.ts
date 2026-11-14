// Session : un seul store global (utilisateur courant) lu par toute l'application via useAuth().
// Le jeton reste dans le navigateur ; un 401 du serveur (session expirée, compte désactivé) ramène à la connexion.
import { useSyncExternalStore } from 'react'
import { setUnauthorizedHandler, tokenStore } from '../../shared/api/client'
import * as authApi from './api'
import { hasPermission } from './types'
import type { Me } from './types'

interface AuthState { status: 'loading' | 'anonymous' | 'authenticated'; user: Me | null }

let state: AuthState = { status: tokenStore.get() ? 'loading' : 'anonymous', user: null }
const listeners = new Set<() => void>()
let onSignOut: (() => void) | null = null

function setState(next: AuthState) {
  state = next
  listeners.forEach((l) => l())
}

/** Appelé quand la session se termine (déconnexion, expiration) : sert à vider le cache des requêtes. */
export function setSignOutHandler(handler: () => void) { onSignOut = handler }

function endSession() {
  tokenStore.clear()
  setState({ status: 'anonymous', user: null })
  onSignOut?.()
}

setUnauthorizedHandler(endSession)

if (state.status === 'loading') {
  authApi.fetchMe().then((user) => setState({ status: 'authenticated', user })).catch(endSession)
}

export async function signIn(username: string, password: string): Promise<void> {
  const result = await authApi.login(username, password)
  tokenStore.set(result.access_token)
  setState({ status: 'authenticated', user: result.user })
}

export async function signOut(): Promise<void> {
  try { await authApi.logout() } catch { /* la déconnexion locale suffit si le serveur est injoignable */ }
  endSession()
}

const subscribe = (l: () => void) => { listeners.add(l); return () => { listeners.delete(l) } }

export function useAuth() {
  const current = useSyncExternalStore(subscribe, () => state)
  return {
    status: current.status,
    user: current.user,
    can: (permission: string) => hasPermission(current.user, permission),
    canAny: (...permissions: string[]) => permissions.some((p) => hasPermission(current.user, p)),
  }
}
