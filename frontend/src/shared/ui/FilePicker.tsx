// Zone de dépôt (glisser-déposer ou clic). Le fichier vit dans l'état du formulaire : « Remplir avec exemple » peut le fixer.
import { FileUp } from 'lucide-react'
import { useRef, useState } from 'react'
import { ACCEPTED_FILES } from '../lib/fichiers'
import { cn } from '../lib/cn'
import { formatSize } from '../lib/format'

interface Props { id: string; file: File | null; onChange: (file: File | null) => void; required?: boolean }

export default function FilePicker({ id, file, onChange, required = false }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onChange(e.dataTransfer.files?.[0] ?? null) }}
      className={cn('flex items-center gap-3 rounded-lg border border-dashed px-4 py-3 transition', over ? 'border-gold-300 bg-gold-500/10' : 'border-gold-500/50 bg-leaf-950/40')}
    >
      <FileUp className="h-5 w-5 shrink-0 text-gold-400" aria-hidden />
      <div className="min-w-0 flex-1 text-sm">
        {file ? <p className="truncate font-medium text-cream-50">{file.name} <span className="font-normal text-cream-300">({formatSize(file.size)})</span></p>
          : <p className="text-cream-300">Glisser un fichier ici, ou le choisir sur l’ordinateur</p>}
      </div>
      <button type="button" className="btn-ghost shrink-0" onClick={() => input.current?.click()}>{file ? 'Changer' : 'Parcourir'}</button>
      <input ref={input} id={id} type="file" accept={ACCEPTED_FILES} required={required && !file} className="sr-only" tabIndex={-1}
        onChange={(e) => onChange(e.target.files?.[0] ?? null)} />
    </div>
  )
}
