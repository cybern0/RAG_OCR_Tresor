import { useQuery } from '@tanstack/react-query'
import { errorMessage } from '../../shared/api/client'
import * as api from './api'

export const dossierKeys = {
  all: ['dossiers'] as const,
  one: (id: number) => ['dossiers', id] as const,
  acces: (id: number) => ['dossiers', id, 'acces'] as const,
}

export const useDossiers = () => useQuery({ queryKey: dossierKeys.all, queryFn: api.listDossiers })
export const useDossier = (id: number) => useQuery({ queryKey: dossierKeys.one(id), queryFn: () => api.getDossier(id), enabled: Number.isFinite(id) })
export const useAcces = (id: number) => useQuery({ queryKey: dossierKeys.acces(id), queryFn: () => api.getAcces(id) })

export const queryError = (q: { error: unknown }) => (q.error ? errorMessage(q.error) : null)
