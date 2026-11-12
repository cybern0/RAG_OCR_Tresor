// Hook d'authentification : utilisateur courant, connexion, déconnexion.
// L'état est global (un seul store) pour que tous les composants voient la même session.
import { useSyncExternalStore } from 'react'
import * as authApi from '../api/auth'
import { setUnauthorizedHandler, tokenStore } from '../api/client'
import type { Me } from '../types/user'
import { can } from '../types/user'

interface AuthState {
  status: 'loading' | 'anonymous' | 'authenticated'
  user: Me | null
}

let state: AuthState = { status: tokenStore.get() ? 'loading' : 'anonymous', user: null }
const listeners = new Set<() => void>()

function setState(next: AuthState) {
  state = next
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

const getSnapshot = () => state

// Session expirée ou compte désactivé : retour à l'écran de connexion
setUnauthorizedHandler(() => {
  tokenStore.clear()
  setState({ status: 'anonymous', user: null })
})

// Au chargement de la page, on retrouve l'utilisateur à partir du jeton mémorisé
if (state.status === 'loading') {
  authApi
    .fetchMe()
    .then((user) => setState({ status: 'authenticated', user }))
    .catch(() => {
      tokenStore.clear()
      setState({ status: 'anonymous', user: null })
    })
}

async function login(username: string, password: string): Promise<void> {
  const result = await authApi.login(username, password)
  tokenStore.set(result.access_token)
  setState({ status: 'authenticated', user: result.user })
}

async function logout(): Promise<void> {
  try {
    await authApi.logout()
  } catch {
    /* la déconnexion locale suffit si le serveur est injoignable */
  }
  tokenStore.clear()
  setState({ status: 'anonymous', user: null })
}

export function useAuth() {
  const current = useSyncExternalStore(subscribe, getSnapshot)
  return {
    status: current.status,
    user: current.user,
    can: (permission: string) => can(current.user, permission),
    login,
    logout,
  }
}
