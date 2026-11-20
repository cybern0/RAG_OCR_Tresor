import { api, query } from '../../shared/api/client'
import type { AgentBrief, UserCreate, UserOut, UserUpdate } from '../auth/types'
import type { Agent, AuditRow, CategoryItem, DashboardStats, Direction, Health, RuleItem, ServiceItem, SimulationResult, TagItem, TypeItem } from './types'

// --- utilisateurs
export const listUsers = () => api<UserOut[]>('/users')
// Agents que l'appelant peut affecter (périmètre du chef de service / de division) ; pourUser ajoute l'agent actuel du compte.
export const listAgentsDisponibles = (pourUser?: number) => api<AgentBrief[]>(pourUser ? `/users/agents-disponibles?pour_user=${pourUser}` : '/users/agents-disponibles')
export const getUser = (id: number) => api<UserOut>(`/users/${id}`)
export const createUser = (data: UserCreate) => api<UserOut>('/users', { method: 'POST', json: data })
export const updateUser = (id: number, data: UserUpdate) => api<UserOut>(`/users/${id}`, { method: 'PATCH', json: data })

// --- structure
export const listDirections = () => api<Direction[]>('/structure/directions')
export const createDirection = (data: { code: string; nom: string }) => api<Direction>('/structure/directions', { method: 'POST', json: data })
export const updateDirection = (id: number, data: { nom?: string; actif?: boolean }) => api<Direction>(`/structure/directions/${id}`, { method: 'PATCH', json: data })
export const listServices = () => api<ServiceItem[]>('/structure/services')
export const createService = (data: { direction_id: number; code: string; nom: string; site?: string | null }) => api<ServiceItem>('/structure/services', { method: 'POST', json: data })
export const updateService = (id: number, data: { nom?: string; actif?: boolean; direction_id?: number }) => api<ServiceItem>(`/structure/services/${id}`, { method: 'PATCH', json: data })
export const listDivisionsAdmin = () => api<{ id: number; service_id: number; nom: string; actif: boolean; code: string | null; service_nom: string | null; direction_nom: string | null }[]>('/structure/divisions')
export const createDivision = (data: { service_id: number; code?: string | null; nom: string }) => api<{ id: number; service_id: number; nom: string; actif: boolean; code: string | null; service_nom: string | null; direction_nom: string | null }>('/structure/divisions', { method: 'POST', json: data })
export const updateDivision = (id: number, data: { nom?: string; actif?: boolean; service_id?: number; code?: string | null }) => api<{ id: number; service_id: number; nom: string; actif: boolean; code: string | null; service_nom: string | null; direction_nom: string | null }>(`/structure/divisions/${id}`, { method: 'PATCH', json: data })
export const listAgents = () => api<Agent[]>('/structure/agents')
export const createAgent = (data: { matricule: string; nom: string; prenom: string; fonction?: string | null; email?: string | null; service_id: number; division_id?: number | null; titre?: 'CHEF_DIVISION' | 'CHEF_SERVICE' | null }) => api<Agent>('/structure/agents', { method: 'POST', json: data })
export const updateAgent = (id: number, data: { nom?: string; prenom?: string; fonction?: string | null; email?: string | null; service_id?: number; division_id?: number | null; titre?: 'CHEF_DIVISION' | 'CHEF_SERVICE' | null; actif?: boolean }) => api<Agent>(`/structure/agents/${id}`, { method: 'PATCH', json: data })
// Suppressions gardées : le backend répond 409 tant que des éléments dépendent encore de l'objet.
export const deleteDirection = (id: number) => api<void>(`/structure/directions/${id}`, { method: 'DELETE' })
export const deleteService = (id: number) => api<void>(`/structure/services/${id}`, { method: 'DELETE' })
export const deleteDivision = (id: number) => api<void>(`/structure/divisions/${id}`, { method: 'DELETE' })
export const deleteAgent = (id: number) => api<void>(`/structure/agents/${id}`, { method: 'DELETE' })

// --- audit, statistiques, santé
export const listAudit = (limit = 200, offset = 0) => api<AuditRow[]>(`/audit${query({ limit, offset })}`)
export const fetchStats = () => api<DashboardStats>('/classement/stats')
export const fetchHealth = () => api<Health>('/health', { anonymous: true })

// --- classement
export const listCategories = () => api<CategoryItem[]>('/classement/categories')
export const createCategory = (d: { nom: string; parent_id?: number | null; couleur?: string | null; ordre?: number }) => api<CategoryItem>('/classement/categories', { method: 'POST', json: d })
export const updateCategory = (id: number, d: Partial<Omit<CategoryItem, 'id'>>) => api<CategoryItem>(`/classement/categories/${id}`, { method: 'PATCH', json: d })
export const deleteCategory = (id: number) => api<unknown>(`/classement/categories/${id}`, { method: 'DELETE' })
export const listTypes = () => api<TypeItem[]>('/classement/types')
export const createType = (d: { nom: string }) => api<TypeItem>('/classement/types', { method: 'POST', json: d })
export const updateType = (id: number, d: Partial<Omit<TypeItem, 'id'>>) => api<TypeItem>(`/classement/types/${id}`, { method: 'PATCH', json: d })
export const deleteType = (id: number) => api<unknown>(`/classement/types/${id}`, { method: 'DELETE' })
export const listTags = () => api<TagItem[]>('/classement/tags')
export const createTag = (d: { nom: string }) => api<TagItem>('/classement/tags', { method: 'POST', json: d })
export const deleteTag = (id: number) => api<unknown>(`/classement/tags/${id}`, { method: 'DELETE' })
export const listRules = () => api<RuleItem[]>('/classement/regles')
export type RuleInput = { nom: string; priorite?: number; actif?: boolean; critere?: unknown; categorie_id?: number | null; type_document_id?: number | null; tags?: string[]; confidentialite?: string | null }
export const createRule = (d: RuleInput) => api<RuleItem>('/classement/regles', { method: 'POST', json: d })
export const updateRule = (id: number, d: Partial<RuleInput>) => api<RuleItem>(`/classement/regles/${id}`, { method: 'PATCH', json: d })
export const deleteRule = (id: number) => api<unknown>(`/classement/regles/${id}`, { method: 'DELETE' })
export const simulate = (d: { nom_fichier?: string; extension?: string; texte?: string }) => api<SimulationResult>('/classement/simuler', { method: 'POST', json: d })

export const transfererChef = (unitId: number, agentId: number | null, motif?: string) =>
  api<unknown>(`/structure/divisions/${unitId}/chef`, { method: 'PUT', json: { agent_id: agentId, motif } })
export const transfererChefService = (serviceId: number, agentId: number | null, motif?: string) =>
  api<unknown>(`/structure/services/${serviceId}/chef`, { method: 'PUT', json: { agent_id: agentId, motif } })
