// Appels de gestion des documents : liste des métadonnées, ajout, modification, suppression.
import type { DocumentMeta } from '../types/document'
import { api } from './client'

export const listDocuments = (serviceId?: number | null) =>
  api<DocumentMeta[]>(serviceId ? `/documents?service_id=${serviceId}` : '/documents')

export interface AddDocumentInput {
  fichier: File
  titre: string
  serviceId?: number | null
  contientTableaux: boolean
}

export function addDocument(input: AddDocumentInput) {
  const form = new FormData()
  form.append('fichier', input.fichier)
  form.append('titre', input.titre)
  if (input.serviceId) form.append('service_id', String(input.serviceId))
  form.append('contient_tableaux', String(input.contientTableaux))
  return api<DocumentMeta>('/documents', { method: 'POST', form })
}

export interface UpdateDocumentInput {
  titre?: string
  serviceId?: number | null
  fichier?: File | null
  contientTableaux?: boolean
}

export function updateDocument(id: number, input: UpdateDocumentInput) {
  const form = new FormData()
  if (input.titre !== undefined) form.append('titre', input.titre)
  if (input.serviceId) form.append('service_id', String(input.serviceId))
  if (input.fichier) {
    form.append('fichier', input.fichier)
    form.append('contient_tableaux', String(Boolean(input.contientTableaux)))
  }
  return api<DocumentMeta>(`/documents/${id}`, { method: 'PATCH', form })
}

export const deleteDocument = (id: number) => api<void>(`/documents/${id}`, { method: 'DELETE' })
