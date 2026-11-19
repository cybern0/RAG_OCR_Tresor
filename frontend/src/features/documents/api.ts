import { api, query, rawFetch } from '../../shared/api/client'
import type { DocumentFilters, DocumentMeta, DocumentPage, FiltresListe, Referentiel, VersionMeta } from './types'

export const listDocuments = (f: DocumentFilters) => api<DocumentPage>(`/documents${query({ ...f })}`)
export const getDocument = (id: number) => api<DocumentMeta>(`/documents/${id}`)
export const getFiltres = () => api<FiltresListe>('/documents/filtres')
export const getReferentiel = () => api<Referentiel>('/classement/referentiel')

export interface AddDocumentInput { fichier: File; titre: string; divisionId: number; contientTableaux: boolean; contientImages: boolean }

export function addDocument(input: AddDocumentInput) {
  const form = new FormData()
  form.append('fichier', input.fichier)
  form.append('titre', input.titre)
  form.append('division_id', String(input.divisionId))
  form.append('contient_tableaux', String(input.contientTableaux))
  form.append('contient_images', String(input.contientImages))
  return api<DocumentMeta>('/documents', { method: 'POST', form })
}

/** Affectation manuelle d'un fichier à des agents de sa division : chef de division ou chef de service. */
export const definirAffectations = (id: number, agent_ids: number[], motif?: string) =>
  api<DocumentMeta>(`/documents/${id}/affectations`, { method: 'PUT', json: { agent_ids, motif } })

export interface UpdateDocumentInput { titre?: string; contientTableaux?: boolean; contientImages?: boolean }

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

/** Relit le fichier déjà stocké d'une version, sans créer de nouvelle version (refusé si aucune case ne change). */
export function reindexVersion(id: number, numero: number, input: { contientTableaux: boolean; contientImages: boolean }) {
  const form = new FormData()
  form.append('contient_tableaux', String(input.contientTableaux))
  form.append('contient_images', String(input.contientImages))
  return api<DocumentMeta>(`/documents/${id}/versions/${numero}/reindexer`, { method: 'POST', form })
}

export const deleteVersion = (id: number, numero: number) => api<void>(`/documents/${id}/versions/${numero}`, { method: 'DELETE' })

export interface ClasserInput {
  ids: number[]
  categorie_id?: number | null
  type_document_id?: number | null
  tags?: string[]
  confidentialite?: string | null
}
export const classerLot = (data: ClasserInput) =>
  api<{ ok: number[]; not_found: number[]; forbidden: number[] }>('/documents/classer-lot', { method: 'POST', json: data })

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

export interface CommentItem { id: number; auteur_nom: string; contenu: string; cree_le: string }
export const listComments = (id: number) => api<CommentItem[]>(`/documents/${id}/commentaires`)
export const addComment = (id: number, contenu: string) => api<CommentItem>(`/documents/${id}/commentaires`, { method: 'POST', json: { contenu } })
