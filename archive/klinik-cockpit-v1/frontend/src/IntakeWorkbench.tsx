import { useEffect, useRef, useState } from 'react'
import { Bot, CheckCheck, FileScan, FlaskConical, LoaderCircle } from 'lucide-react'
import { api, ApiError } from './api'
import CitationLinks from './CitationLinks'
import type { AgentRun, Citation, DocumentIntake, Encounter, Health, ScanRegion } from './types'
import type { IntakeFocus } from './demoStory'

const fieldLabels: Record<string, string> = {
  PatientName: 'Name', CaseId: 'Fallnummer', DocumentDate: 'Dokumentdatum',
  FollowupRecommendation: 'Erkannte Nachverfolgungsempfehlung',
}
export const taskStatus = {
  waiting_for_result: 'Wartet auf Abschlussbefund',
  awaiting_review: 'Befund eingetroffen · menschliche Prüfung ausstehend',
  completed: 'Menschlich geprüft und abgeschlossen',
}

export function ScanPreview({ caseId, intake, regions = [] }: {
  caseId: string; intake: Pick<DocumentIntake, 'id' | 'page_count'>; regions?: ScanRegion[]
}) {
  const [page, setPage] = useState(regions[0]?.page ?? 1)
  const [failed, setFailed] = useState(false)
  const zoomRef = useRef<HTMLDialogElement>(null)
  useEffect(() => { setPage(regions[0]?.page ?? 1); setFailed(false) }, [intake.id, regions[0]?.page])
  const sheet = () => <div className="scan-sheet"><img alt={`Synthetischer Originalscan, Seite ${page}`} onError={() => setFailed(true)}
    src={`/api/cases/${caseId}/intakes/${intake.id}/pages/${page}`} />
    {regions.filter(region => region.page === page).map((region, index) => <span key={index}
      className="scan-region" aria-hidden="true" style={{
        left: `${region.x * 100}%`, top: `${region.y * 100}%`,
        width: `${Math.min(region.width, 1 - region.x) * 100}%`,
        height: `${Math.min(region.height, 1 - region.y) * 100}%`,
      }} />)}
  </div>
  return <div className="scan-preview">
    {intake.page_count > 1 && <label>Originalseite<select value={page} onChange={e => { setPage(Number(e.target.value)); setFailed(false) }}>
      {Array.from({ length: intake.page_count }, (_, index) => <option key={index} value={index + 1}>Seite {index + 1}</option>)}
    </select></label>}
    {sheet()}
    <button type="button" className="text-button" onClick={() => zoomRef.current?.showModal()}>Original mit Fundstelle groß ansehen</button>
    <dialog className="scan-zoom" ref={zoomRef} aria-label="Vergrößerter Originalscan">
      <button type="button" className="button" onClick={() => zoomRef.current?.close()}>Originalansicht schließen</button>
      {sheet()}
    </dialog>
    {failed && <p className="message error" role="alert">Originalseite konnte nicht geladen werden. Keine Prüfung anhand einer fehlenden Vorschau bestätigen.</p>}
    <p className="muted small">{regions.length ? 'Gelbe Markierung: Fundstelle des ausgewählten Felds aus Azure, keine medizinische Warnung. Ein anderes Feld verschiebt die Markierung.' : 'Keine Fundstelle ausgewählt. Erkannte Angaben einzeln anklicken.'} OCR und Extraktion können fehlerhaft sein.</p>
  </div>
}

type Action = { kind: 'source' | 'task' | 'complete' | 'retry-scan' | 'retry-event' | 'automation'; id: string; revision: number }

