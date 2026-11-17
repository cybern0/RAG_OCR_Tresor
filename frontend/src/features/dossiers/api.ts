import { api, query } from '../../shared/api/client'
import type { Dossier, DossierDetail } from './types'

export const listDossiers = (params: { division_id?: number } = {}) => api<Dossier[]>(`/dossiers${query(params)}`)
export const getDossier = (id: number) => api<DossierDetail>(`/dossiers/${id}`)
export const createDossier = (data: { nom: string; description?: string | null; parent_id?: number | null; division_id?: number | null }) =>
  api<Dossier>('/dossiers', { method: 'POST', json: data })
export const updateDossier = (id: number, data: { nom?: string; description?: string; archive?: boolean; parent_id?: number | null }) =>
  api<Dossier>(`/dossiers/${id}`, { method: 'PATCH', json: data })
export const deleteDossier = (id: number) => api<void>(`/dossiers/${id}`, { method: 'DELETE' })
