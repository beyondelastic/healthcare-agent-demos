import { useEffect, useState } from 'react'
import { CircleAlert, CircleDot, FileText } from 'lucide-react'
import type { AgentRun, Encounter } from './types'
import { readSources } from './sourceEvidence'
export { readSources } from './sourceEvidence'

export type Scene = 'sources' | 'agent' | 'review' | 'handover'

export function initialSources(encounter: Encounter) {
  const previews = encounter.documents.filter(doc => ['Aufnahme', 'Verlauf'].includes(doc.kind))
  return (previews.length >= 2 ? previews : encounter.documents.filter(doc => doc.status === 'available')).slice(0, 2)
}

export function usePresentationMode(caseId: string) {
  const [presentation, setPresentation] = useState(
    new URLSearchParams(window.location.search).get('view') !== 'full',
  )
  useEffect(() => {
    const url = new URL(window.location.href)
    url.searchParams.set('case', caseId)
    url.searchParams.set('view', presentation ? 'presentation' : 'full')
    window.history.replaceState(null, '', url)
  }, [caseId, presentation])
  return [presentation, setPresentation] as const
}

export function ViewModeToggle({ presentation, onChange }: {
  presentation: boolean; onChange: (value: boolean) => void
}) {
  return <div className="view-mode-toggle" role="group" aria-label="Ansichtsmodus">
    <button type="button" aria-pressed={presentation} onClick={() => onChange(true)}>Präsentation</button>
    <button type="button" aria-pressed={!presentation} onClick={() => onChange(false)}>Vollansicht</button>
  </div>
}

export function PresentationSteps({ scene, onChange, hasDraft, hasProposal }: {
  scene: Scene; onChange: (value: Scene) => void; hasDraft: boolean; hasProposal: boolean
}) {
  const steps: { id: Scene; title: string; subtitle: string; blocked?: string }[] = [
    { id: 'sources', title: 'Ausgangslage', subtitle: 'Verteilte Informationen' },
    { id: 'agent', title: 'Agent arbeitet', subtitle: 'Quellen tatsächlich abrufen' },
    { id: 'review', title: 'Vorschlag prüfen', subtitle: 'Lücken sehen. Änderungen verstehen.',
      blocked: !hasDraft && !hasProposal ? 'Zuerst einen Agentenvorschlag erstellen.' : undefined },
    { id: 'handover', title: 'Freigeben & übergeben', subtitle: 'Der Mensch entscheidet',
      blocked: hasProposal ? 'Zuerst den offenen Vorschlag übernehmen oder verwerfen.'
        : !hasDraft ? 'Zuerst einen Entwurf übernehmen.' : undefined },
  ]
  return <nav className="presentation-steps" aria-label="Demo-Szenen">
    {steps.map((step, index) => <button key={step.id} type="button"
      aria-current={scene === step.id ? 'step' : undefined}
      disabled={Boolean(step.blocked)} title={step.blocked} onClick={() => onChange(step.id)}>
      <span>{index + 1}</span><div><strong>{step.title}</strong><small>{step.subtitle}</small></div>
    </button>)}
  </nav>
}

export function SourceOverview({ encounter, onShowSource }: {
  encounter: Encounter; onShowSource: (id: string) => void
}) {
  return <section className="source-overview">
    <div className="eyebrow">1 · AUSGANGSLAGE</div>
    <h1>Viele Quellen. Noch kein gemeinsames Bild.</h1>
    <p>Aufnahme und Verlauf sind bereits einsehbar. Die Quellenprüfung erschließt weitere Dokumente dieses Aufenthalts.</p>
    <div className="source-card-grid">{initialSources(encounter).map(doc => <button key={doc.id}
      type="button" onClick={() => onShowSource(doc.id)}>
      <FileText size={23} /><strong>{doc.kind}</strong>
      <span className={`pill ${doc.status === 'pending' ? 'amber' : 'teal'}`}>
        {doc.status === 'pending' ? 'Ausstehend' : 'Verfügbar'}</span>
      <small>Quelle ansehen →</small>
    </button>)}</div>
    <p className="source-preview-note">Weitere Quellen und ihr Abrufstatus erscheinen während der Prüfung.</p>
    {encounter.draft && <p className="saved-draft-context">Ein gespeicherter Entwurf ist vorhanden. Diese Quellenansicht blendet ihn nur aus; ein neuer Agentenauftrag erstellt zunächst einen Vorschlag.</p>}
  </section>
}

