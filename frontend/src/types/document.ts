// Types TypeScript des documents (métadonnées, statut d'ingestion). Jamais de contenu.

export type Statut = 'pending' | 'processing' | 'ready' | 'error'

export interface DocumentMeta {
  id: number
  titre: string
  nom_fichier: string
  type_mime: string | null
  taille_octets: number | null
  nb_pages: number | null
  ocr_utilise: boolean
  has_tabular: boolean
  statut: Statut
  message_erreur: string | null
  service_id: number
  service_nom: string
  cree_par_nom: string | null
  cree_le: string
  modifie_le: string
}
