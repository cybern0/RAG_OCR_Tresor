// Appels d'authentification : connexion, déconnexion, utilisateur courant.
import type { Me } from '../types/user'
import { api } from './client'

interface TokenOut {
  access_token: string
  expires_in: number
  user: Me
}

export const login = (nom_utilisateur: string, mot_de_passe: string) =>
  api<TokenOut>('/auth/login', { method: 'POST', json: { nom_utilisateur, mot_de_passe }, anonymous: true })

export const logout = () => api<void>('/auth/logout', { method: 'POST' })

export const fetchMe = () => api<Me>('/auth/me')
