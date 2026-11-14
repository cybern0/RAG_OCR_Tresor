import { api } from '../../shared/api/client'
import type { Me } from './types'

interface TokenOut { access_token: string; expires_in: number; user: Me }

export const login = (nom_utilisateur: string, mot_de_passe: string) =>
  api<TokenOut>('/auth/login', { method: 'POST', json: { nom_utilisateur, mot_de_passe }, anonymous: true })
export const logout = () => api<void>('/auth/logout', { method: 'POST' })
export const fetchMe = () => api<Me>('/auth/me')
