import { api } from '../../shared/api/client'

export interface Indicateur { cle: string; libelle: string; valeur: number; ton: 'neutre' | 'attention' | 'alerte'; lien: string | null }
export interface Repartition { titre: string; colonnes: { cle: string; libelle: string }[]; lignes: { id: number | null; libelle: string; sous_titre: string | null; valeurs: Record<string, number>; alerte: boolean }[] }
export interface FichierBrief { id: number; titre: string; dossier_id: number; dossier_nom: string; depose_par: string | null; depose_le: string }
export interface TableauDeBord {
  niveau: 'ROOT' | 'DIVISION' | 'AGENT'; titre: string; sous_titre: string | null; indicateurs: Indicateur[]
  repartition: Repartition | null; alertes: string[]; a_classer: FichierBrief[]
  mes_roles: { id: number; code: string; libelle: string }[]; mes_fichiers: FichierBrief[]
  acces_ponctuels: { document_id: number; document_titre: string; expire_le: string }[]
}
export const fetchTableauDeBord = () => api<TableauDeBord>('/tableau-de-bord')