function activityTitle(item: AgentRun['events'][number]): string {
  if (item.kind === 'tool_result') {
    if (item.title === 'list_case_documents') return 'Dokumentenbestand aus dem Demo-KIS abgerufen'
    if (item.title === 'get_case_workflow') return 'Offene Punkte und Freigabestatus abgerufen'
    if (item.title === 'get_laboratory_status') return 'Tatsächlichen Status im simulierten LIS geprüft'
    if (item.title === 'get_followup_context') return 'Zuständigkeiten und vorhandene Nachverfolgungsaufgaben abgeglichen'
    if (item.title === 'read_case_document') {
      const result = item.result
      if (result && typeof result === 'object' && 'document' in result) {
        const document = result.document
        if (document && typeof document === 'object' && 'title' in document && typeof document.title === 'string') {
          return `Quelle gelesen: ${document.title}`
        }
      }
      return 'Dokumentabruf beantwortet; kein freigegebener Inhalt verfügbar'
    }
  }
  return item.title
}

export function CompactActivity({ run, onShowSource, compact = false }: { run: AgentRun; onShowSource: (id: string) => void; compact?: boolean }) {
  const events = run.events.filter(item => !['tool_call', 'model_result'].includes(item.kind)).slice(compact ? -3 : -6)
  const sources = readSources(run)
  return <div className={`compact-activity${compact ? ' focused-activity' : ''}`}>
    <div className="eyebrow">{compact ? 'ECHTE AGENTENAKTIVITÄT' : '2 · ECHTE AGENTENAKTIVITÄT'}</div>
    <h2>{run.status === 'running' ? 'Der Agent beschafft die Informationen.' : run.status === 'failed'
      ? 'Der Auftrag wurde nicht abgeschlossen.' : 'Die Quellenarbeit ist nachvollziehbar.'}</h2>
    <p>Letzte {events.length} Ereignisse aus diesem Auftrag. Keine simulierten Schritte.</p>
    <details className="retrieved-sources" open={compact ? undefined : true}>
      <summary>{sources.length} tatsächlich gelesene Quellen ansehen</summary>
      <h3>{sources.length} tatsächlich gelesene Quellen</h3>
      <p>Nur erfolgreiche Dokumentabrufe, nicht die Bestandsliste. „Ausstehend“ bedeutet: nur der ausstehende Befundvermerk wurde gelesen.</p>
      <div className="source-card-grid">{sources.map(doc => <button type="button" key={doc.id}
        onClick={() => onShowSource(doc.id)}>
        <FileText size={20} /><strong>{doc.title}</strong>
        <span className={`pill ${doc.status === 'pending' ? 'amber' : 'teal'}`}>{doc.status === 'pending' ? 'Vermerk gelesen · Befund ausstehend' : 'Quelle gelesen'}</span>
        <small>Originalquelle ansehen →</small>
      </button>)}</div>
    </details>
    <ol>{events.map((item, index) => <li key={`${item.at}-${index}`}>
      {item.kind === 'error' || item.kind === 'tool_error' ? <CircleAlert size={17} /> : <CircleDot size={17} />}
      <div><strong>{activityTitle(item)}</strong>
        {item.error && <p>{item.error}</p>}
        <small>{new Date(item.at).toLocaleTimeString('de-DE')}</small>
      </div>
    </li>)}</ol>
  </div>
}
