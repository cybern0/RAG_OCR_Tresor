import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from './api'
import { isIndexing } from './types'
import type { DocumentFilters, DocumentMeta, Statut } from './types'

export const docKeys = {
  lists: ['documents', 'list'] as const,
  list: (f: DocumentFilters) => ['documents', 'list', f] as const,
  one: (id: number) => ['documents', 'one', id] as const,
  versions: (id: number) => ['documents', 'one', id, 'versions'] as const,
  comments: (id: number) => ['documents', 'one', id, 'comments'] as const,
  referentiel: ['referentiel'] as const,
}

const POLL_MS = 3000

/** Liste paginée ; tant qu'une version s'indexe, la liste se rafraîchit toute seule. */
export const useDocuments = (filters: DocumentFilters) =>
  useQuery({
    queryKey: docKeys.list(filters),
    queryFn: () => api.listDocuments(filters),
    placeholderData: keepPreviousData,
    refetchInterval: (q) => (q.state.data?.items.some((d) => isIndexing(d.version.statut)) ? POLL_MS : false),
  })

export const useDocument = (id: number) =>
  useQuery({
    queryKey: docKeys.one(id),
    queryFn: () => api.getDocument(id),
    refetchInterval: (q) => (q.state.data && isIndexing(q.state.data.version.statut as Statut) ? POLL_MS : false),
  })

export const useVersions = (id: number) =>
  useQuery({
    queryKey: docKeys.versions(id),
    queryFn: () => api.listVersions(id),
    refetchInterval: (q) => (q.state.data?.some((v) => isIndexing(v.statut)) ? POLL_MS : false),
  })

export const useReferentiel = () => useQuery({ queryKey: docKeys.referentiel, queryFn: api.getReferentiel, staleTime: 60_000 })

export const useComments = (id: number, enabled: boolean) => useQuery({ queryKey: docKeys.comments(id), queryFn: () => api.listComments(id), enabled })

/** Après une écriture : les listes de fichiers, la fiche et les compteurs des dossiers sont à relire. */
export function useRefreshDocuments() {
  const qc = useQueryClient()
  return () => Promise.all([qc.invalidateQueries({ queryKey: ['documents'] }), qc.invalidateQueries({ queryKey: ['dossiers'] })])
}

export function useDocumentMutations() {
  const refresh = useRefreshDocuments()
  const settle = { onSuccess: () => refresh() }
  return {
    add: useMutation({ mutationFn: api.addDocument, ...settle }),
    update: useMutation({ mutationFn: (v: { id: number } & api.UpdateDocumentInput) => api.updateDocument(v.id, v), ...settle }),
    addVersion: useMutation({ mutationFn: (v: { id: number; fichier: File; contientTableaux: boolean; contientImages: boolean }) => api.addVersion(v.id, v), ...settle }),
    remove: useMutation({ mutationFn: (id: number) => api.deleteDocument(id), ...settle }),
    purge: useMutation({ mutationFn: (id: number) => api.deleteDocument(id, true), ...settle }),
    restore: useMutation({ mutationFn: api.restoreDocument, ...settle }),
    removeVersion: useMutation({ mutationFn: (v: { id: number; numero: number }) => api.deleteVersion(v.id, v.numero), ...settle }),
    classer: useMutation({ mutationFn: api.classerLot, ...settle }),
  }
}

export type { DocumentMeta }
