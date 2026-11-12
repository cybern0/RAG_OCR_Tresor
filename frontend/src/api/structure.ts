// Appels de gestion des directions, services et agents, et du journal d'audit (ADMIN).
import type { Agent, AuditRow, Direction, ServiceItem } from '../types/structure'
import { api } from './client'

export const listDirections = () => api<Direction[]>('/structure/directions')
export const createDirection = (data: { code: string; nom: string }) =>
  api<Direction>('/structure/directions', { method: 'POST', json: data })
export const updateDirection = (id: number, data: { nom?: string; actif?: boolean }) =>
  api<Direction>(`/structure/directions/${id}`, { method: 'PATCH', json: data })

export const listServices = () => api<ServiceItem[]>('/structure/services')
export const createService = (data: { direction_id: number; code: string; nom: string; site?: string | null }) =>
  api<ServiceItem>('/structure/services', { method: 'POST', json: data })
export const updateService = (id: number, data: { nom?: string; actif?: boolean; direction_id?: number }) =>
  api<ServiceItem>(`/structure/services/${id}`, { method: 'PATCH', json: data })

export const listAgents = () => api<Agent[]>('/structure/agents')
export const createAgent = (data: {
  matricule: string
  nom: string
  prenom: string
  fonction?: string | null
  email?: string | null
  service_id: number
}) => api<Agent>('/structure/agents', { method: 'POST', json: data })
export const updateAgent = (id: number, data: { actif?: boolean; service_id?: number; fonction?: string | null }) =>
  api<Agent>(`/structure/agents/${id}`, { method: 'PATCH', json: data })

export const listAudit = () => api<AuditRow[]>('/audit?limit=200')
