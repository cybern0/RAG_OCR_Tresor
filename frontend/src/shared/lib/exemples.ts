// Données d'exemple pour le bouton « Remplir avec exemple » : fausses informations plausibles, tirées au hasard.
// Aucun de ces noms ne désigne une vraie personne ; les champs restent vides tant que le bouton n'est pas cliqué.

const pick = <T,>(items: T[]): T => items[Math.floor(Math.random() * items.length)]
const nombre = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1)) + min
const sansAccent = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '')

const NOMS = ['Rakoto', 'Rabe', 'Randria', 'Andrianina', 'Razafy', 'Ravelo', 'Rasoa', 'Rakotomalala', 'Ratsimba']
const PRENOMS = ['Hery', 'Soa', 'Lalaina', 'Tahiana', 'Mialy', 'Fidy', 'Njaka', 'Volana', 'Toky']
const FONCTIONS = ['Chargé d’études', 'Comptable', 'Gestionnaire de dossiers', 'Secrétaire de direction', 'Contrôleur de gestion']
const THEMES = ['marchés publics', 'congés annuels', 'budget prévisionnel', 'frais de mission', 'archivage', 'courrier entrant', 'formation du personnel']
const SERVICES = ['Service du budget', 'Service des marchés', 'Service du personnel', 'Service de la comptabilité', 'Service des archives']
const DIRECTIONS = ['Direction générale', 'Direction des finances', 'Direction des ressources humaines', 'Direction administrative']
const QUESTIONS = [
  'Quel est le délai de paiement prévu pour les factures fournisseurs ?',
  'Combien de jours de congé annuel sont accordés par an ?',
  'Quelle est la dernière version de la procédure d’archivage et que change-t-elle ?',
  'Quels documents faut-il joindre à une demande de frais de mission ?',
]

export const exempleNom = () => pick(NOMS)
export const exemplePrenom = () => pick(PRENOMS)
export const exempleFonction = () => pick(FONCTIONS)
export const exempleTheme = () => pick(THEMES)
export const exempleQuestion = () => pick(QUESTIONS)
export const exempleMatricule = () => `M${nombre(10000, 99999)}`
export const exempleEmail = (prenom: string, nom: string) => `${sansAccent(prenom).toLowerCase()}.${sansAccent(nom).toLowerCase()}@exemple.mg`
export const exempleIdentifiant = () => `${sansAccent(pick(PRENOMS)).toLowerCase()}.${sansAccent(pick(NOMS)).toLowerCase()}`
export const exempleMotDePasse = () => `Exemple-${nombre(1000, 9999)}-mdp`
export const exempleCode = (prefixe: string) => `${prefixe}-${nombre(100, 999)}`
export const exempleNomService = () => `${pick(SERVICES)} (exemple ${nombre(1, 99)})`
export const exempleNomDirection = () => `${pick(DIRECTIONS)} (exemple ${nombre(1, 99)})`
export const exempleNomDossier = () => `Dossier ${exempleTheme()} ${nombre(2024, 2026)} (exemple)`
export const exempleDescription = () => `Documents relatifs aux ${exempleTheme()} : exemple de description de division.`
export const exempleTitreFichier = () => `Note sur les ${exempleTheme()} (exemple)`

/** Faux fichier texte avec un contenu plausible, pour remplir un champ fichier. */
export function exempleFichier(): File {
  const theme = exempleTheme()
  const jours = nombre(10, 45)
  const texte =
    `Note interne sur les ${theme}\n\n` +
    `Article 1. Le délai de traitement est de ${jours} jours à compter de la réception de la demande.\n\n` +
    `Article 2. Le responsable du marché est ${exemplePrenom()} ${exempleNom()}, qui valide chaque étape.\n\n` +
    `Article 3. Le montant maximal autorisé est de ${nombre(5, 90) * 100000} Ar par dossier.\n` +
    `Référence : EX-${nombre(1000, 9999)}\n`
  return new File([texte], `note_exemple_${nombre(100, 999)}.txt`, { type: 'text/plain' })
}
