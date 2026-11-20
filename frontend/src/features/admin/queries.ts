// Requêtes d'administration : une clé par ressource, invalidée après chaque écriture.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from './api'

export const adminKeys = {
  users: ['admin', 'users'] as const, directions: ['admin', 'directions'] as const, services: ['admin', 'services'] as const,
  agents: ['admin', 'agents'] as const, audit: ['admin', 'audit'] as const, stats: ['admin', 'stats'] as const, health: ['admin', 'health'] as const,
  categories: ['admin', 'classement', 'categories'] as const, types: ['admin', 'classement', 'types'] as const,
  tags: ['admin', 'classement', 'tags'] as const, rules: ['admin', 'classement', 'rules'] as const,
}

export const useUsers = () => useQuery({ queryKey: adminKeys.users, queryFn: api.listUsers })
export const useUser = (id: number) => useQuery({ queryKey: [...adminKeys.users, id], queryFn: () => api.getUser(id), enabled: Number.isFinite(id) })
export const useDirections = () => useQuery({ queryKey: adminKeys.directions, queryFn: api.listDirections })
export const useServices = () => useQuery({ queryKey: adminKeys.services, queryFn: api.listServices })
export const useAgentsDisponibles = (pourUser?: number) => useQuery({ queryKey: [...adminKeys.agents, 'disponibles', pourUser ?? null], queryFn: () => api.listAgentsDisponibles(pourUser) })
export const useAgents = () => useQuery({ queryKey: adminKeys.agents, queryFn: api.listAgents })
export const useAudit = () => useQuery({ queryKey: adminKeys.audit, queryFn: () => api.listAudit(200) })
export const useStats = () => useQuery({ queryKey: adminKeys.stats, queryFn: api.fetchStats })
export const useHealth = () => useQuery({ queryKey: adminKeys.health, queryFn: api.fetchHealth, refetchInterval: 30_000 })
export const useCategories = () => useQuery({ queryKey: adminKeys.categories, queryFn: api.listCategories })
export const useTypes = () => useQuery({ queryKey: adminKeys.types, queryFn: api.listTypes })
export const useTags = () => useQuery({ queryKey: adminKeys.tags, queryFn: api.listTags })
export const useRules = () => useQuery({ queryKey: adminKeys.rules, queryFn: api.listRules })

/** Mutation qui invalide les clés données (préfixes) en cas de succès. */
export function useAdminMutation<TVars, TData>(fn: (v: TVars) => Promise<TData>, invalidate: readonly (readonly unknown[])[]) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => Promise.all(invalidate.map((queryKey) => qc.invalidateQueries({ queryKey }))) })
}
