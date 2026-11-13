// Appels de gestion des fichiers : liste, ajout, nouvelle version, modification, suppression, aperçu et téléchargement.
import type { DocumentMeta, VersionMeta } from '../types/document'
import { api, rawFetch } from './client'

export const listDocuments = (dossierId?: number | null, corbeille = false) => {
  const params = new URLSearchParams()
  if (dossierId) params.set('dossier_id', String(dossierId))
  if (corbeille) params.set('corbeille', 'true')
  const qs = params.toString()
  return api<DocumentMeta[]>(qs ? `/documents?${qs}` : '/documents')
}

export interface AddDocumentInput {
  fichier: File
  titre: string
  dossierId: number
  contientTableaux: boolean
  contientImages: boolean
}

export function addDocument(input: AddDocumentInput) {
  const form = new FormData()
  form.append('fichier', input.fichier)
  form.append('titre', input.titre)
  form.append('dossier_id', String(input.dossierId))
  form.append('contient_tableaux', String(input.contientTableaux))
  form.append('contient_images', String(input.contientImages))
  return api<DocumentMeta>('/documents', { method: 'POST', form })
}

export interface UpdateDocumentInput {
  titre?: string
  contientTableaux?: boolean
  contientImages?: boolean
}

export function updateDocument(id: number, input: UpdateDocumentInput) {
  const form = new FormData()
  if (input.titre !== undefined) form.append('titre', input.titre)
  if (input.contientTableaux !== undefined) form.append('contient_tableaux', String(input.contientTableaux))
  if (input.contientImages !== undefined) form.append('contient_images', String(input.contientImages))
  return api<DocumentMeta>(`/documents/${id}`, { method: 'PATCH', form })
}

export const deleteDocument = (id: number, force = false) => api<void>(`/documents/${id}${force ? '?force=true' : ''}`, { method: 'DELETE' })
export const restoreDocument = (id: number) => api<void>(`/documents/${id}/restore`, { method: 'POST' })

export const listVersions = (id: number) => api<VersionMeta[]>(`/documents/${id}/versions`)

export function addVersion(id: number, input: { fichier: File; contientTableaux: boolean; contientImages: boolean }) {
  const form = new FormData()
  form.append('fichier', input.fichier)
  form.append('contient_tableaux', String(input.contientTableaux))
  form.append('contient_images', String(input.contientImages))
  return api<DocumentMeta>(`/documents/${id}/versions`, { method: 'POST', form })
}

export const deleteVersion = (id: number, numero: number) =>
  api<void>(`/documents/${id}/versions/${numero}`, { method: 'DELETE' })

/** Le contenu passe par l'API (jeton d'authentification) : on récupère un Blob, jamais une URL publique. */
export async function fetchPreview(id: number, numero: number): Promise<Blob> {
  return (await rawFetch(`/documents/${id}/versions/${numero}/apercu`)).blob()
}

export async function downloadVersion(id: number, numero: number, nomFichier: string): Promise<void> {
  const blob = await (await rawFetch(`/documents/${id}/versions/${numero}/telecharger`)).blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = nomFichier
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

export interface DocumentShareLink {
  id: number
  document_id: number
  role: string
  est_anonyme: boolean
  expire_le: string | null
  token_hash: string | null
  token: string | null
  cree_le: string
}

export interface AccessRequestItem {
  id: number
  subject_type: string
  subject_id: number
  requested_by: number
  requested_role: string
  message: string
  status: string
  created_at: string
}

export const listDocumentShares = (documentId: number) =>
  api<DocumentShareLink[]>(`/partage/documents/${documentId}/partages`)

export const createDocumentLinkShare = (documentId: number, data: { role?: string; expire_le?: string | null; est_anonyme?: boolean; token?: string | null }) =>
  api<DocumentShareLink>(`/partage/documents/${documentId}/liens`, { method: 'POST', json: data })

export const listAccessRequests = (filters?: { subject_type?: string; subject_id?: number; status?: string }) => {
  const params = new URLSearchParams()
  if (filters?.subject_type) params.set('subject_type', filters.subject_type)
  if (filters?.subject_id) params.set('subject_id', String(filters.subject_id))
  if (filters?.status) params.set('status', filters.status)
  const qs = params.toString()
  return api<AccessRequestItem[]>(`/partage/demandes-acces${qs ? `?${qs}` : ''}`)
}

export const resolveAccessRequest = (
  requestId: number,
  data: { decision: 'accepted' | 'rejected'; granted_role?: string | null; message?: string | null },
) => api<AccessRequestItem>(`/partage/demandes-acces/${requestId}`, { method: 'PATCH', json: data })
