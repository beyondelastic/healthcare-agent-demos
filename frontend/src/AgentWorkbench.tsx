import { useEffect, useRef, useState } from 'react'
import { Bot, CheckCheck, CircleAlert, Database, LoaderCircle, RefreshCw, ShieldCheck } from 'lucide-react'
import { api, ApiError } from './api'
import type { AgentRun, Citation, Encounter, Health } from './types'
import SectionWarnings, { findingsForSection } from './SectionWarnings'
import { CompactActivity } from './Presentation'
import type { Scene } from './Presentation'
import CitationLinks, { EvidenceShortcut } from './CitationLinks'
import { currentLetterCopy } from './demoStory'
import type { StoryStage } from './demoStory'
import AgentActivity from './AgentActivity'

const statusLabels: Record<AgentRun['status'], string> = {
  running: 'Agent arbeitet', awaiting_approval: 'Vorschlag zur Prüfung', applied: 'Menschlich übernommen',
  rejected: 'Verworfen', failed: 'Auftrag fehlgeschlagen',
}

export default function AgentWorkbench({ encounter, health, dirty, busy, onBusy, onChange, onCitation, onReload, onShowFinding,
  presentation, scene, onSceneChange, onRunChange, onShowSource, onEnsureCurrent, onActionChange, externalPending,
  guided, guidedWaiting, guidedStage, onHistoryReady, needsAgent, focusSection }: {
  encounter: Encounter; health: Health | null; dirty: boolean; busy: boolean
  onBusy: (label: string) => void; onChange: (value: Encounter) => void
  onCitation: (value: Citation) => void; onReload: () => void
  onShowFinding: (id: string) => void
  presentation: boolean; scene: Scene; onSceneChange: (scene: Scene) => void
  onRunChange: (run: AgentRun | null, previous: AgentRun | null) => void
  onShowSource: (id: string) => void; onEnsureCurrent: () => Promise<boolean>
  onActionChange: (pending: boolean) => void
  externalPending: boolean
  guided: boolean; guidedWaiting: boolean; guidedStage?: StoryStage
  needsAgent: boolean; focusSection: string
  onHistoryReady: (ready: boolean) => void
}) {
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [selectedRun, setSelectedRun] = useState('')
  const [refreshCounter, setRefreshCounter] = useState(0)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState<{ revision: number; text: string } | null>(null)
  const [reviewer, setReviewer] = useState('Demo-Prüfer(in)')
  const [confirmed, setConfirmed] = useState(false)
  const [action, setAction] = useState<'accept' | 'reject' | 'writeback' | null>(null)
  const confirmationRef = useRef<HTMLDivElement>(null)
  const latestRunId = useRef('')
  const run = guided ? runs[0] : runs.find(item => item.id === selectedRun) ?? runs[0]
  const running = runs.some(item => item.status === 'running')
  const proposalStale = Boolean(run && run.base_revision !== encounter.revision)
  const firstDraft = !run?.base_sections.length
  const kisUrl = `/demo-kis?case=${encounter.id}&view=${presentation ? 'presentation' : 'full'}`
  const savedCopy = currentLetterCopy(encounter)
  const blocked = busy || dirty || externalPending
  const writebackReason = dirty ? 'Zuerst die Briefänderungen speichern.'
    : !encounter.draft ? 'Zuerst einen Entwurf übernehmen.'
      : encounter.draft.source_version !== encounter.source_version ? 'Der Brief hat einen älteren Quellenstand. Zuerst aktualisieren und erneut prüfen.'
        : encounter.status !== 'approved' ? 'Zuerst die Prüfpunkte bewerten und unten die Demo-Freigabe erteilen.'
          : busy ? 'Bitte die laufende Aktion abwarten.' : ''

  useEffect(() => { onRunChange(run ?? null, runs.find(item => item.id !== run?.id && item.proposal) ?? null) }, [run, runs, onRunChange])
  useEffect(() => { onActionChange(Boolean(action)) }, [action, onActionChange])

  useEffect(() => {
    if (action) confirmationRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [action])

  useEffect(() => {
    setConfirmed(false)
    if (action) setError('Der Fallstand wurde aktualisiert. Bitte die Aktion erneut prüfen und ausdrücklich bestätigen.')
  }, [encounter.revision])

  useEffect(() => {
    let active = true
    let timer: number | undefined
    async function refresh() {
      try {
        const items = await api<AgentRun[]>(`/cases/${encounter.id}/agent-runs`)
        if (!active) return
        setRuns(items)
        const displayed = guided ? items[0] : items.find(item => item.id === selectedRun) ?? items[0]
        onRunChange(displayed ?? null, items.find(item => item.id !== displayed?.id && item.proposal) ?? null)
        onHistoryReady(true)
        if (items[0] && latestRunId.current && items[0].id !== latestRunId.current) {
          setSelectedRun(items[0].id); setAction(null); setConfirmed(false); setNotice(null)
        }
        latestRunId.current = items[0]?.id ?? ''
        if (!items.length) { setSelectedRun(''); setAction(null); setConfirmed(false); setNotice(null); setError('') }
        if (items.some(item => item.status === 'running') || encounter.event_automation.enabled)
          timer = window.setTimeout(() => void refresh(), 1500)
      } catch (err) {
        if (active) { onHistoryReady(true); setError(err instanceof Error ? err.message : 'Agentenprotokoll konnte nicht geladen werden.') }
      }
    }
    void refresh()
    return () => { active = false; window.clearTimeout(timer) }
  }, [encounter.id, encounter.revision, selectedRun, refreshCounter, guided])

  async function start() {
    if (!await onEnsureCurrent()) {
      setError('Auftrag nicht gestartet. Bitte den aktualisierten Fallstand oder den Ladehinweis prüfen und erneut starten.')
      return
    }
    onSceneChange('agent')
    onBusy('Agentenauftrag starten'); setError(''); setNotice(null)
    try {
      const created = await api<AgentRun>(`/cases/${encounter.id}/agent-runs`, {
        method: 'POST', body: JSON.stringify({ revision: encounter.revision }),
      })
      setRuns(items => [created, ...items]); setSelectedRun(created.id); setAction(null); setConfirmed(false)
    } catch (err) { setError(err instanceof Error ? err.message : 'Agentenauftrag konnte nicht gestartet werden.') }
    finally { onBusy('') }
  }

  async function prepareAction(value: 'accept' | 'reject' | 'writeback') {
    if (!await onEnsureCurrent()) {
      setError('Aktion nicht geöffnet. Bitte den aktualisierten Fallstand oder den Ladehinweis prüfen und erneut öffnen.')
      return
    }
    setAction(value); setConfirmed(false); setError(''); setNotice(null)
  }

  async function commit() {
    if (!action || !confirmed || reviewer.trim().length < 2) return
    if (!await onEnsureCurrent()) {
      setConfirmed(false)
      setError('Keine Änderung gespeichert. Fallstand prüfen und die Aktion erneut bestätigen; bei einem Ladefehler KIS-Stand laden.')
      return
    }
    if (action !== 'writeback' && (!run || run.status !== 'awaiting_approval')) {
      setError('Dieser Vorschlag steht nicht mehr zur Übernahme oder zum Verwerfen bereit. Bitte den Fall neu laden.')
      return
    }
    onBusy('Menschliche Bestätigung speichern'); setError(''); setNotice(null)
    try {
      const path = action === 'writeback' ? `/kis/cases/${encounter.id}/writeback`
        : `/cases/${encounter.id}/agent-runs/${run.id}/${action}`
      const value = await api<Encounter>(path, {
        method: 'POST', body: JSON.stringify({ revision: encounter.revision, reviewer, confirmed: true }),
      })
      setError('')
      onChange(value); onSceneChange(action === 'writeback' ? 'handover' : value.draft ? 'review' : 'sources')
      setAction(null); setConfirmed(false)
      setNotice({ revision: value.revision, text: action === 'accept' ? 'Vorschlag übernommen. Den Brief und seine Quellen jetzt fachlich prüfen; noch keine Demo-Freigabe.'
        : action === 'reject' ? 'Vorschlag verworfen. Der Brief ist unverändert.'
          : 'Geprüfter Demo-Entwurf im Demo-KIS gespeichert. Keine klinische Signatur und kein Versand.' })
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setConfirmed(false)
      setError(err instanceof Error ? err.message : 'Bestätigung fehlgeschlagen.')
    }
    finally { onBusy('') }
  }

  const trace = run && <details className="agent-trace-details" open={presentation ? undefined : true}>
    <summary>Technische Details · Originalprotokoll</summary>
    <div className="agent-trace"><h3>Was tatsächlich passiert</h3><p>Originale Werkzeugereignisse, keine simulierten Gedanken. Details enthalten synthetische Quelldaten.</p>
      <ol>{run.events.map((item, index) => <li key={index} className={`trace-${item.kind}`}>
        <span>{new Date(item.at).toLocaleTimeString('de-DE')}</span>
        <details open={item.kind === 'tool_error'}><summary>{item.title}{item.kind === 'tool_call' ? ' · angefordert' : item.kind === 'tool_result' ? ' · empfangen' : ''}</summary>
          {item.response_id && <code>{item.response_id}</code>}
          {item.arguments && <pre>{item.arguments}</pre>}
          {item.result !== undefined && <pre>{JSON.stringify(item.result, null, 2)}</pre>}
          {item.error && <p>{item.error}</p>}
        </details>
      </li>)}</ol>
      {run.status === 'running' && <p role="status"><LoaderCircle size={15} className="spin" /> Auf echte Foundry-Antwort warten …</p>}
    </div>
  </details>

  return <section className="agent-workbench" aria-label="Foundry-Agent und Demo-KIS">
    <div className="agent-heading" hidden={presentation}>
      <div className="agent-identity"><span className="agent-symbol"><Bot size={26} /></span><div>
        <div className="eyebrow">MICROSOFT FOUNDRY · ECHTER AGENT</div>
        <h2>Der Agent holt die Quellen. Sie entscheiden.</h2>
        <p>Fallauftrag → lesende KIS-Werkzeuge → quellenbasierter Vorschlag → menschliche Übernahme.</p>
      </div></div>
      <a className="button" href={kisUrl}><Database size={15} />Demo-KIS öffnen</a>
    </div>
    {guided && run && <AgentActivity run={run} runCount={runs.length} currentSourceVersion={encounter.source_version} />}
    <div className="agent-toolbar" hidden={presentation && (scene === 'handover' || (guided && !needsAgent))}>
      <span hidden={presentation}>{health?.agent.name ?? 'Dokumentationsagent'} · Version {health?.agent.version || 'nicht eingerichtet'} · nur lesende Werkzeuge</span>
      {presentation && !guided && <a className="button" href={kisUrl}><Database size={15} />Demo-KIS öffnen</a>}
      <div className="inline-actions"><button className="button" disabled={busy} onClick={() => { setError(''); setRefreshCounter(value => value + 1); onReload() }}><RefreshCw size={14} />KIS-Stand laden</button>
        {presentation && run?.status === 'awaiting_approval' && !proposalStale && scene !== 'review' && <button className="button primary" onClick={() => onSceneChange('review')}>Zum Vorschlag</button>}
        <button className="button primary" hidden={presentation && (Boolean(action) || run?.status === 'awaiting_approval' && !proposalStale)}
          disabled={blocked || running || guidedWaiting || !health?.agent.configured} onClick={() => void start()}>
          {running ? <LoaderCircle size={16} className="spin" /> : <Bot size={16} />}
          {running ? 'Quellenprüfung läuft …' : run && run.source_version !== encounter.source_version
            ? 'Neue Quelle mit Agent prüfen' : run || encounter.draft ? 'Quellen mit Agent erneut prüfen' : guided ? 'Quellen mit Agent prüfen' : 'Agentenauftrag starten'}
        </button></div>
    </div>
    {!health?.agent.configured && <p className="agent-warning" role="status">Der Foundry-Agent ist nicht eingerichtet. In der Vollansicht stehen Konfiguration und der ausdrücklich gekennzeichnete Probenmodus bereit.</p>}
    {dirty && <p className="agent-warning">Ungespeicherte Briefänderungen zuerst speichern. Kein Vorschlag darf diese unbemerkt überschreiben.</p>}
    <div className="agent-storyline" hidden={presentation}><span>1 · Agent liest die verteilten Quellen</span><span>2 · Fehlenden Plan im Demo-KIS freigeben</span><span>3 · Erneut prüfen & Änderungen vergleichen</span><span>4 · Geprüften Entwurf zurückgeben</span></div>
    {error && <div className="message error" role="alert">{error} Bitte Fall/KIS-Stand neu laden.</div>}
    {notice?.revision === encounter.revision && (!guided || notice.text.startsWith('Vorschlag verworfen')) && <div className="message success" role="status">{notice.text}</div>}
    {run?.error && presentation && (!guided || run.source_version === encounter.source_version) && <div className="agent-warning" role="alert"><strong>Kein Brief verändert.</strong><p>{run.error}</p></div>}
    {run && <div className="agent-results" hidden={presentation && (scene === 'sources' || scene === 'handover'
      || (scene === 'review' && run.status !== 'awaiting_approval')
      || (guided && scene === 'review' && (proposalStale || dirty))
      || (guided && (run.source_version !== encounter.source_version
        || (scene !== 'agent' && !['medication', 'initial-letter', 'letter', 'update'].includes(guidedStage ?? '')))))}>
      <div className="agent-run-heading" hidden={guided}><strong>{statusLabels[run.status]}</strong>
        <label hidden={presentation}>Auftrag <select value={run.id} onChange={e => { setSelectedRun(e.target.value); setAction(null); setConfirmed(false) }}>
          {runs.map(item => <option key={item.id} value={item.id}>{new Date(item.created_at).toLocaleTimeString('de-DE')} · {statusLabels[item.status]}</option>)}
        </select></label>
        <span hidden={presentation}>Quellenstand {run.source_version}</span>
      </div>
      {presentation && scene === 'agent' && !(guided && ['start', 'medication'].includes(guidedStage ?? ''))
        && <CompactActivity run={run} onShowSource={onShowSource} compact={guided} />}
      <div className="agent-output-grid">
        {!guided && <div hidden={presentation && scene !== 'agent'}>{trace}</div>}
        <div className="agent-proposal" hidden={presentation && scene !== 'review'}>
          {run.error ? <div className="agent-warning"><strong>Kein Brief verändert.</strong><p>{run.error}</p></div>
            : run.proposal ? <>
              <div className="eyebrow">VORSCHLAG · NICHT AUTOMATISCH ÜBERNOMMEN</div>
              <h3>{guided ? guidedStage === 'update' ? 'Aktualisierter Briefvorschlag' : 'Briefvorschlag zur Prüfung'
                : firstDraft ? 'Ihr Entlassbrief-Entwurf' : 'Vorgeschlagene Änderungen'}</h3>
              {guided ? <details className="guided-proof"><summary>Zusammenfassung des Agenten ansehen</summary><p>{run.proposal.summary}</p></details>
                : <p>{run.proposal.summary}</p>}
              <p className="muted small">{!presentation && `${run.proposal.duration_seconds.toFixed(1)} Sekunden · `}{run.proposal.changed_section_ids.length} neue oder geänderte Abschnitte · Quellen geprüft, keine klinische Validierung.</p>
              {!guided && run.proposal.next_actions.length > 0 && <details className="agent-next" open={presentation ? undefined : true}><summary>Nächste menschliche Schritte</summary><ul>{run.proposal.next_actions.map((item, i) => <li key={i}>{item}</li>)}</ul></details>}
              {run.proposal.sections.map(section => {
                const before = run.base_sections.find(item => item.id === section.id)
                const changed = run.proposal!.changed_section_ids.includes(section.id)
                const staleSources = run.source_version !== encounter.source_version
                const warnings = findingsForSection(encounter.findings, section.id)
                return <details className={`section-comparison${warnings.length || staleSources ? ' has-section-warnings' : ''}`} key={section.id} open={guided ? section.id === focusSection : changed && section.id === 'medication'}>
                  <summary>{section.title}{(warnings.length > 0 || staleSources) && <span className="section-warning-badge"><CircleAlert size={12} aria-hidden="true" />{staleSources ? 'Quellenstand prüfen' : 'Offener Sachverhalt'}</span>}<EvidenceShortcut citations={section.citations} onCitation={onCitation} /><span className={`pill ${changed ? 'amber' : 'teal'}`}>{changed ? before ? 'Geändert' : 'Neu' : 'Unverändert'}</span></summary>
                  <div className={`comparison-grid${before ? '' : ' no-baseline'}`}><div><strong>Bisheriger Stand</strong><p>{before?.text ?? 'Noch kein Entwurf vorhanden.'}</p></div><div><strong>Agentenvorschlag</strong>
                    <SectionWarnings findings={warnings} stale={staleSources} onShowFinding={onShowFinding} /><p>{section.text}</p>
                    <CitationLinks citations={section.citations} documents={encounter.documents} onCitation={onCitation} />
                  </div></div>
                </details>
              })}
              <p className="proposal-review-note">{firstDraft ? 'Alle sechs Abschnitte sind oben einsehbar und werden als erster bearbeitbarer Entwurf gespeichert.' : 'Alle sechs Abschnitte sind oben einsehbar und ersetzen bei der Übernahme den bisherigen Entwurf.'} Bitte den vollständigen Vorschlag prüfen.</p>
              {run.status === 'awaiting_approval' && !(guided && guidedStage === 'medication') && <>
                {proposalStale && <p className="agent-warning">Fall seit dem Auftrag geändert. Alten Vorschlag nicht übernehmen; KIS-Stand laden und Agent neu starten.</p>}
                <div className="agent-decision-actions" hidden={guided && Boolean(action)}><button className="button primary" disabled={blocked || proposalStale} onClick={() => void prepareAction('accept')}><CheckCheck size={15} />{firstDraft ? 'Entwurf prüfen & übernehmen' : 'Änderungen prüfen & übernehmen'}</button>
                  <button className="button" disabled={blocked} onClick={() => void prepareAction('reject')}>Verwerfen</button></div>
              </>}
            </> : <div className="agent-empty"><Bot size={38} /><h3>Der Brief bleibt unverändert.</h3><p>Der Agent erhält zunächst nur den Fallauftrag. Dokumentinhalte muss er über seine Werkzeuge beschaffen. Anschließend erscheint hier sein Vorschlag.</p></div>}
        </div>
      </div>
    </div>}
    {presentation && scene === 'agent' && !run && <div className="agent-empty"><Bot size={32} /><h3>Noch kein Agentenauftrag.</h3><p>„Agentenauftrag starten“ ruft Foundry auf. Erst dann erscheinen hier tatsächliche Ereignisse.</p></div>}
    <div className="agent-writeback" hidden={presentation && (scene !== 'handover' || (guided && encounter.status !== 'approved'))}><div><ShieldCheck size={18} /><span><strong>Rückgabe an das Demo-KIS</strong><small>Erst Brief prüfen und Demo-Freigabe erteilen. Danach ausdrücklich eine unveränderliche Kopie speichern. Kein autonomer Schreibzugriff.</small></span></div>
      {savedCopy && <section className="handover-complete" role="status"><CheckCheck size={28} /><div>
        <h3>Übergabe abgeschlossen · Brief im Demo-KIS gespeichert</h3>
        <p>{new Date(savedCopy.at).toLocaleString('de-DE')} · {savedCopy.reviewer} · Quellenstand {savedCopy.source_version}</p>
        <p>Unveränderliche Kopie. Keine klinische Signatur und kein Versand an ein echtes KIS.</p>
      </div></section>}
      <button className={guided && !savedCopy ? 'button primary' : 'button'} hidden={guided && Boolean(action)} disabled={blocked || Boolean(savedCopy) || encounter.status !== 'approved' || encounter.draft?.source_version !== encounter.source_version} onClick={() => void prepareAction('writeback')}>{savedCopy ? 'Aktueller Brief bereits übergeben' : 'Geprüften Entwurf ins Demo-KIS'}</button>
      {writebackReason && <p className="writeback-reason">{writebackReason}</p>}
      <a className={savedCopy ? 'button primary' : 'text-button'} href={`${kisUrl}#briefablage`}>{savedCopy ? 'Gespeicherten Brief im Demo-KIS ansehen →' : 'Briefablage im Demo-KIS ansehen →'}</a>
      {encounter.kis.letters.length > 0 && <span className="pill teal">{encounter.kis.letters.length} {encounter.kis.letters.length === 1 ? 'gespeicherter Briefstand' : 'gespeicherte Briefstände'}</span>}
    </div>
    {action && <div className="human-confirmation" ref={confirmationRef}
      hidden={!guided && presentation && (action === 'writeback' ? scene !== 'handover' : scene !== 'review')}>
      <h3>{action === 'accept' ? firstDraft ? 'Ersten bearbeitbaren Entwurf speichern' : 'Änderungen in den Entwurf übernehmen' : action === 'reject' ? 'Vorschlag verwerfen' : 'Kopie im simulierten KIS speichern'}</h3>
      <p>{action === 'accept' ? `${firstDraft ? 'Alle sechs angezeigten Abschnitte werden erstmals als Entwurf gespeichert.' : 'Alle sechs bisherigen Abschnitte werden durch den angezeigten Vorschlag ersetzt. Die Gegenüberstellung bezieht sich auf den Stand beim Auftrag.'} Keine Demo-Freigabe oder Signatur.` : action === 'reject' ? 'Der bestehende Brief bleibt unverändert.' : 'Nur lokale Demo-Ablage. Nicht klinisch signiert und an kein echtes System gesendet.'}</p>
      {error && <div className="message error" role="alert">{error}<button className="button" disabled={busy} onClick={onReload}>KIS-Stand laden</button></div>}
      <label>Prüfername (mindestens 2 Zeichen)<input value={reviewer} onChange={e => setReviewer(e.target.value)} maxLength={100} /></label>
      <label className="confirmation-checkbox"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Ich habe die angezeigte Aktion geprüft und bestätige sie ausdrücklich.</label>
      <div className="inline-actions"><button className="button" disabled={busy} onClick={() => setAction(null)}>Abbrechen</button><button className="button primary" disabled={blocked || !confirmed || reviewer.trim().length < 2 || (action === 'accept' && proposalStale)} onClick={() => void commit()}>Bestätigen</button></div>
    </div>}
    {guided && run && <details className="guided-agent-evidence"><summary>Agentenaktivität und Quellen ansehen</summary>
      {run.source_version !== encounter.source_version && <p>Dieser Auftrag gehört zu Quellenstand {run.source_version}; aktuell ist Stand {encounter.source_version}.</p>}
      {!guidedWaiting && <CompactActivity run={run} onShowSource={onShowSource} compact />}
      {trace}
    </details>}
  </section>
}