export default function IntakeWorkbench({ encounter, health, run, blocked, onBusy, onChange, onEnsureCurrent,
  onActionChange, onCitation, guided, focus, onOpen }: {
  encounter: Encounter; health: Health | null; run: AgentRun | null; blocked: boolean
  onBusy: (label: string) => void; onChange: (value: Encounter) => void
  onEnsureCurrent: () => Promise<boolean>; onActionChange: (pending: boolean) => void
  onCitation: (value: Citation) => void
  guided: boolean; focus?: IntakeFocus; onOpen: () => void
}) {
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [synthetic, setSynthetic] = useState(false)
  const [action, setAction] = useState<Action | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [monitor, setMonitor] = useState(false)
  const [reviewer, setReviewer] = useState('Demo-Prüfer(in)')
  const [role, setRole] = useState('ward-team')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [selectedField, setSelectedField] = useState('FollowupRecommendation')
  const fileRef = useRef<HTMLInputElement>(null)
  const confirmRef = useRef<HTMLDivElement>(null)
  const intake = encounter.intakes.find(item => item.id === selectedId) ?? encounter.intakes.at(-1)
  const followup = run?.proposal?.followup
  const currentProposal = run?.status === 'awaiting_approval' && run.base_revision === encounter.revision
  const lab = encounter.documents.find(doc => doc.kind === 'Mikrobiologie')
  const running = run?.status === 'running'
  const hasStory = encounter.intakes.length > 0
  const latestEvent = encounter.event_automation.events.at(-1)
  const actionStale = Boolean(action && action.revision !== encounter.revision)
  const expanded = open || guided || Boolean(action || file)
  const task = encounter.followup_tasks[0]
  const followupTitle = task ? task.status === 'waiting_for_result'
    ? 'Zuständigkeit bestätigt · wartet auf Abschlussbefund'
    : task.status === 'awaiting_review' ? 'Abschlussbefund eingetroffen · menschliche Prüfung offen'
      : 'Nachverfolgung menschlich abgeschlossen'
    : followup?.action === 'none' ? 'Keine zusätzliche Nachverfolgung vorgeschlagen'
      : followup?.title ?? 'Befundnachverfolgung'

  useEffect(() => { onActionChange(Boolean(action || file)) }, [action, file, onActionChange])
  useEffect(() => {
    setConfirmed(false)
    if (action) setError('Fallstand geändert. Angaben nochmals prüfen und Bestätigung erneuern.')
  }, [encounter.revision])
  useEffect(() => {
    if (action) confirmRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [action])

  function selectFile(value: File | null) {
    setError(''); setSynthetic(false)
    if (value && value.size > 5 * 1024 * 1024) {
      setError('Datei überschreitet 5 MiB.'); return
    }
    setFile(value)
  }

  async function sample() {
    onBusy('Synthetischen Scan vorbereiten'); setError('')
    try {
      const response = await fetch(`/api/cases/${encounter.id}/sample-scan.png`)
      if (!response.ok) throw new Error('Vorbereiteter Scan konnte nicht geladen werden.')
      selectFile(new File([await response.blob()], `Konsilbericht-${encounter.id}.png`, { type: 'image/png' }))
    } catch (err) { setError(err instanceof Error ? err.message : 'Scan nicht verfügbar.') }
    finally { onBusy('') }
  }

  async function upload() {
    if (!file || !synthetic || blocked || !await onEnsureCurrent()) return
    onBusy('Scan zur echten Azure-Analyse senden'); setError(''); setNotice('')
    try {
      const query = new URLSearchParams({ revision: String(encounter.revision), synthetic_only: 'true', filename: file.name })
      const updated = await api<Encounter>(`/cases/${encounter.id}/intakes?${query}`, {
        method: 'POST', headers: { 'Content-Type': file.type }, body: file,
      })
      onChange(updated); setFile(null); setSynthetic(false)
      if (fileRef.current) fileRef.current.value = ''
      setSelectedId(updated.intakes.at(-1)?.id ?? '')
      setNotice('Datei gespeichert. Azure analysiert den tatsächlichen Scan. Noch keine Quelle übernommen.')
    } catch (err) {
      setSynthetic(false)
      setError(err instanceof Error ? err.message : 'Dokument konnte nicht gesendet werden.')
    } finally { onBusy('') }
  }

  async function prepare(kind: Action['kind'], id: string) {
    if (blocked || !await onEnsureCurrent()) return
    setAction({ kind, id, revision: encounter.revision }); setConfirmed(false); setError(''); setNotice('')
    if (kind === 'source') setMonitor(encounter.event_automation.enabled)
    if (kind === 'task') setRole(followup?.role_id ?? 'ward-team')
  }

  async function recheck() {
    if (!action || !await onEnsureCurrent()) return
    setAction({ ...action, revision: encounter.revision }); setConfirmed(false); setError('')
  }

  async function commit() {
    if (!action || actionStale || !confirmed || reviewer.trim().length < 2 || blocked) return
    if (!await onEnsureCurrent()) { setConfirmed(false); return }
    const root = `/cases/${encounter.id}`
    const path = action.kind === 'source' ? `${root}/intakes/${action.id}/accept`
      : action.kind === 'retry-scan' ? `${root}/intakes/${action.id}/retry`
        : action.kind === 'task' ? `${root}/agent-runs/${action.id}/task`
          : action.kind === 'complete' ? `${root}/tasks/${action.id}/complete`
            : action.kind === 'retry-event' ? `${root}/events/${action.id}/retry` : `${root}/automation`
    onBusy('Bestätigte Demo-Aktion speichern'); setError('')
    try {
      const updated = await api<Encounter>(path, { method: 'POST', body: JSON.stringify({
        revision: encounter.revision, reviewer, confirmed: true,
        ...(action.kind === 'source' ? { synthetic_only: true, monitor_events: monitor } : {}),
        ...(action.kind === 'task' ? { role_id: role } : {}),
        ...(action.kind === 'automation' ? { enabled: !encounter.event_automation.enabled } : {}),
      }) })
      onChange(updated); setAction(null); setConfirmed(false)
      setNotice(action.kind === 'task'
        ? 'Aufgabe bestätigt. Die neue Zuständigkeit ist eine eigene Quelle. Der bisherige Vorschlag wird nicht stillschweigend übernommen.'
        : action.kind === 'source' ? 'Scan als Quelle übernommen. Altbrief unverändert; aktueller Entwurf muss erneut geprüft werden.'
          : action.kind === 'complete' ? 'Aufgabe nach ausdrücklicher menschlicher Befundprüfung abgeschlossen. Kein automatischer klinischer Abschluss.'
            : 'Demo-Aktion gespeichert. Eine laufende Inferenz wird nicht zurückgerufen.')
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setConfirmed(false)
      setError(err instanceof Error ? err.message : 'Bestätigung fehlgeschlagen.')
    } finally { onBusy('') }
  }

  return <section className="intake-workbench" aria-label="Dokumenteingang und Befundnachverfolgung">
    <div className="intake-heading" hidden={guided}><div><div className="eyebrow">DIE AKTE LEBT WEITER</div>
      <h2><FileScan size={22} />{hasStory ? 'Neuer Hinweis. Neue Verantwortung.' : 'Was passiert nach der Übergabe?'}</h2>
      <p>{hasStory ? 'Scan, Labor und Nachverfolgung verbinden – ohne den alten Brief zu überschreiben.' : 'Ein Scan trifft ein. Der Agent gleicht ihn mit Labor und Aufgaben ab.'}</p>
    </div><button className="button" aria-expanded={expanded} disabled={Boolean(action || file)} onClick={() => { if (!open) onOpen(); setOpen(value => !value) }}>
      {expanded ? 'Details ausblenden' : hasStory ? 'Dokument & Nachverfolgung öffnen' : 'Neues Dokument einlesen'}
    </button></div>
    {hasStory && !guided && <div className="impact-summary" aria-live="polite">
      <span><strong>{encounter.intakes.filter(item => item.status === 'accepted').length}</strong> bestätigte Scanquelle(n)</span>
      <span><strong>{lab?.status === 'available' ? 'Befund verfügbar' : 'Befund ausstehend'}</strong> Simuliertes LIS</span>
      <span><strong>{encounter.followup_tasks[0] ? taskStatus[encounter.followup_tasks[0].status] : 'Noch keine Aufgabe bestätigt'}</strong> Demo-Aufgabenmanagement</span>
      {encounter.kis.letters.length > 0 && <p>Bereits übergebene Briefkopien bleiben unverändert. Neue Informationen erfordern eine neue Prüfung.</p>}
    </div>}
    {expanded && <div className="intake-content">
      {error && <div className="message error" role="alert">{error}</div>}
      {notice && !guided && <p className="message success" role="status">{notice}</p>}
      {action ? <div className="human-confirmation" ref={confirmRef}>
        <h3>{action.kind === 'source' ? 'Scan als neue Quelle bestätigen' : action.kind === 'task' ? 'Nachverfolgung verbindlich zuordnen'
          : action.kind === 'complete' ? 'Befund und Dokumentation menschlich geprüft' : action.kind === 'automation' ? 'Ereignisprüfung ändern' : 'Echten Azure-Aufruf erneut starten'}</h3>
        <p>{action.kind === 'source' ? 'Name, Fallnummer, erkannte Absätze und markierte Fundstellen am Original prüfen. OCR kann falsch sein. Der Entwurf wird veraltet, alte KIS-Kopien bleiben unverändert.'
          : action.kind === 'task' ? 'Nur die lokale Demo-Aufgabe wird angelegt. Eine neue echte Agentenprüfung berücksichtigt anschließend die bestätigte Zuständigkeit, wenn Ereignisprüfung aktiviert ist.'
            : action.kind === 'complete' ? 'Ich habe den eingetroffenen Abschlussbefund und die aktuelle Dokumentation fachlich geprüft. Dies ist nur ein menschlicher Demo-Aufgabenabschluss.'
              : 'Ereignisprüfung bedeutet zusätzliche echte Foundry-Aufrufe durch den lokalen Server. Kein autonomes Übernehmen, Signieren oder Versenden. Ausschalten widerruft keine bereits laufende Inferenz.'}</p>
        {action.kind === 'task' && <label>Zuständige Rolle<select value={role} onChange={e => setRole(e.target.value)}>
          {health?.followup_roles.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select></label>}
        {action.kind === 'source' && <label className="confirmation-checkbox"><input type="checkbox" checked={monitor} onChange={e => setMonitor(e.target.checked)} />
          Neue Quellen automatisch mit Agent prüfen.
        </label>}
        {action.kind === 'source' && <p>Nur mit dieser zusätzlichen Zustimmung lösen neue bestätigte Quellen, Aufgaben und spätere Laborbefunde echte Agentenläufe aus. Zusätzliche Modellaufrufe; Brief und Aufgaben werden nie automatisch übernommen. Ohne Zustimmung den Agenten jeweils manuell starten.</p>}
        <label>Prüfername (mindestens 2 Zeichen)<input value={reviewer} onChange={e => setReviewer(e.target.value)} maxLength={100} /></label>
        <label className="confirmation-checkbox"><input type="checkbox" checked={confirmed} disabled={actionStale} onChange={e => setConfirmed(e.target.checked)} />
          Ich habe die Angaben geprüft und bestätige diese synthetische Demo-Aktion ausdrücklich.
        </label>
        {actionStale && <button className="button" disabled={blocked} onClick={() => void recheck()}>Aktuellen Stand prüfen</button>}
        <div className="inline-actions"><button className="button" disabled={blocked} onClick={() => { setAction(null); setConfirmed(false); setError('') }}>Abbrechen</button>
          <button className="button primary" disabled={blocked || !confirmed || actionStale || reviewer.trim().length < 2} onClick={() => void commit()}>Bestätigen</button></div>
      </div> : <div hidden={guided && Boolean(focus) && focus !== 'scan'}>
        {encounter.intakes.length < 4 && <details className="scan-upload" open={!intake || Boolean(file)}>
          <summary>{intake ? 'Weiteres Dokument einlesen' : 'Dokument auswählen'}</summary>
          <p>Synthetisches PDF, PNG oder JPEG auswählen. Analyse mit Azure Content Understanding; maximal 5 MiB und drei Seiten.</p>
          {!health?.document_analysis.configured && <p className="agent-warning">Azure-Dokumentanalyse nicht konfiguriert. Kein Ersatz-OCR.</p>}
          <div className="inline-actions"><button className={guided && !file && !intake ? 'button primary' : 'button'} disabled={blocked} onClick={() => void sample()}><FlaskConical size={15} />Beispielscan auswählen</button>
            <label className="button file-picker">Eigene synthetische Datei<input ref={fileRef} type="file" accept="application/pdf,image/png,image/jpeg"
              disabled={blocked} onChange={e => selectFile(e.target.files?.[0] ?? null)} /></label></div>
          {file && <><p><strong>{file.name}</strong> · {(file.size / 1024).toFixed(0)} KiB</p>
            <label className="confirmation-checkbox"><input type="checkbox" checked={synthetic} onChange={e => setSynthetic(e.target.checked)} />
              Ausschließlich synthetische Daten. Diese Datei darf zur Analyse an Azure gesendet werden; globale Verarbeitung ist für diese Demo erlaubt.
            </label><div className="inline-actions"><button className="button primary" disabled={blocked || !synthetic || !health?.document_analysis.configured} onClick={() => void upload()}>Scan mit Azure analysieren</button>
              <button className="button" disabled={blocked} onClick={() => { selectFile(null); if (fileRef.current) fileRef.current.value = '' }}>Datei verwerfen</button></div></>}
        </details>}
        {intake && <article className="intake-review">
          <div className="intake-selection"><h3>Original und erkannte Angaben</h3>
            {encounter.intakes.length > 1 && <label>Dokumenteingang<select value={intake.id} onChange={e => { setSelectedId(e.target.value); setSelectedField('FollowupRecommendation') }}>
              {encounter.intakes.map(item => <option key={item.id} value={item.id}>{item.filename} · {item.status === 'accepted' ? 'übernommen' : item.status === 'ready' ? 'zur Prüfung' : item.status === 'failed' ? 'fehlgeschlagen' : 'Analyse läuft'}</option>)}
            </select></label>}</div>
          {intake.status === 'analyzing' && <p role="status"><LoaderCircle size={17} className="spin" />Dokumentanalyse läuft. Die Quelle ist noch nicht bestätigt.</p>}
          {intake.status === 'failed' && <div className="agent-warning" role="alert"><p>{intake.error}</p>
            <button className="button" disabled={blocked} onClick={() => void prepare('retry-scan', intake.id)}>Analyse ausdrücklich erneut starten</button></div>}
          {intake.extraction && <details className="scan-result-details" open={intake.status === 'accepted' ? undefined : true}>
            <summary>{intake.status === 'accepted' ? 'Bestätigter Scan · Original und Fundstellen bei Bedarf ansehen' : 'Analyseergebnis mit dem Original abgleichen'}</summary>
            <div className="intake-evidence-grid"><div>
            <p className={intake.extraction.matched ? 'pill teal' : 'agent-warning'}>{intake.extraction.match_note}</p>
            {Object.entries(intake.extraction.fields).map(([name, value]) => <button type="button" className={`extracted-field${selectedField === name ? ' selected' : ''}`} key={name} onClick={() => setSelectedField(name)}>
              <strong>{fieldLabels[name] ?? name}</strong><span>{value.value || 'Nicht erkannt'}</span>
              <small>{value.confidence === null || value.confidence === undefined ? 'Keine Extraktionskonfidenz geliefert' : `Extraktionskonfidenz ${Math.round(value.confidence * 100)} %${value.confidence < 0.8 ? ' · besonders sorgfältig prüfen' : ''}`} · {value.regions.length ? 'Fundstelle ansehen →' : 'Keine genaue Fundstelle geliefert'}</small>
            </button>)}
            <p className="muted small">Extraktionskonfidenz ist keine medizinische Sicherheit. Die Agentenquelle besteht aus den geprüften OCR-Absätzen, nicht aus frei erzeugten Feldern.</p>
            <details><summary>Alle erkannten Originalabsätze prüfen</summary>{intake.extraction.paragraphs.map(paragraph => <p key={paragraph.id}><strong>{paragraph.id.toUpperCase()}</strong> · {paragraph.text}</p>)}</details>
            {intake.status === 'ready' && <button className="button primary" disabled={blocked || !intake.extraction.matched || running} onClick={() => void prepare('source', intake.id)}>Geprüften Scan als Quelle übernehmen</button>}
            {intake.status === 'accepted' && <p className="pill teal"><CheckCheck size={14} />Als Quelle bestätigt · {intake.reviewer}</p>}
          </div><ScanPreview caseId={encounter.id} intake={intake} regions={intake.extraction.fields[selectedField]?.regions} /></div></details>}
        </article>}
      </div>}
      {hasStory && <section className="agent-impact" hidden={guided && focus === 'scan'}>
        <div className="eyebrow" hidden={guided}>3 · DER AGENT VERBINDET DIE SYSTEME</div>
        <h3 hidden={guided}><Bot size={20} />{running ? 'Neue Situation wird tatsächlich geprüft …' : followupTitle}</h3>
        {run?.trigger && !guided && <p>Auslöser dieses Auftrags: <strong>{run.trigger.title}</strong></p>}
        {followup && currentProposal && <>
          {guided && focus === 'responsibility' && followup.action === 'create' && <article className="followup-task">
            <span className="pill amber">Agentenvorschlag · noch keine Aufgabe angelegt</span>
            <h4>{followup.title}</h4>
            <p>Der Abschlussbefund steht aus. Erst Ihre Bestätigung legt eine Aufgabe an; die zuständige Rolle wählen Sie im nächsten Schritt.</p>
          </article>}
          {guided ? <details className="guided-proof"><summary>Begründung und Originalquellen ansehen</summary>
            <p>{followup.action === 'none' && task ? followupTitle : followup.reason}</p>
            <CitationLinks citations={followup.citations} documents={encounter.documents} onCitation={onCitation} />
          </details> : <><p>{followup.action === 'none' && task ? followupTitle : followup.reason}</p>
            <CitationLinks citations={followup.citations} documents={encounter.documents} onCitation={onCitation} /></>}
          {followup.action === 'create' && !encounter.followup_tasks.length && <button className="button primary" disabled={blocked || Boolean(action)} onClick={() => void prepare('task', run!.id)}>Vorgeschlagene Nachverfolgung bestätigen</button>}
          {followup.action === 'create' && <p className="muted small">Nach bestätigter Zuordnung ist eine erneute Quellenprüfung erforderlich. Die Zuständigkeit wird dabei als neue Quelle berücksichtigt.</p>}
        </>}
        {encounter.followup_tasks.map(task => <article className={`followup-task task-${task.status}`} key={task.id}>
          <span className={`pill ${task.status === 'completed' ? 'teal' : 'amber'}`}>{taskStatus[task.status]}</span>
          <h4>{task.title}</h4><p><strong>{task.role_label}</strong> · ausdrücklich bestätigt durch {task.reviewer}</p>
          {task.status === 'awaiting_review' && <><p>Ein eingetroffener Befund schließt diese Aufgabe nicht automatisch. Erst aktuellen Briefvorschlag übernehmen, dann Befund und Dokumentation prüfen.</p>
            <button className={guided && focus === 'complete' ? 'button primary' : 'button'} disabled={blocked || Boolean(action) || running || !encounter.draft || encounter.draft.source_version !== encounter.source_version} onClick={() => void prepare('complete', task.id)}>Befund geprüft · Aufgabe abschließen</button></>}
          {task.status === 'completed' && <p>Abgeschlossen durch {task.completed_by}. Keine klinische Signatur.</p>}
        </article>)}
        {!encounter.event_automation.enabled && <p className="agent-warning">Ereignisprüfung ist ausgeschaltet. Neue Quellen manuell mit „Quellen mit Agent erneut prüfen“ prüfen.</p>}
        <details className="event-settings"><summary>Ereignisprüfung · {encounter.event_automation.enabled ? 'aktiv' : 'aus'} · echte lokale Auslöser</summary>
          <p>Der lokale Python-Server startet den vorhandenen Foundry-Agenten bei bestätigten neuen Quellen. Kein dauerhaft selbstständig laufendes Modell und keine Foundry-Routine.</p>
          {latestEvent?.error && <p className="message error" role="alert">{latestEvent.error}</p>}
          {latestEvent?.status === 'failed' && <button className="button" disabled={blocked || Boolean(action) || !encounter.event_automation.enabled} onClick={() => void prepare('retry-event', latestEvent.id)}>Ereignisprüfung erneut bestätigen</button>}
          <button className="button" disabled={blocked || Boolean(action)} onClick={() => void prepare('automation', encounter.id)}>{encounter.event_automation.enabled ? 'Ereignisprüfung ausschalten' : 'Ereignisprüfung aktivieren'}</button>
        </details>
      </section>}
    </div>}
  </section>
}
