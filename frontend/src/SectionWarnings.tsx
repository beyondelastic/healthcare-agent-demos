import { CircleAlert } from 'lucide-react'
import type { Finding } from './types'

export function findingsForSection(findings: Finding[], sectionId: string): Finding[] {
  return findings.filter(finding => !finding.resolved && finding.section_ids.includes(sectionId))
}

export default function SectionWarnings({ findings, stale, onShowFinding }: {
  findings: Finding[]
  stale: boolean
  onShowFinding: (id: string) => void
}) {
  if (!findings.length && !stale) return null
  return <aside className="section-warnings" aria-label="Dokumentationshinweise zu diesem Abschnitt">
    {stale && <div className="section-warning stale-section-warning">
      <CircleAlert size={16} aria-hidden="true" /><div><strong>Älterer Quellenstand</strong>
        <p>Dieser Text ist noch nicht gegen die neuesten Quellen aktualisiert. Erneut erstellen bzw. mit dem Agenten prüfen und anschließend fachlich prüfen.</p>
      </div>
    </div>}
    {findings.map(finding => <div className="section-warning" key={finding.id}>
      <CircleAlert size={16} aria-hidden="true" /><div>
        <span className="section-warning-kind">{finding.type === 'pending' ? 'Befund ausstehend'
          : finding.type === 'missing' ? 'Quelle fehlt' : 'Klärungsbedarf'}</span>
        <strong>{finding.title}</strong>
        {finding.review && <p>Bewertung dokumentiert – der Sachverhalt ist weiterhin offen.</p>}
        <button type="button" onClick={() => onShowFinding(finding.id)}
          aria-label={`Prüfpunkt ansehen: ${finding.title}`}>Prüfpunkt ansehen →</button>
      </div>
    </div>)}
  </aside>
}
