import { api } from '../../shared/api/client'

export type TypeUnite = 'division'
export interface UniteSecret {
  type: TypeUnite; id: number; nom: string; service_id: number; service_nom: string
  secret_defini: boolean; deverrouille: boolean; valide_jusqua: string | null
}
export const listUnites = () => api<UniteSecret[]>('/securite/unites')
export const deverrouiller = (type: TypeUnite, unite_id: number, mot_de_passe: string) =>
  api<{ valide_jusqua: string; minutes: number }>('/securite/deverrouiller', { method: 'POST', json: { type, unite_id, mot_de_passe } })
export const verrouiller = (type: TypeUnite, unite_id: number) => api<void>('/securite/verrouiller', { method: 'POST', json: { type, unite_id } })
export const definirSecret = (type: TypeUnite, unite_id: number, nouveau_mot_de_passe: string, ancien_mot_de_passe?: string) =>
  api<void>('/securite/secrets', { method: 'PUT', json: { type, unite_id, nouveau_mot_de_passe, ancien_mot_de_passe: ancien_mot_de_passe || undefined } })
