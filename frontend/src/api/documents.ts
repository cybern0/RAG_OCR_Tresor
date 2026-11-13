// Appels de gestion des fichiers : liste, ajout, nouvelle version, modification, suppression, aperçu et téléchargement.
import type { DocumentMeta, VersionMeta } from '../types/document'
import { api, rawFetch } from './client'

export const listDocuments = (dossierId?: number | null) =>
  api<DocumentMeta[]>(dossierId ? `/documents?dossier_id=${dossierId}` : '/documents')

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

export const deleteDocument = (id: number) => api<void>(`/documents/${id}`, { method: 'DELETE' })

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
