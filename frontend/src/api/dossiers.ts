// Appels de gestion des dossiers (liste pour tous ; création, accès et rôles réservés à l'ADMIN).
import type { AccesDossier, Dossier, RoleDossier } from '../types/dossier'
import { api } from './client'

export const listDossiers = () => api<Dossier[]>('/dossiers')
export const createDossier = (data: { nom: string; description?: string | null }) =>
  api<Dossier>('/dossiers', { method: 'POST', json: data })
export const updateDossier = (id: number, data: { nom?: string; description?: string; archive?: boolean }) =>
  api<Dossier>(`/dossiers/${id}`, { method: 'PATCH', json: data })
export const deleteDossier = (id: number) => api<void>(`/dossiers/${id}`, { method: 'DELETE' })

export const getAcces = (id: number) => api<AccesDossier>(`/dossiers/${id}/acces`)
export const setMembre = (id: number, userId: number, role: RoleDossier) =>
  api<void>(`/dossiers/${id}/membres/${userId}`, { method: 'PUT', json: { role } })
export const removeMembre = (id: number, userId: number) =>
  api<void>(`/dossiers/${id}/membres/${userId}`, { method: 'DELETE' })
export const setServiceAcces = (id: number, serviceId: number, role: RoleDossier) =>
  api<void>(`/dossiers/${id}/services/${serviceId}`, { method: 'PUT', json: { role } })
export const removeServiceAcces = (id: number, serviceId: number) =>
  api<void>(`/dossiers/${id}/services/${serviceId}`, { method: 'DELETE' })
