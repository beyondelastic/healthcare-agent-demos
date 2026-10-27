import { Link2 } from 'lucide-react'
import type { Citation, SourceDocument } from './types'

type EvidenceProps = {
  citations: Citation[]
  documents: SourceDocument[]
  onCitation: (citation: Citation) => void
}

export function EvidenceShortcut({ citations, onCitation }: Omit<EvidenceProps, 'documents'>) {
  if (!citations.length) return null
  const count = new Set(citations.map(ref => ref.document_id)).size
  return <button type="button" className="source-shortcut" onClick={event => {
    event.preventDefault()
    event.stopPropagation()
    onCitation(citations[0])
  }}><Link2 size={14} />{count === 1 ? 'Quelle ansehen' : `${count} Quellen ansehen`}</button>
}

export default function CitationLinks({ citations, documents, onCitation }: EvidenceProps) {
  const ids = [...new Set(citations.map(ref => ref.document_id))]
  return <div className="evidence-links" aria-label="Originalquellen und Absatzbelege">
    {ids.map(id => {
      const refs = citations.filter(ref => ref.document_id === id)
        .filter((ref, index, items) => items.findIndex(item => item.paragraph_id === ref.paragraph_id) === index)
      return <div className="evidence-group" key={id}>
        <strong><Link2 size={13} />{documents.find(doc => doc.id === id)?.title ?? id}</strong>
        <div>{refs.map(ref => <button type="button" key={ref.paragraph_id}
          title={ref.quote} aria-label={`${documents.find(doc => doc.id === id)?.title ?? id}, Absatz ${ref.paragraph_id}`}
          onClick={() => onCitation(ref)}>Absatz {ref.paragraph_id.toUpperCase()} ansehen →</button>)}</div>
      </div>
    })}
  </div>
}
