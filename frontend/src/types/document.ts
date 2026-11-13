// Types des fichiers (documents) et de leurs versions : métadonnées et statut d'ingestion. Jamais de contenu.

export type Statut = 'pending' | 'processing' | 'ready' | 'error'
export type ApercuMode = 'pdf' | 'image' | 'texte' | 'csv' | 'pdf_converti' | 'aucun'

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
}
