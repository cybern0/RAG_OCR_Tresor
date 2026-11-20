import Badge from '../../../shared/ui/Badge'
import type { DocumentMeta } from '../types'

const CONF_TONE = { PUBLIC: 'green', INTERNE: 'gray', CONFIDENTIEL: 'red' } as const

export function ClassementBadges({ doc, max = 3 }: { doc: DocumentMeta; max?: number }) {
  return (
    <div className="flex flex-wrap items-center gap-1">
      {doc.categorie_nom && <Badge tone="gold">{doc.categorie_nom}</Badge>}
      {doc.type_nom && <Badge tone="gray">{doc.type_nom}</Badge>}
      <Badge tone={CONF_TONE[doc.confidentialite] ?? 'gray'}>{doc.confidentialite.charAt(0) + doc.confidentialite.slice(1).toLowerCase()}</Badge>
      {doc.tags.slice(0, max).map((t) => <Badge key={t} tone="gray" className="font-normal">#{t}</Badge>)}
      {doc.tags.length > max && <span className="text-xs text-slate-600">+{doc.tags.length - max}</span>}
    </div>
  )
}
