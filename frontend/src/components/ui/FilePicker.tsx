// Sélecteur de fichier contrôlé : le fichier vit dans l'état du formulaire, donc « Remplir avec exemple » peut le fixer.
import { useRef } from 'react'
import { ACCEPTED_FILES, formatSize } from '../../lib/fichiers'

interface Props {
  id: string
  file: File | null
  onChange: (file: File | null) => void
  required?: boolean
}

export default function FilePicker({ id, file, onChange, required = false }: Props) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <div className="flex items-center gap-3">
      <button type="button" className="btn-ghost shrink-0" onClick={() => input.current?.click()}>Choisir un fichier</button>
      <span className="min-w-0 truncate text-sm text-cream-100">
        {file ? `${file.name} (${formatSize(file.size)})` : 'Aucun fichier choisi'}
      </span>
      <input
        ref={input}
        id={id}
        type="file"
        accept={ACCEPTED_FILES}
        required={required && !file}
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
    </div>
  )
}
