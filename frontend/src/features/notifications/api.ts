import { api } from '../../shared/api/client'

export interface Notification { id: number; type_evenement: string; reference_type: string | null; reference_id: number | null; message: string; lu: boolean; cree_le: string }
export interface Notifications { non_lues: number; items: Notification[] }

export const listNotifications = () => api<Notifications>('/notifications')
export const marquerLue = (id: number) => api<void>(`/notifications/${id}/lue`, { method: 'POST' })
export const toutMarquerLu = () => api<void>('/notifications/lues', { method: 'POST' })
// Nettoyage : supprime les notifications lues et celles des demandes déjà tranchées ou annulées.
export const nettoyerNotifications = () => api<{ supprimees: number }>('/notifications/nettoyer', { method: 'POST' })
