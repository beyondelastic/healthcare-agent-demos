import { Check, CircleAlert, FileText } from 'lucide-react'
import type { AgentRun, Encounter } from './types'
import { initialSources } from './Presentation'
import { readSources, sourceEvidence } from './sourceEvidence'

export default function SourceInvestigation({ encounter, run, previousRun, onShowSource, onContinue, blocked }: {
  encounter: Encounter
  run: AgentRun
  previousRun: AgentRun | null
  onShowSource: (id: string) => void
  onContinue?: () => void
  blocked: boolean
}) {
  const sources = sourceEvidence(run)
  const previousSources = previousRun?.case_id === run.case_id && previousRun.source_version <= run.source_version
    ? readSources(previousRun) : []
  const knownIds = new Set([...initialSources(encounter), ...previousSources].map(doc => doc.id))
  const read = sources.filter(doc => doc.read)
  const additional = read.filter(doc => !knownIds.has(doc.id))
  const pending = read.filter(doc => doc.availability === 'pending')
  const unavailable = sources.filter(doc => doc.availability === 'not_released')
  const complete = run.status === 'awaiting_approval' && run.base_revision === encounter.revision
    && run.source_version === encounter.source_version
  const findings = complete ? encounter.findings.filter(finding => !finding.resolved) : []
  return <section className="source-investigation" aria-label="Quellenprüfung und Ergebnis">
    <div className="investigation-heading"><div><h2>Dokumente im Fallkontext</h2>
      <p>{run.status === 'running' ? 'Dokumentenbestand und Inhalte werden aus den angebundenen Quellsystemen abgerufen.'
        : 'Ergebnis der Quellenprüfung. Es wurden keine Dokumente oder Brieftexte automatisch geändert.'}</p></div>
      <span className="pill subtle">Quellenstand {run.source_version}</span>
    </div>
    <div className="source-counts" aria-live="polite">
      <span><strong>{sources.length}</strong> gefunden</span>
      <span><strong>{read.length}</strong> gelesen{pending.length > 0 && ` · davon ${pending.length} Befundvermerk`}</span>
      <span><strong>+{additional.length}</strong> zusätzlich erschlossen</span>
      {unavailable.length > 0 && <span className="amber-text"><strong>{unavailable.length}</strong> nicht freigegeben</span>}
    </div>
    {!sources.length && <p className="muted small">Die Dokumentenübersicht wurde noch nicht zurückgeliefert.</p>}
    <div className="discovered-sources">{sources.map(doc => {
      const extra = !knownIds.has(doc.id)
      const label = doc.availability === 'not_released' ? 'Nicht freigegeben · kein Inhalt'
        : doc.read ? doc.availability === 'pending' ? 'Vermerk gelesen · Befund ausstehend' : 'Inhalt gelesen'
          : doc.availability === 'pending' ? 'Befund ausstehend · Abruf offen' : 'Gefunden · Abruf offen'
      return <button key={doc.id} type="button" className={`discovered-source${extra && doc.read ? ' additional-source' : ''}`}
        title={doc.read ? `${doc.title} · Originalquelle öffnen` : undefined}
        disabled={!doc.read || blocked} onClick={() => onShowSource(doc.id)}>
        {doc.read ? <Check size={18} /> : <FileText size={18} />}
        <span><strong>{doc.title}</strong><small>{doc.system}</small>
          <span className={`pill ${doc.availability !== 'available' ? 'amber' : doc.read ? 'teal' : 'subtle'}`}>{label}</span>
        </span>
        {extra && doc.read && <small className="additional-label">Zusätzlich erschlossen</small>}
      </button>
    })}</div>
    {run.status === 'failed' && <p className="message error" role="alert">Quellenprüfung nicht abgeschlossen. Ein Abruffehler ist kein Nachweis fehlender Dokumente.</p>}
    {complete && <div className="investigation-findings">
      <h3>{findings.length ? 'Offene Punkte' : 'Keine offenen Punkte in der Quellenprüfung'}</h3>
      {findings.map(finding => <article key={finding.id}><CircleAlert size={18} />
        <div><strong>{finding.title}</strong><p>{finding.description}</p></div>
      </article>)}
      {!findings.length && <p>Der Briefvorschlag bleibt fachlich zu prüfen.</p>}
      {onContinue && <button className="button primary" disabled={blocked} onClick={onContinue}>
        {encounter.kis.medication_released ? 'Briefvorschlag öffnen' : 'Medikationsplan prüfen'}
      </button>}
    </div>}
  </section>
}
