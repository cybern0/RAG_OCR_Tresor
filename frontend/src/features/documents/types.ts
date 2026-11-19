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
  // paramètres de la dernière indexation réussie (null : inconnu) : servent à savoir si réindexer changerait quelque chose
  tableaux_indexes: boolean | null
  images_indexes: boolean | null
}

export interface DocumentMeta {
  id: number
  titre: string
  division_id: number
  division_nom: string
  has_tabular: boolean
  has_image: boolean
  tableaux_imposes: boolean
  images_imposees: boolean
  nb_versions: number
  version: VersionMeta // la plus récente
  mon_role: string
  droits: string[]
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
  q?: string
  categorie_id?: number
  type_id?: number
  confidentialite?: string
  statut?: string
  role_id?: number
  division_id?: number
  tri?: 'date_desc' | 'titre_asc' | 'titre_desc'
  page: number
  taille: number
  corbeille?: boolean
  a_classer?: boolean
}

export interface Referentiel {
  categories: { id: number; parent_id: number | null; nom: string; couleur: string | null; ordre: number; actif: boolean }[]
  types: { id: number; nom: string; actif: boolean }[]
  tags: { id: number; nom: string }[]
  confidentialites: Confidentialite[]
}

/** Options des filtres de la liste des fichiers, selon le périmètre du compte connecté. */
export interface FiltresListe {
  roles: { id: number; code: string; libelle: string; division_id: number; division_nom: string | null }[]
  divisions: { id: number; nom: string }[]
  depot_divisions: number[]
}

export const isIndexing = (s: Statut) => s === 'pending' || s === 'processing'
