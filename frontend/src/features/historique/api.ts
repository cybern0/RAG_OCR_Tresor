import { api, query } from '../../shared/api/client'

export interface Evenement {
  id: number; rang: number | null; acteur_nom: string | null; cible_type: string; cible_id: number | null; action: string
  avant: string | null; apres: string | null; motif: string | null; date_action: string
}
export interface PageHistorique { total: number; items: Evenement[] }
export interface Verification { ok: boolean; total: number; premier_rang_invalide: number | null }

export const listHistorique = (p: { cible_type?: string; action?: string; limit: number; offset: number }) => api<PageHistorique>(`/historique${query(p)}`)
export const verifierHistorique = () => api<Verification>('/historique/verification')
