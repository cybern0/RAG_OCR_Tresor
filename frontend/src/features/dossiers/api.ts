import { api, query } from '../../shared/api/client'
import type { Dossier } from './types'

export const listDossiers = (params: { division_id?: number } = {}) => api<Dossier[]>(`/dossiers${query(params)}`)
export const getDossier = (id: number) => api<Dossier>(`/dossiers/${id}`)
// Pas de création : les dossiers sont posés automatiquement par le backend à la création de la division.
export const updateDossier = (id: number, data: { nom?: string; description?: string; archive?: boolean }) =>
  api<Dossier>(`/dossiers/${id}`, { method: 'PATCH', json: data })
export const deleteDossier = (id: number) => api<void>(`/dossiers/${id}`, { method: 'DELETE' })
