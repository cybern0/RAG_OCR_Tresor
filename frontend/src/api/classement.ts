import { api } from './client'

export interface DashboardStatItem {
  value?: number
  total?: number
  categorie_id?: number
  type_document_id?: number
  service_id?: number
  direction_id?: number
}

export interface DashboardStats {
  total_documents: number
  actifs: number
  corbeille: number
  statut: Record<string, number>
  par_categorie: Array<{ categorie_id: number; total: number }>
  par_type: Array<{ type_document_id: number; total: number }>
  par_confidentialite: Record<string, number>
  par_extension: Record<string, number>
  par_service: Array<{ service_id: number; total: number }>
  par_direction: Array<{ direction_id: number; total: number }>
}

export interface CategoryItem {
  id: number
  parent_id: number | null
  nom: string
  couleur: string | null
  ordre: number
  actif: boolean
}

export interface TypeItem {
  id: number
  nom: string
  actif: boolean
}

export interface TagItem {
  id: number
  nom: string
}

export interface RuleItem {
  id: number
  nom: string
  priorite: number
  actif: boolean
  critere: Record<string, unknown>
  categorie_id: number | null
  type_document_id: number | null
  tags: string[]
  confidentialite: string | null
  cree_le: string
  modifie_le: string
}

export interface SimulationInput {
  nom_fichier?: string
  extension?: string
  dossier_id?: number
  service_createur_id?: number | null
  texte?: string
  taille_octets?: number
  nb_pages?: number
  ocr_utilise?: boolean
  classement_source?: string
}

export interface SimulationResult {
  categorie_id: number | null
  type_document_id: number | null
  tags: string[]
  confidentialite: string | null
}

export const fetchDashboardStats = () => api<DashboardStats>('/classement/stats')

export const listCategories = () => api<CategoryItem[]>('/classement/categories')
export const createCategory = (payload: { nom: string; parent_id?: number | null; couleur?: string | null; ordre?: number; actif?: boolean }) =>
  api<CategoryItem>('/classement/categories', { method: 'POST', json: payload })
export const updateCategory = (id: number, payload: Partial<{ nom: string; parent_id: number | null; couleur: string | null; ordre: number; actif: boolean }>) =>
  api<CategoryItem>(`/classement/categories/${id}`, { method: 'PATCH', json: payload })
export const deleteCategory = (id: number) => api<{ ok: boolean; id: number }>(`/classement/categories/${id}`, { method: 'DELETE' })

export const listTypes = () => api<TypeItem[]>('/classement/types')
export const createType = (payload: { nom: string; actif?: boolean }) =>
  api<TypeItem>('/classement/types', { method: 'POST', json: payload })
export const updateType = (id: number, payload: Partial<{ nom: string; actif: boolean }>) =>
  api<TypeItem>(`/classement/types/${id}`, { method: 'PATCH', json: payload })
export const deleteType = (id: number) => api<{ ok: boolean; id: number }>(`/classement/types/${id}`, { method: 'DELETE' })

export const listTags = () => api<TagItem[]>('/classement/tags')
export const createTag = (payload: { nom: string }) => api<TagItem>('/classement/tags', { method: 'POST', json: payload })
export const updateTag = (id: number, payload: Partial<{ nom: string }>) => api<TagItem>(`/classement/tags/${id}`, { method: 'PATCH', json: payload })
export const deleteTag = (id: number) => api<{ ok: boolean; id: number }>(`/classement/tags/${id}`, { method: 'DELETE' })

export const listRules = () => api<RuleItem[]>('/classement/regles')
export const createRule = (payload: {
  nom: string
  priorite?: number
  actif?: boolean
  critere?: Record<string, unknown>
  categorie_id?: number | null
  type_document_id?: number | null
  tags?: string[]
  confidentialite?: string | null
}) => api<RuleItem>('/classement/regles', { method: 'POST', json: payload })
export const updateRule = (id: number, payload: Partial<{
  nom: string
  priorite: number
  actif: boolean
  critere: Record<string, unknown>
  categorie_id: number | null
  type_document_id: number | null
  tags: string[]
  confidentialite: string | null
}>) => api<RuleItem>(`/classement/regles/${id}`, { method: 'PATCH', json: payload })
export const deleteRule = (id: number) => api<{ ok: boolean; id: number }>(`/classement/regles/${id}`, { method: 'DELETE' })

export const simulateClassification = (payload: SimulationInput) =>
  api<SimulationResult>('/classement/simuler', { method: 'POST', json: payload })
