// Outils sur les fichiers : type d'après l'extension, cases « tableaux / images » imposées, lecture CSV.
// Miroir de la règle du backend (services/ingestion/parser.py) : le backend reste l'autorité.

export const ACCEPTED_FILES =
  '.pdf,.docx,.doc,.pptx,.ppt,.odt,.ods,.odp,.rtf,.xlsx,.xls,.csv,.txt,.md,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp'

export const extension = (name: string) => {
  const i = name.lastIndexOf('.')
  return i === -1 ? '' : name.slice(i).toLowerCase()
}

const TABLE_EXT = new Set(['.csv', '.xlsx', '.xls', '.ods'])
const IMAGE_EXT = new Set(['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp'])

/** Cases imposées par le type du fichier (cochées et non modifiables). */
export function forcedFlags(name: string): { tableaux: boolean; images: boolean } {
  const ext = extension(name)
  return { tableaux: TABLE_EXT.has(ext), images: IMAGE_EXT.has(ext) }
}

export type PreviewKind = 'pdf' | 'image' | 'texte' | 'csv' | 'aucun'

/** Aperçu possible localement, avant l'envoi. Word, PowerPoint, etc. sont convertis par le serveur après l'envoi. */
export function localPreviewKind(name: string): PreviewKind {
  const ext = extension(name)
  if (ext === '.pdf') return 'pdf'
  if (['.png', '.jpg', '.jpeg', '.webp', '.bmp'].includes(ext)) return 'image'
  if (ext === '.csv') return 'csv'
  if (ext === '.txt' || ext === '.md') return 'texte'
  return 'aucun'
}

/** Lecture simple d'un CSV (guillemets ; séparateur « ; », « , » ou tabulation détecté sur la première ligne). */
export function parseCsv(text: string, maxRows = 200): string[][] {
  const first = text.split(/\r?\n/, 1)[0] ?? ''
  const sep = [';', '\t', ','].reduce((best, c) => (first.split(c).length > first.split(best).length ? c : best), ';')
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  for (let i = 0; i < text.length && rows.length < maxRows; i++) {
    const ch = text[i]
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++ } else if (ch === '"') quoted = false
      else cell += ch
    } else if (ch === '"') quoted = true
    else if (ch === sep) { row.push(cell); cell = '' }
    else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++
      row.push(cell); cell = ''
      if (row.some((c) => c !== '')) rows.push(row)
      row = []
    } else cell += ch
  }
  if (rows.length < maxRows && (cell !== '' || row.length)) { row.push(cell); rows.push(row) }
  return rows
}
