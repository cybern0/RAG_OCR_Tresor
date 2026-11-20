import type { DivisionItem } from './api'

/** Liste déroulante de choix de la division (affichée seulement quand le compte peut en choisir une). */
export default function DivisionSelect({ divisions, value, onChange }: { divisions: DivisionItem[]; value: number; onChange: (id: number) => void }) {
  return (
    <select className="input w-64" aria-label="Division" value={value} onChange={(e) => onChange(Number(e.target.value))}>
      {divisions.map((d) => <option key={d.id} value={d.id}>{d.nom}{d.service_nom ? ` (${d.service_nom})` : ''}</option>)}
    </select>
  )
}
