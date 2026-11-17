import { api } from '../../shared/api/client'

export type StatutDemande = 'en_attente' | 'acceptee' | 'refusee' | 'annulee'
export interface Demande {
  id: number; type_demande: 'role' | 'fichier'; statut: StatutDemande; demandeur_user_id: number; demandeur_nom: string
  division_id: number; division_nom: string; cible_id: number | null; cible_libelle: string; motif: string
  duree_heures: number | null; reponse: string | null; decisionnaire_nom: string | null
  date_creation: string; date_decision: string | null; peut_decider: boolean; peut_annuler: boolean
}
export interface DemandeIn { type_demande: 'role' | 'fichier'; cible_id: number; motif: string; duree_heures?: number }
export interface DecisionIn { accepter: boolean; reponse?: string; duree_heures?: number }

export const listDemandes = () => api<Demande[]>('/demandes')
export const creerDemande = (data: DemandeIn) => api<Demande>('/demandes', { method: 'POST', json: data })
export const decider = (id: number, data: DecisionIn) => api<Demande>(`/demandes/${id}/decision`, { method: 'POST', json: data })
export const annuler = (id: number) => api<Demande>(`/demandes/${id}/annuler`, { method: 'POST' })
