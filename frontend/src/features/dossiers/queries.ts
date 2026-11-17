import { useQuery } from '@tanstack/react-query'
import { errorMessage } from '../../shared/api/client'
import * as api from './api'

export const dossierKeys = {
  all: ['dossiers'] as const,
  one: (id: number) => ['dossiers', id] as const,
}

export const useDossiers = (divisionId: number | null = null) => useQuery({
  queryKey: [...dossierKeys.all, divisionId],
  queryFn: () => api.listDossiers(divisionId === null ? {} : { division_id: divisionId }),
  enabled: divisionId !== null,
})
export const useDossier = (id: number) => useQuery({ queryKey: dossierKeys.one(id), queryFn: () => api.getDossier(id), enabled: Number.isFinite(id) })

export const queryError = (q: { error: unknown }) => (q.error ? errorMessage(q.error) : null)
