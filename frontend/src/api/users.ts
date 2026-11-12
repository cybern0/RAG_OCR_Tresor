// Appels de gestion des utilisateurs (réservés à l'ADMIN).
import type { UserCreate, UserOut, UserUpdate } from '../types/user'
import { api } from './client'

export const listUsers = () => api<UserOut[]>('/users')
export const createUser = (data: UserCreate) => api<UserOut>('/users', { method: 'POST', json: data })
export const updateUser = (id: number, data: UserUpdate) =>
  api<UserOut>(`/users/${id}`, { method: 'PATCH', json: data })
