// Types des fichiers (documents) et de leurs versions : métadonnées, classement et statut d'ingestion. Jamais de contenu.
export type Statut = 'pending' | 'processing' | 'ready' | 'error'
export type ApercuMode = 'pdf' | 'image' | 'texte' | 'csv' | 'pdf_converti' | 'aucun'
export type Confidentialite = 'PUBLIC' | 'INTERNE' | 'CONFIDENTIEL'

export interface VersionMeta {
  numero: number
  nom_fichier: string
  type_mime: string | null
  taille_octets: number | null
  nb_pages: number | null
  ocr_utilise: boolean
  statut: Statut
  message_erreur: string | null
  cree_par_nom: string | null
  cree_le: string
  est_courante: boolean
  apercu: ApercuMode
}

export interface DocumentMeta {
  id: number
  titre: string
  dossier_id: number
  dossier_nom: string
  has_tabular: boolean
  has_image: boolean
  tableaux_imposes: boolean
  images_imposees: boolean
  nb_versions: number
  version: VersionMeta // la plus récente
  mon_role: string
  cree_par_nom: string | null
  cree_le: string
  modifie_le: string
  categorie_id: number | null
  categorie_nom: string | null
  type_document_id: number | null
  type_nom: string | null
  confidentialite: Confidentialite
  tags: string[]
  classement_source: string
  corbeille_le: string | null
}

export interface DocumentPage { items: DocumentMeta[]; total: number; page: number; taille: number }

export interface DocumentFilters {
  dossier_id?: number
  q?: string
  categorie_id?: number
  type_id?: number
  confidentialite?: string
  statut?: string
  tri?: 'date_desc' | 'titre_asc' | 'titre_desc'
  page: number
  taille: number
  corbeille?: boolean
}

export interface Referentiel {
  categories: { id: number; parent_id: number | null; nom: string; couleur: string | null; ordre: number; actif: boolean }[]
  types: { id: number; nom: string; actif: boolean }[]
  tags: { id: number; nom: string }[]
  confidentialites: Confidentialite[]
}

export const isIndexing = (s: Statut) => s === 'pending' || s === 'processing'
