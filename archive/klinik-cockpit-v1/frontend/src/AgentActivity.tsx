import { Bot, LoaderCircle } from 'lucide-react'
import type { AgentRun } from './types'
import { agentActivity } from './agentActivitySummary'

export default function AgentActivity({ run, runCount, currentSourceVersion }: {
  run: AgentRun; runCount: number; currentSourceVersion: number
}) {
  const activity = agentActivity(run)
  const status = run.status === 'running' ? 'In Bearbeitung' : run.status === 'failed' ? 'Fehlgeschlagen'
    : run.status === 'awaiting_approval' ? 'Vorschlag bereit'
      : run.status === 'applied' ? 'Vorschlag übernommen' : 'Vorschlag nicht übernommen'
  return <section className="agent-activity-summary" aria-label="Agentenarbeit aus dem Originalprotokoll">
    <div className="agent-activity-heading"><h2><Bot size={21} />Agentenarbeit</h2>
      <span className="pill subtle">{run.status === 'running' && <LoaderCircle size={13} className="spin" />}{status}</span>
    </div>
    <p><strong>Auslöser:</strong> {run.trigger?.title ?? 'Manuell gestartete Quellenprüfung'}
      <span className="muted"> · Auftrag {runCount} · Quellenstand {run.source_version}</span></p>
    {run.source_version !== currentSourceVersion && <p className="agent-warning">
      Dieser Lauf gehört zum früheren Quellenstand. Aktuell ist Stand {currentSourceVersion}; die neue Quelle ist hier noch nicht berücksichtigt.
    </p>}
    <dl className="agent-call-metrics">
      <div><dt>Modellaufrufe</dt><dd>{activity.modelCalls}<small>{activity.modelResponses} Antworten</small></dd></div>
      <div><dt>Werkzeugaufrufe</dt><dd>{activity.toolCalls}<small>{activity.toolResponses} Antworten{activity.toolErrors > 0 && ` · ${activity.toolErrors} Fehler`}</small></dd></div>
      <div><dt>Quellen gelesen</dt><dd>{activity.sourcesRead}<small>{activity.pendingNotices
        ? `davon ${activity.pendingNotices} ausstehende Befundvermerke` : 'erfolgreiche Inhaltsabrufe'}</small></dd></div>
      <div><dt>Abschnitte vorgeschlagen</dt><dd>{activity.changedSections.length}<small>neu oder geändert · keine automatische Übernahme</small></dd></div>
    </dl>
    <div className="agent-tool-results">{activity.tools.map(tool => <div key={tool.name}>
      <strong>{tool.label}</strong><span>{tool.calls} {tool.calls === 1 ? 'Aufruf' : 'Aufrufe'} · {tool.responses} {tool.responses === 1 ? 'Antwort' : 'Antworten'}{tool.errors > 0 && ` · ${tool.errors} Fehler`}</span>
    </div>)}</div>
    {activity.changedSections.length > 0 && <p className="agent-change-list"><strong>Vorgeschlagene Änderung:</strong> {activity.changedSections.map(section => section.title).join(' · ')}</p>}
    <details className="agent-call-details"><summary>Werkzeuge und Aufrufnachweis</summary>
      <p>Zahlen aus den gespeicherten Aufrufereignissen, keine simulierte Denkspur. Eine Werkzeugantwort allein belegt noch keinen erfolgreichen Inhaltsabruf.</p>
      {activity.tools.map(tool => <p key={tool.name}><code>{tool.name}</code> · {tool.calls} Aufrufe · {tool.responses} Antworten · {tool.errors} Fehler</p>)}
      <p>Auftrags-ID: <code>{run.id}</code>. Response-IDs und einzelne Ereignisse stehen unter „Agentenaktivität und Quellen ansehen“.</p>
    </details>
  </section>
}
