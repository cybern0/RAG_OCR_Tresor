import { api } from '../../shared/api/client'

export interface RoleDivision { id: number; division_id: number; code: string; libelle: string; actif: boolean; nb_agents: number; nb_fichiers: number }
export interface DivisionItem { id: number; service_id: number; code: string | null; nom: string; actif: boolean; service_nom: string | null }

export const listDivisions = () => api<DivisionItem[]>('/structure/divisions')
export const rolesDeUser = (userId: number) => api<{ id: number; code: string; libelle: string }[]>(`/users/${userId}/roles`)
export const definirRolesUser = (userId: number, role_ids: number[], motif?: string) =>
  api<{ id: number }[]>(`/users/${userId}/roles`, { method: 'PUT', json: { role_ids, motif } })
export const listRoles = (divisionId: number) => api<RoleDivision[]>(`/divisions/${divisionId}/roles`)
export const creerRole = (divisionId: number, data: { libelle: string; code?: string }) => api<RoleDivision>(`/divisions/${divisionId}/roles`, { method: 'POST', json: data })
export const modifierRole = (divisionId: number, id: number, data: { libelle?: string; actif?: boolean }) =>
  api<RoleDivision>(`/divisions/${divisionId}/roles/${id}`, { method: 'PATCH', json: data })
export const supprimerRole = (divisionId: number, id: number) => api<void>(`/divisions/${divisionId}/roles/${id}`, { method: 'DELETE' })
