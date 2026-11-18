import { api } from '../../shared/api/client'

export interface Indicateur { cle: string; libelle: string; valeur: number; ton: 'neutre' | 'attention' | 'alerte'; lien: string | null }
export interface Repartition { titre: string; colonnes: { cle: string; libelle: string }[]; lignes: { id: number | null; libelle: string; sous_titre: string | null; valeurs: Record<string, number>; alerte: boolean }[] }
export interface FichierBrief { id: number; titre: string; division_nom: string; depose_par: string | null; depose_le: string }
export interface ErreurIndexationBrief {
  document_id: number; titre: string; version_numero: number; nom_fichier: string
  message_erreur: string | null; division_nom: string; service_nom: string | null; roles: string[]; cree_le: string
}
export interface ErreursIndexation {
  total: number
  par_service: { nom: string; total: number }[]
  par_division: { nom: string; total: number }[]
  par_role: { nom: string; total: number }[]
  items: ErreurIndexationBrief[]
}
export interface TableauDeBord {
  niveau: 'ROOT' | 'SERVICE' | 'DIVISION' | 'AGENT'; titre: string; sous_titre: string | null; indicateurs: Indicateur[]
  repartition: Repartition | null; alertes: string[]; a_classer: FichierBrief[]
  erreurs_indexation: ErreursIndexation | null
  mes_roles: { id: number; code: string; libelle: string }[]; mes_fichiers: FichierBrief[]
  acces_ponctuels: { document_id: number; document_titre: string; expire_le: string }[]
}
export const fetchTableauDeBord = () => api<TableauDeBord>('/tableau-de-bord')
