import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Database, FileText, FlaskConical, RefreshCw, ShieldCheck } from 'lucide-react'
import { api, ApiError } from './api'
import type { CaseSummary, Encounter, SourceDocument } from './types'
import { usePresentationMode, ViewModeToggle } from './Presentation'
import { useNavigationGuard, useWorkspaceSync } from './useWorkspaceSafety'
import { taskStatus } from './IntakeWorkbench'
import { deriveKisGuide } from './demoStory'

type KisView = { case: Encounter; prepared_medication: SourceDocument | null }
type Action = 'release-medication' | 'release-report' | 'retrieval-fault'

export default function KisApp() {
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [selected, setSelected] = useState(new URLSearchParams(window.location.search).get('case') ?? 'DEMO-031')
  const [presentation, setPresentation] = usePresentationMode(selected)
  const [data, setData] = useState<KisView | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [action, setAction] = useState<Action | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [reviewer, setReviewer] = useState('Demo-Prüfer(in)')
  const confirmationRef = useRef<HTMLElement>(null)
  const receiptsRef = useRef<HTMLElement>(null)
  const encounter = data?.case
  const guide = encounter ? deriveKisGuide(encounter) : null
  const live = useRef({ data, busy, action })
  live.current = { data, busy, action }
  const checking = useRef(false)
  const actionUnavailable = action === 'release-medication' && encounter?.kis.medication_released
    || action === 'release-report' && !encounter?.documents.some(doc => doc.kind === 'Mikrobiologie' && doc.status === 'pending')

  useNavigationGuard(Boolean(action), busy, setError)
  useWorkspaceSync(() => checkCurrent())

  async function checkCurrent(allowUpdated = false): Promise<boolean> {
    const before = live.current
    if (!before.data || before.busy || checking.current) return false
    checking.current = true
    try {
      const view = await api<KisView>(`/kis/cases/${before.data.case.id}`)
      const current = live.current
      if (!current.data || current.busy || current.data.case.id !== view.case.id) return false
      if (view.case.revision < current.data.case.revision) return false
      if (view.case.revision === current.data.case.revision) {
        if (JSON.stringify(view.case.event_automation) !== JSON.stringify(current.data.case.event_automation))
          setData(view)
        setError(value => value.startsWith('Synchronisation:') ? '' : value)
        return true
      }
      setData(view); setConfirmed(false)
      setNotice('KIS-Stand aus der anderen Ansicht aktualisiert. Keine Quelle automatisch freigegeben.')
      if (current.action) setError('Der Fallstand wurde geändert. Bitte die aktuelle Aktion erneut prüfen und das Bestätigungsfeld erneut aktivieren.')
      return allowUpdated && !current.action
    } catch (err) {
      setError(`Synchronisation: ${err instanceof Error ? err.message : 'KIS-Stand konnte nicht geladen werden.'}`)
      return false
    } finally { checking.current = false }
  }

  useEffect(() => { document.title = 'Klinik Studio · Demo-KIS' }, [])

  useEffect(() => {
    if (action) confirmationRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [action])

  useEffect(() => {
    if (data && window.location.hash === '#briefablage') {
      requestAnimationFrame(() => receiptsRef.current?.scrollIntoView({ block: 'start' }))
    }
  }, [data])

  useEffect(() => {
    let active = true
    setData(null); setError(''); setNotice(''); setAction(null); setConfirmed(false)
    Promise.all([api<CaseSummary[]>('/cases'), api<KisView>(`/kis/cases/${selected}`)])
      .then(([items, view]) => { if (active) { setCases(items); setData(view) } })
      .catch((err: Error) => { if (active) setError(err.message) })
    return () => { active = false }
  }, [selected])

  async function reload() {
    setBusy(true); setError('')
    try {
      const view = await api<KisView>(`/kis/cases/${selected}`)
      if (view.case.revision !== encounter?.revision) {
        setConfirmed(false)
        if (action) setError('Fallstand aktualisiert. Bitte die aktuelle Aktion erneut prüfen und bestätigen.')
      }
      setData(view)
    }
    catch (err) { setError(err instanceof Error ? err.message : 'KIS-Stand konnte nicht geladen werden.') }
    finally { setBusy(false) }
  }

  async function choose(value: Action) {
    if (!await checkCurrent(true)) {
      setError(previous => previous || 'Fallstand aktualisiert. Bitte die Quelle prüfen und die gewünschte Aktion erneut öffnen.')
      return
    }
    setAction(value); setConfirmed(false); setNotice(''); setError('')
  }

  async function commit() {
    if (!encounter || !action || !confirmed || reviewer.trim().length < 2 || actionUnavailable) return
    if (!await checkCurrent()) { setConfirmed(false); return }
    setBusy(true); setError(''); setNotice('')
    try {
      const path = action === 'release-report' ? `/cases/${selected}/release-report` : `/kis/cases/${selected}/${action}`
      const body = action === 'release-report' ? { revision: encounter.revision }
        : action === 'retrieval-fault' ? { revision: encounter.revision, enabled: !encounter.kis.retrieval_fault }
          : { revision: encounter.revision, reviewer, confirmed: true }
      const updated = await api<Encounter>(path, { method: 'POST', body: JSON.stringify(body) })
      setError('')
      setData(previous => previous ? {
        ...previous, case: updated, prepared_medication: updated.kis.medication_released ? null : previous.prepared_medication,
      } : previous)
      setAction(null); setConfirmed(false)
      setNotice(action === 'retrieval-fault' ? 'Technische Demo-Abrufstörung umgeschaltet. Ein laufender Auftrag wird nicht stillschweigend mit alten Daten fortgeführt.'
        : action === 'release-report' && updated.event_automation.enabled
          ? 'Befund veröffentlicht. Eine echte Agentenprüfung wird automatisch gestartet. Der Brief bleibt bis zur menschlichen Übernahme unverändert; Aufgaben warten auf Befundprüfung.'
          : action === 'release-medication' && updated.event_automation.enabled
            ? 'Medikationsplan veröffentlicht. Eine echte Agentenprüfung wird automatisch gestartet. Der Brief bleibt bis zur menschlichen Übernahme unverändert.'
          : 'Quelle freigegeben. Der bestehende Brief bleibt unverändert. Zum Cockpit zurückkehren und „Neue Quelle mit Agent prüfen“ wählen.')
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setConfirmed(false)
      setError(err instanceof Error ? err.message : 'KIS-Aktion fehlgeschlagen. Bitte Stand neu laden.')
    }
    finally { setBusy(false) }
  }

  return <div className={`kis-app${presentation ? ' kis-presentation-mode' : ''}`}>
    <header className="kis-topbar"><a href={`/?case=${selected}&view=${presentation ? 'presentation' : 'full'}`} className="button"><ArrowLeft size={15} />Zum Cockpit</a><span><Database size={19} /><strong>Demo-KIS</strong> · Universitätsklinikum Musterstadt</span><span className="pill amber">{presentation ? 'Synthetische Demo · KIS simuliert' : 'SIMULATION'}</span>
      <ViewModeToggle presentation={presentation} onChange={setPresentation} /></header>
    <main>
      <div className="page-heading"><div><div className="eyebrow">QUELLSYSTEM · SEPARATE DEMO-ANSICHT</div><h1>Hier wird aus „fehlt“ eine verfügbare Quelle.</h1><p>Eine bedienbare KIS-Simulation im selben Demo-Backend. Kein echtes Krankenhausinformationssystem.</p></div></div>
      <div className="demo-banner"><FlaskConical size={18} /><span><strong>Vorbereitete synthetische Inhalte.</strong> Keine realen Patientendaten, medizinischen Entscheidungen oder klinischen Freigaben. Der Foundry-Agent hat hier ausschließlich Lesezugriff.</span></div>
      <div className="kis-controls"><label>Aufenthalt<select value={selected} disabled={busy} onChange={e => setSelected(e.target.value)}>{cases.map(item => <option key={item.id} value={item.id}>{item.name} · {item.id}</option>)}</select></label>
        <button className="button" disabled={busy} onClick={() => void reload()}><RefreshCw size={15} />KIS-Stand neu laden</button></div>
      {error && <div className="message error" role="alert">{error}</div>}
      {notice && <div className="message success" role="status">{notice}</div>}
      {encounter && <><section className="patient-card"><div className="patient-identity"><span className="patient-avatar">{encounter.initials}</span><div><h2>{encounter.name}</h2><p className="patient-meta">{encounter.id} · {encounter.department} · Quellenstand {encounter.source_version}</p></div></div><span className="pill subtle">Fiktiver Aufenthalt</span></section>
        {presentation && guide && <section className="kis-guide" aria-live="polite">
          <div className="eyebrow">QUELLSYSTEM · MEDIKATION UND BEFUNDE</div>
          <h1>{guide.title}</h1><p>{guide.next}</p>
          {guide.action === 'return' && !action && <a className="button primary" href={`/?case=${selected}&view=presentation`}>
            <ArrowLeft size={15} />Zurück zum Cockpit</a>}
        </section>}
        <div className="kis-grid"><section className="kis-panel"><div className="eyebrow">DOKUMENTENEINGANG</div><h2>Medikationsmodul und Befunde</h2><p>Erst eine bestätigte Freigabe macht neue Inhalte für die Quellenprüfung verfügbar. Der Brief wird dabei nicht automatisch geändert.</p>
          {data?.prepared_medication ? <article className="kis-prepared"><span className="pill amber">Noch nicht freigegeben · für Agenten gesperrt</span><h3>Entlassmedikationsplan</h3>
            <p className="muted small">Noch nicht freigegebene Version. Medikament und Dosis sind für den Agenten nicht abrufbar.</p>
            {presentation ? <><p>{data.prepared_medication.paragraphs[0]?.text}</p>
              <details className="prepared-source-details"><summary>Vollständigen Plan ansehen</summary>
                {data.prepared_medication.paragraphs.map(p => <p key={p.id}>{p.text}</p>)}
              </details></> : data.prepared_medication.paragraphs.map(p => <p key={p.id}>{p.text}</p>)}
            <button className="button primary" hidden={presentation && Boolean(action)} disabled={busy} onClick={() => void choose('release-medication')}>Medikationsplan freigeben</button>
          </article> : <div className="kis-ready"><ShieldCheck size={19} /><p>Freigegebener Medikationsplan ist als Quelle abrufbar.</p></div>}
          {encounter.documents.some(doc => doc.kind === 'Mikrobiologie' && doc.status === 'pending') && <article className="kis-prepared" hidden={presentation && guide?.action !== 'report' && action !== 'release-report'}><span className="pill amber">Befund ausstehend</span><h3>Mikrobiologischer Abschlussbefund</h3><p>Vorbereiteter synthetischer Abschlussbefund kann jetzt als verspäteter Eingang veröffentlicht werden.</p>
            {encounter.event_automation.enabled && <p>Ereignisprüfung aktiv: Nach Veröffentlichung startet ein neuer echter Foundry-Aufruf. Der Brief wird nicht automatisch geändert.</p>}
            <button className={presentation ? 'button primary' : 'button'} hidden={presentation && Boolean(action)} disabled={busy} onClick={() => void choose('release-report')}>Abschlussbefund bereitstellen</button></article>}
          <details className="kis-fault" hidden={presentation && !encounter.kis.retrieval_fault}
            open={presentation && encounter.kis.retrieval_fault ? true : undefined}><summary>{encounter.kis.retrieval_fault ? 'Abrufstörung aktiv · Simulation' : 'Technischen Fehler demonstrieren'}</summary><p>Die lesenden Agentenwerkzeuge melden bei aktiver Simulation ausdrücklich einen Abruffehler. Das ist keine fehlende Quelle; ein Brief wird daraus nicht erzeugt.</p><strong>{encounter.kis.retrieval_fault ? 'Abrufstörung aktiv' : 'Abruf verfügbar'}</strong><button className="button" disabled={busy} onClick={() => void choose('retrieval-fault')}>{encounter.kis.retrieval_fault ? 'Abrufstörung beenden' : 'Abrufstörung aktivieren'}</button></details>
        </section>
        <details className="kis-panel kis-inventory" open={presentation ? undefined : true}>
          <summary>{encounter.documents.length} Quelldokumente ansehen</summary>
          <p>Dieselben freigegebenen Quelldokumente, die der Agent über seine Werkzeuge abrufen kann. Ein ausstehender Befund enthält nur den Vermerk.</p>
          {encounter.documents.map(doc => <details className="kis-document" key={doc.id}><summary><FileText size={16} /><span>{doc.title}<small>{doc.system}</small></span><span className={`pill ${doc.status === 'pending' ? 'amber' : 'teal'}`}>{doc.status === 'pending' ? 'Ausstehend' : 'Verfügbar'}</span></summary><code>{doc.id}</code>{doc.paragraphs.map(p => <p key={p.id}>{p.text}</p>)}</details>)}
        </details></div>
        {encounter.intakes.length > 0 && <section className="kis-panel kis-followup"><div className="eyebrow">SIMULIERTES LIS & AUFGABENMANAGEMENT</div>
          <h2>Laborstatus und Nachverfolgung</h2>
          <p>Lokale Simulation zweier Krankenhaussysteme. Keine echte KIS-/FHIR-Anbindung.</p>
          <div className="impact-summary"><span><strong>{encounter.documents.find(doc => doc.kind === 'Mikrobiologie')?.status === 'available' ? 'Abschlussbefund verfügbar' : 'Abschlussbefund ausstehend'}</strong>Laborstatus</span>
            <span><strong>{encounter.intakes.filter(item => item.status === 'accepted').length} bestätigte Scans</strong>Dokumenteneingang</span></div>
          {!encounter.followup_tasks.length && <p>Noch keine Nachverfolgungsaufgabe menschlich bestätigt.</p>}
          {encounter.followup_tasks.map(task => <article className="followup-task" key={task.id}><span className={`pill ${task.status === 'completed' ? 'teal' : 'amber'}`}>{taskStatus[task.status]}</span>
            <h3>{task.title}</h3><p><strong>{task.role_label}</strong> · bestätigt durch {task.reviewer}</p><p>Ein späterer Befund ändert nur den Arbeitsstatus. Fachliche Prüfung und Abschluss bleiben beim Menschen im Cockpit.</p></article>)}
        </section>}
        {action && <section className="human-confirmation" ref={confirmationRef}><h3>{action === 'release-medication' ? 'Vorbereiteten Plan veröffentlichen' : action === 'release-report' ? 'Vorbereiteten Befund veröffentlichen' : 'Technische Simulation umschalten'}</h3><p>Sie ändern ausschließlich diesen synthetischen Demo-Aufenthalt. Ein laufender Agentenauftrag kann dadurch veralten. Der bestehende Brief bleibt erhalten.</p>
          {error && <div className="message error" role="alert">{error}<button className="button" disabled={busy} onClick={() => void reload()}>Aktuellen KIS-Stand laden</button></div>}
          {actionUnavailable && <p className="agent-warning">Diese Quelle wurde bereits freigegeben. Bitte die Bestätigung schließen.</p>}
          <label>Prüfername (mindestens 2 Zeichen)<input value={reviewer} onChange={e => setReviewer(e.target.value)} maxLength={100} /></label><label className="confirmation-checkbox"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Ich bestätige diese Demo-Aktion ausdrücklich.</label><div className="inline-actions"><button className="button" disabled={busy} onClick={() => setAction(null)}>Abbrechen</button><button className="button primary" disabled={busy || !confirmed || reviewer.trim().length < 2 || Boolean(actionUnavailable)} onClick={() => void commit()}>Bestätigen</button></div></section>}
        <section className="kis-panel kis-receipts" id="briefablage" ref={receiptsRef}><div className="eyebrow">RÜCKKANAL AUS DEM COCKPIT</div><h2>Übernommene Briefstände</h2><p>Unveränderliche Kopien nach menschlicher Demo-Prüfung und ausdrücklicher Rückgabe. Keine Signatur, kein echter KIS-Schreibzugriff und kein Versand.</p>
          {encounter.kis.letters.length === 0 ? <div className="kis-empty">Noch kein Brief übergeben. Der Agent kann keine Übergabe auslösen.</div> : [...encounter.kis.letters].reverse().map((letter, index) => <details className="kis-document" key={letter.id} open={window.location.hash === '#briefablage' && index === 0 ? true : undefined}><summary><FileText size={17} /><span>{new Date(letter.at).toLocaleString('de-DE')} · {letter.reviewer}<small>{letter.label} · Quellenstand {letter.source_version}</small></span><span className="pill teal">Gespeichert</span></summary><code>{letter.id}</code>{letter.sections.map(section => <article key={section.id}><h3>{section.title}</h3><p>{section.text}</p></article>)}</details>)}
        </section></>}
    </main>
  </div>
}
