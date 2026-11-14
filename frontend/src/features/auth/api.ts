import { api } from '../../shared/api/client'
import type { Me } from './types'

export interface TokenOut { access_token: string; expires_in: number; user: Me }

export const login = (nom_utilisateur: string, mot_de_passe: string) =>
  api<TokenOut>('/auth/login', { method: 'POST', json: { nom_utilisateur, mot_de_passe }, anonymous: true })
export const logout = () => api<void>('/auth/logout', { method: 'POST' })
export const fetchMe = () => api<Me>('/auth/me')

export interface ProfileInput { nom_utilisateur?: string; ancien_mot_de_passe?: string; nouveau_mot_de_passe?: string; confirmation_mot_de_passe?: string }
/** Modifie son propre profil ; renvoie un nouveau jeton (les jetons sont liés au mot de passe). */
export const updateProfile = (data: ProfileInput) => api<TokenOut>('/auth/me', { method: 'PATCH', json: data })
