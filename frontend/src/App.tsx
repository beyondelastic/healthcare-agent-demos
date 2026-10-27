import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  Activity, ArrowDownToLine, ArrowRight, BookOpen, Check, CheckCheck,
  ChevronDown, ChevronRight, CircleAlert, ClipboardCheck, Clock3, Database,
  FileCheck2, FileText, FlaskConical, History, Layers3, Link2, LoaderCircle,
  PanelRightClose, Plus, RefreshCw, Save, Search, ShieldCheck, Sparkles, X,
} from 'lucide-react'
import type { AgentRun, CaseSummary, Citation, Encounter, Finding, Health, Section } from './types'
import AgentWorkbench from './AgentWorkbench'
import SectionWarnings, { findingsForSection } from './SectionWarnings'
import { initialSources, readSources, SourceOverview, usePresentationMode, ViewModeToggle } from './Presentation'
import type { Scene } from './Presentation'
import { api, ApiError } from './api'
import CitationLinks, { EvidenceShortcut } from './CitationLinks'
import { useNavigationGuard, useWorkspaceSync } from './useWorkspaceSafety'
import IntakeWorkbench, { ScanPreview } from './IntakeWorkbench'
import GuidedStory from './GuidedStory'
import { derivePresentationStory } from './demoStory'
import SourceInvestigation from './SourceInvestigation'

type Tab = 'quality' | 'sources' | 'audit' | 'platform'
type Modal = { type: 'review'; finding: Finding } | { type: 'approve' }
  | { type: 'generate'; mode: 'foundry' | 'rehearsal' } | { type: 'export'; text: string }
  | { type: 'resolve-followup' } | { type: 'reset' } | null

const titles = ['Aufnahmegrund und Anamnese', 'Dokumentierte Diagnosen', 'Relevante Befunde', 'Therapie und Verlauf', 'Entlassmedikation', 'Weiterbehandlung und offene Befunde']
const stateLabels = { new: 'Noch kein Entwurf', draft: 'In Bearbeitung', approved: 'Demo-freigegeben' }
const time = (value: string) => new Date(value).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })

function LetterText({ section, disabled, onChange }: {
  section: Section
  disabled: boolean
  onChange: (text: string) => void
}) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    let width = element.clientWidth
    const fit = () => {
      element.style.height = 'auto'
      element.style.height = `${element.scrollHeight + 2}px`
    }
    fit()
    const observer = new ResizeObserver(() => {
      if (element.clientWidth !== width) {
        width = element.clientWidth
        fit()
      }
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [section.text])
  return <textarea ref={ref} aria-label={section.title} value={section.text}
    disabled={disabled} rows={3} onChange={event => onChange(event.target.value)} />
}

export default function App() {
  const [scene, setScene] = useState<Scene>('sources')
  const [storyStarted, setStoryStarted] = useState(false)
  const [inspectionOpen, setInspectionOpen] = useState(false)
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null)
  const [previousAgentRun, setPreviousAgentRun] = useState<AgentRun | null>(null)
  const onAgentRunChange = useCallback((run: AgentRun | null, previous: AgentRun | null) => {
    setAgentRun(run); setPreviousAgentRun(previous)
  }, [])
  const [agentHistoryReady, setAgentHistoryReady] = useState(false)
  const [reviewedInvestigation, setReviewedInvestigation] = useState<string | null>(null)
  const [expandedLetter, setExpandedLetter] = useState(false)
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [selected, setSelected] = useState(new URLSearchParams(window.location.search).get('case') ?? 'DEMO-014')
  const [presentation, setPresentation] = usePresentationMode(selected)
  const [encounter, setEncounter] = useState<Encounter | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [sections, setSections] = useState<Section[]>([])
  const [dirty, setDirty] = useState(false)
  const [tab, setTab] = useState<Tab>('quality')
  const [documentId, setDocumentId] = useState('')
  const [citation, setCitation] = useState<Citation | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    try {
      setReviewedInvestigation(sessionStorage.getItem(`klinik-studio:reviewed-sources:${selected}`))
    } catch {
      setReviewedInvestigation(null)
      setError('Der Ansichtsfortschritt konnte nicht geladen werden. Die Quellenprüfung bleibt zur Sichtung geöffnet.')
    }
  }, [selected])
  const [notice, setNotice] = useState('')
  const [filter, setFilter] = useState('')
  const [modal, setModal] = useState<Modal>(null)
  const [reviewer, setReviewer] = useState('Demo-Prüfer(in)')
  const [note, setNote] = useState('')
  const [decision, setDecision] = useState<'acknowledged' | 'rejected'>('acknowledged')
  const [confirmed, setConfirmed] = useState(false)
  const [agentConfirmation, setAgentConfirmation] = useState(false)
  const [intakeConfirmation, setIntakeConfirmation] = useState(false)
  const [modalChanged, setModalChanged] = useState(false)
  const [externalChange, setExternalChange] = useState(false)
  const [followupDate, setFollowupDate] = useState('')
  const [sourceStart, setSourceStart] = useState(false)
  const [generationMode, setGenerationMode] = useState<'foundry' | 'rehearsal'>('foundry')
  const [elapsed, setElapsed] = useState(0)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const exportRef = useRef<HTMLTextAreaElement>(null)
  const inspectorRef = useRef<HTMLElement>(null)
  const sourceViewerRef = useRef<HTMLElement>(null)
  const live = useRef({ encounter, dirty, busy, modal })
  live.current = { encounter, dirty, busy, modal }
  const checking = useRef(false)
  const lastPresentationPosition = useRef('')
  const presentationSourceIds = new Set([
    ...(encounter ? initialSources(encounter).map(doc => doc.id) : []),
    ...readSources(agentRun).map(doc => doc.id),
  ])
  const visibleDocuments = encounter?.documents.filter(doc => !presentation || encounter.draft
    || agentRun?.proposal || presentationSourceIds.has(doc.id)) ?? []
  const activeDoc = visibleDocuments.find(doc => doc.id === documentId)
  const revealFindings = !presentation || Boolean(encounter?.draft || agentRun?.proposal)
  const openFindings = encounter?.findings.filter(f => !f.review).length ?? 0
  const stale = Boolean(encounter?.draft && encounter.draft.source_version !== encounter.source_version)
  const hasExtendedContext = Boolean(encounter?.documents.some(doc => doc.intake_id) || encounter?.followup_tasks.length)
  const pendingReport = encounter?.documents.some(doc => doc.kind === 'Mikrobiologie' && doc.status === 'pending')
  const generating = busy === 'Entwurf erstellen'
  const letterVisible = Boolean(encounter?.draft && (presentation || !sourceStart))
  const hasProposal = Boolean(agentRun?.status === 'awaiting_approval' && agentRun.proposal)
  const guided = presentation
  const story = guided && encounter ? derivePresentationStory(encounter, agentRun, scene, agentHistoryReady, storyStarted, previousAgentRun,
    Boolean(agentRun && reviewedInvestigation === agentRun.id)) : null
  const viewScene = guided && dirty && encounter?.draft ? 'review' : story?.scene ?? scene
  const presentationPosition = `${encounter?.id}:${viewScene}:${story?.stage}:${story?.waiting}:${story?.currentProposal}:${story?.intakeFocus}:${encounter?.status}`
  const showSavedLetter = viewScene === 'review' && (!(guided ? story?.currentProposal : hasProposal) || dirty)
  const approvalReason = dirty ? 'Zuerst Briefänderungen speichern.'
    : !encounter?.draft ? 'Zuerst einen Entwurf übernehmen.'
      : stale ? 'Neue Quellen sind verfügbar. Den Entwurf zuerst aktualisieren und erneut prüfen.'
        : openFindings ? `Noch ${openFindings} Prüfpunkte bewerten. Offene Sachverhalte bleiben auch danach gekennzeichnet.`
          : ''
  const followupRequirements = [
    ...(!followupDate ? ['Gültigen Termin auswählen.'] : []),
    ...(reviewer.trim().length < 2 ? ['Prüfername: mindestens 2 Zeichen.'] : []),
    ...(note.trim().length < 8 ? [`Begründung: mindestens 8 Zeichen (${note.trim().length}/8).`] : []),
    ...(!confirmed ? ['Bestätigungsfeld aktivieren.'] : []),
  ]

  function acceptCase(data: Encounter) {
    setNotice('')
    live.current = { ...live.current, encounter: data, dirty: false }
    setEncounter(data)
    setSections(data.draft?.sections ?? [])
    setDirty(false)
    setExternalChange(false)
  }

  function continueInvestigation() {
    if (!agentRun || !encounter || agentRun.source_version !== encounter.source_version
      || agentRun.base_revision !== encounter.revision || agentRun.status !== 'awaiting_approval') return
    setReviewedInvestigation(agentRun.id)
    try {
      sessionStorage.setItem(`klinik-studio:reviewed-sources:${encounter.id}`, agentRun.id)
    } catch {
      setError('Der Ansichtsfortschritt gilt nur für diese Ansicht und konnte nicht für das Neuladen gespeichert werden. Fall und Brief bleiben unverändert.')
    }
  }

  async function checkCurrent(explicit = false): Promise<boolean> {
    const before = live.current
    if (!before.encounter || before.busy || checking.current) return false
    checking.current = true
    try {
      const data = await api<Encounter>(`/cases/${before.encounter.id}`)
      const current = live.current
      if (!current.encounter || current.encounter.id !== data.id || current.busy) return false
      if (data.revision < current.encounter.revision) return false
      if (data.revision === current.encounter.revision) {
        if (JSON.stringify(data.event_automation) !== JSON.stringify(current.encounter.event_automation)) {
          live.current = { ...current, encounter: data }
          setEncounter(data)
        }
        setError(value => value.startsWith('Synchronisation:') ? '' : value)
        return true
      }
      if (current.dirty) {
        setExternalChange(true)
        setError('Der Fall wurde in einer anderen Ansicht geändert. Ihre Texteingaben bleiben erhalten. Text sichern und den Fall ausdrücklich neu laden, bevor Sie speichern.')
        return false
      }
      acceptCase(data)
      setConfirmed(false)
      if (current.modal && current.modal.type !== 'export') {
        setModalChanged(true)
        setModal(value => {
          if (value?.type !== 'review') return value
          const finding = data.findings.find(item => item.id === value.finding.id)
          return finding ? { ...value, finding } : null
        })
      }
      setNotice(explicit
        ? 'Fallstand aktualisiert. Bitte die angezeigten Informationen prüfen und die Aktion erneut öffnen.'
        : presentation ? '' : 'Fallstand aktualisiert. Der Brief wird nicht automatisch neu erstellt.')
      return false
    } catch (err) {
      setError(`Synchronisation: ${err instanceof Error ? err.message : 'Aktueller Fallstand konnte nicht geladen werden.'}`)
      return false
    } finally { checking.current = false }
  }

  useWorkspaceSync(() => checkCurrent())
  useNavigationGuard(dirty || Boolean(modal) || agentConfirmation || intakeConfirmation, Boolean(busy), setError)

  async function beginModal(value: Exclude<Modal, null>) {
    if (intakeConfirmation) { setError('Zuerst die offene Dokumentaktion abschließen oder verwerfen.'); return }
    if (!await checkCurrent(true)) return
    setModalChanged(false); setConfirmed(false); setError(''); setModal(value)
  }

  useEffect(() => {
    let active = true
    Promise.all([api<CaseSummary[]>('/cases'), api<Health>('/health')])
      .then(([items, status]) => { if (active) { setCases(items); setHealth(status) } })
      .catch((err: Error) => { if (active) setError(err.message) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    setEncounter(null)
    setCitation(null)
    setDocumentId('')
    setError('')
    setNotice('')
    setSourceStart(false)
    setStoryStarted(false)
    setAgentRun(null)
    setPreviousAgentRun(null)
    setAgentHistoryReady(false)
    setAgentConfirmation(false); setIntakeConfirmation(false); setModalChanged(false); setExternalChange(false)
    setModal(null); setConfirmed(false)
    setInspectionOpen(false)
    api<Encounter>(`/cases/${selected}`)
      .then(data => {
        if (active) {
          acceptCase(data)
          setScene(data.status === 'approved' ? 'handover' : data.draft ? 'review' : 'sources')
        }
      })
      .catch((err: Error) => { if (active) setError(err.message) })
    return () => { active = false }
  }, [selected])

  useEffect(() => {
    if (agentRun?.status === 'running') setScene('agent')
    if (agentRun?.status === 'awaiting_approval') setScene('review')
  }, [agentRun?.id, agentRun?.status])

  useEffect(() => {
    setInspectionOpen(false)
    if (viewScene === 'handover') setTab('quality')
  }, [viewScene])

  useEffect(() => {
    if (!presentation || modal || intakeConfirmation || agentConfirmation || dirty
      || lastPresentationPosition.current === presentationPosition) return
    const target = document.querySelector('.guided-story, .presentation-steps')
    if (!target) return
    lastPresentationPosition.current = presentationPosition
    requestAnimationFrame(() => target.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }, [presentationPosition, presentation, modal, intakeConfirmation, agentConfirmation, dirty])

  useEffect(() => {
    if (!presentation || !inspectionOpen || modal) return
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setInspectionOpen(false) }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [presentation, inspectionOpen, modal])

  useEffect(() => {
    if (modal) dialogRef.current?.showModal()
    else {
      dialogRef.current?.close()
      setModalChanged(false)
    }
  }, [modal])

  useEffect(() => {
    if (!generating) return
    const started = Date.now()
    setElapsed(0)
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [generating])

  useEffect(() => {
    if (tab === 'sources' && documentId) {
      sourceViewerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [tab, documentId, citation])

  async function mutate(path: string, body: object, label: string, method = 'POST') {
    if (!encounter || busy || modalChanged || externalChange || intakeConfirmation) return
    if (!await checkCurrent(true)) return
    setBusy(label); setError(''); setNotice('')
    if (path === '/generate') setModal(null)
    try {
      const data = await api<Encounter>(`/cases/${encounter.id}${path}`, {
        method, body: JSON.stringify({ ...body, revision: encounter.revision }),
      })
      setError('')
      acceptCase(data)
      setModal(null)
      if (label === 'Entwurf erstellen') {
        setScene('review')
        setSourceStart(false)
        setTab('quality')
        setDocumentId('')
        setCitation(null)
      }
      if (label === 'Demo-Entwurf freigeben') setScene('handover')
      setNotice(label === 'Entwurf erstellen' && data.draft
        ? `${data.draft.mode === 'foundry' ? 'Live-KI' : 'Probenmodus'}: Neuer Entwurf aus ${data.documents.length} Quellen in ${data.draft.duration_seconds.toFixed(1)} Sekunden erstellt und gespeichert. Bitte alle sechs Abschnitte und Quellen prüfen.`
        : label === 'Termin bestätigen'
          ? hasExtendedContext
            ? 'Termin als neue Quelle bestätigt. Der Entwurf bleibt erhalten und muss mit dem Agenten aktualisiert werden; Scanempfehlungen und bestätigte Zuständigkeiten werden nicht durch Textbausteine ersetzt.'
            : data.draft
            ? 'Termin bestätigt. Nur „Weiterbehandlung und offene Befunde“ wurde quellenbasiert aktualisiert, ohne neuen KI-Aufruf. Alle übrigen Abschnitte bleiben unverändert. Aktualisierten Text bitte prüfen.'
            : 'Termin als zusätzliche Quelle bestätigt. Noch kein Brief erstellt. Der bestätigte Termin wird beim ersten KI-Entwurf berücksichtigt.'
        : label === 'Demo-Entwurf freigeben'
          ? 'Demo-Freigabe gespeichert. Noch keine KIS-Übergabe: Die Briefkopie anschließend separat bestätigen.'
          : 'Änderung dauerhaft im Demo-Prüfprotokoll gespeichert.')
      if (label === 'Termin bestätigen') setSourceStart(false)
      setCases(await api<CaseSummary[]>('/cases'))
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConfirmed(false)
        if (modal) setModalChanged(true)
        if (dirty) setExternalChange(true)
      }
      setError(err instanceof Error ? err.message : 'Unerwarteter Fehler. Bitte neu laden.')
    } finally { setBusy('') }
  }

  function showCitation(ref: Citation) {
    setInspectionOpen(true)
    setCitation(ref); setDocumentId(ref.document_id); setTab('sources')
    if (window.innerWidth < 850) {
      requestAnimationFrame(() => inspectorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }

  function showFinding(id: string) {
    setInspectionOpen(true)
    setTab('quality')
    requestAnimationFrame(() => document.getElementById(`finding-${id}`)?.scrollIntoView({
      behavior: 'smooth', block: 'center',
    }))
  }

  function changeCase(id: string) {
    if (id === selected || busy) return
    if ((dirty || modal || agentConfirmation || intakeConfirmation) && !window.confirm('Ungespeicherte Eingaben oder offene Bestätigungen verwerfen und Fall wechseln?')) return
    setDirty(false); setSelected(id)
  }

  function generate(mode: 'foundry' | 'rehearsal') {
    if (hasExtendedContext) {
      setError('Für diesen Scan-/Aufgabenfall bitte den Agentenworkflow verwenden. Die einfache Direktgenerierung prüft diesen Kontext nicht vollständig.')
      return
    }
    if (encounter?.draft) {
      void beginModal({ type: 'generate', mode })
      return
    }
    startGeneration(mode)
  }

  function startGeneration(mode: 'foundry' | 'rehearsal') {
    setGenerationMode(mode)
    void mutate('/generate', { mode }, 'Entwurf erstellen')
  }

  function beginWithSources() {
    if (busy || dirty) return
    setSourceStart(true)
    setDocumentId('')
    setCitation(null)
    setTab('sources')
    setNotice('')
    setError('')
  }

  async function reload() {
    if (dirty && !window.confirm('Ungespeicherte Änderungen verwerfen und neu laden?')) return
    setBusy('Neu laden'); setError('')
    try {
      const [data, list, status] = await Promise.all([
        api<Encounter>(`/cases/${selected}`), api<CaseSummary[]>('/cases'), api<Health>('/health'),
      ])
      const changed = data.revision !== live.current.encounter?.revision
      acceptCase(data); setCases(list); setHealth(status)
      if (changed && modal && modal.type !== 'export') {
        setModalChanged(true); setConfirmed(false)
        setModal(value => {
          if (value?.type !== 'review') return value
          const finding = data.findings.find(item => item.id === value.finding.id)
          return finding ? { ...value, finding } : null
        })
      }
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Laden fehlgeschlagen.')
      return false
    }
    finally { setBusy('') }
  }

  async function download() {
    if (!encounter || busy || dirty) return
    setBusy('Export laden'); setError(''); setNotice('')
    try {
      const response = await fetch(`/api/cases/${encounter.id}/export`)
      if (!response.ok) {
        const data: { detail?: unknown } = await response.json()
        throw new Error(typeof data.detail === 'string' ? data.detail : `Export fehlgeschlagen (${response.status}).`)
      }
      setModal({ type: 'export', text: await response.text() })
    } catch (err) { setError(err instanceof Error ? err.message : 'Export fehlgeschlagen.') }
    finally { setBusy('') }
  }

  async function resetDemo() {
    if (busy || !confirmed || modalChanged) return
    if (!await checkCurrent(true)) return
    setBusy('Demo zurücksetzen'); setError(''); setNotice('')
    try {
      const latest = await api<CaseSummary[]>('/cases')
      if (latest.some(item => cases.find(old => old.id === item.id)?.revision !== item.revision)) {
        setCases(latest); setConfirmed(false)
        setError('Ein Demo-Fall wurde geändert. Die Fallliste ist aktualisiert. Bitte das Zurücksetzen erneut prüfen und bestätigen.')
        return
      }
      const result = await api<{ backup_id: string; cases: Encounter[] }>('/demo/reset', {
        method: 'POST', body: JSON.stringify({
          confirmed: true,
          revisions: Object.fromEntries(cases.map(item => [item.id, item.revision])),
        }),
      })
      const current = result.cases.find(item => item.id === selected)
      if (!current) throw new Error('Demo zurückgesetzt, aber der aktuelle Fall fehlt in der Antwort. Bitte neu laden.')
      acceptCase(current)
      setCases(result.cases.map(item => ({
        ...item, documents: item.documents.length,
        open_findings: item.findings.filter(finding => !finding.review).length,
      })))
      setTab('sources'); setDocumentId(''); setCitation(null); setSourceStart(false)
      setScene('sources'); setInspectionOpen(false)
      setStoryStarted(false); setAgentRun(null); setPreviousAgentRun(null); setAgentHistoryReady(false)
      setFilter(''); setNote(''); setFollowupDate(''); setConfirmed(false)
      setReviewer('Demo-Prüfer(in)'); setModal(null)
      setNotice(`Alle drei Demo-Fälle sind wieder am Anfang: keine Entwürfe oder Bewertungen, ursprüngliche Quellen und offene Befunde. Vorheriger gespeicherter Stand gesichert (Sicherungs-ID: ${result.backup_id}).`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Zurücksetzen fehlgeschlagen. Bitte neu laden.')
    } finally { setBusy('') }
  }

  return (
    <div className={`app${presentation ? ' presentation-mode' : ''}${guided ? ' guided-mode' : ''}`} data-scene={viewScene}>
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="Klinik Studio Startseite">
          <span className="brand-mark"><Plus size={24} strokeWidth={3} /></span>
          <span>Klinik<span className="brand-light">Studio</span><small>DOCUMENTATION INTELLIGENCE</small></span>
        </a>
        <div className="workspace-label">ARBEITSBEREICH <span>EBC DEMO</span></div>
        <button className="nav-item active" onClick={() => setTab('quality')}><Layers3 size={18} /> Dokumentationscockpit <ChevronRight size={15} /></button>
        <button className="nav-item" onClick={() => setTab('platform')}><ShieldCheck size={18} /> Plattform & Transparenz</button>
        <a className="nav-item" href={`/demo-kis?case=${selected}&view=${presentation ? 'presentation' : 'full'}`}><Database size={18} />Demo-KIS · Quellsystem</a>
        <div className="case-heading"><span>DEMO-FÄLLE</span><span>{cases.length.toString().padStart(2, '0')}</span></div>
        <label className="search"><Search size={16} /><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Fall suchen …" aria-label="Demo-Fälle suchen" /></label>
        <div className="case-list">
          {cases.filter(item => `${item.id} ${item.name}`.toLowerCase().includes(filter.toLowerCase())).map(item => (
            <button className={`case-item ${selected === item.id ? 'selected' : ''}`} key={item.id} onClick={() => changeCase(item.id)} disabled={Boolean(busy)}>
              <div className="case-item-top"><span className="case-avatar">{item.initials}</span><span><strong>{item.name}</strong><small>{item.id} · {item.age} Jahre</small></span>{selected === item.id && <span className="selected-dot" />}</div>
              <div className="case-item-bottom"><span>{item.documents} Quellen</span><span className={item.open_findings ? 'amber-text' : 'teal-text'}>{item.open_findings ? `${item.open_findings} offen` : 'Keine offenen Punkte'}</span></div>
              <small className="case-scenario">{item.label}</small>
            </button>
          ))}
          {cases.length > 0 && !cases.some(item => `${item.id} ${item.name}`.toLowerCase().includes(filter.toLowerCase())) && <p className="muted small">Kein passender Demo-Fall.</p>}
        </div>
        <div className="sidebar-bottom">
          <div className="platform-card"><Sparkles size={18} /><div><strong>Powered by Microsoft Foundry</strong><small>Ein Workflow. Nachvollziehbare Quellen.</small></div></div>
          <div className="user"><span>DP</span><div>Demo-Arbeitsplatz<small>Lokaler Einzelplatz · ohne SSO</small></div><ShieldCheck size={16} /></div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar"><div><Plus size={18} /><strong>{presentation ? 'Klinik Studio' : 'Entlassdokumentation'}</strong>
          {presentation && encounter && <span className="topbar-patient">{encounter.name}</span>}</div>
          <span className="topbar-right"><span className="live-dot" />Synthetische Demo · KIS simuliert</span>
          <ViewModeToggle presentation={presentation} onChange={value => {
            setPresentation(value)
            if (value && (tab === 'audit' || tab === 'platform')) setTab('quality')
          }} /></header>
        <main>
          <div className="page-heading"><div><div className="eyebrow">KLINISCHE DOKUMENTATION, NEU GEDACHT</div><h1>Mehr Überblick. Weniger Schreibarbeit.</h1><p>Vom verteilten Wissen zum nachvollziehbaren Entlassbrief-Entwurf.</p></div><span className="pill subtle"><ShieldCheck size={14} /> Menschliche Prüfung bleibt entscheidend</span></div>
          <div className="demo-banner"><FlaskConical size={17} /><span><strong>Ausschließlich synthetische Daten.</strong> Keine Patientenversorgung, keine klinische Signatur. Alle KIS-, RIS- und LIS-Anbindungen sind simuliert.</span><span className="banner-tag">DEMO</span></div>
          <div className="demo-reset-controls"><span>Für eine neue Vorführung alle drei Fälle auf den Anfang zurücksetzen.</span><button className="button" disabled={Boolean(busy) || cases.length !== 3} onClick={() => void beginModal({ type: 'reset' })}><RefreshCw size={15} />Demo zurücksetzen</button></div>
          {presentation && <details className="presenter-menu"><summary>Präsentationssteuerung</summary>
            <div><label>Demo-Fall<select value={selected} disabled={Boolean(busy)} onChange={event => changeCase(event.target.value)}>
              {cases.map(item => <option key={item.id} value={item.id}>{item.name} · {item.id}</option>)}
            </select></label>
              <button className="button" disabled={Boolean(busy)} onClick={() => void reload()}><RefreshCw size={14} />Fall neu laden</button>
              <button className="button" disabled={Boolean(busy) || cases.length !== 3} onClick={() => void beginModal({ type: 'reset' })}>Demo zurücksetzen</button>
            </div>
            <p>Ansicht und Szenen wechseln ohne Zurücksetzen. Probenmodus, frühere Aufträge und Plattformdetails stehen in der Vollansicht bereit.</p>
          </details>}
          {error && <div className="message error" role="alert"><CircleAlert size={18} /><span>{error}</span><button onClick={() => void reload()} disabled={Boolean(busy)}><RefreshCw size={14} /> Neu laden</button></div>}
          {notice && <div className="message success" role="status"><Check size={17} /><span>{notice}</span><button aria-label="Hinweis schließen" onClick={() => setNotice('')}><X size={15} /></button></div>}
          {!encounter ? <div className="loading">{error ? <CircleAlert size={24} /> : <LoaderCircle className="spin" size={24} />}<p>{error ? 'Fall konnte nicht geladen werden.' : 'Demo-Fall wird geladen …'}</p></div> : <>
            <section className="patient-card">
              <div className="patient-identity"><div className="patient-avatar">{encounter.initials}</div><div><div className="patient-title"><h2>{encounter.name}</h2><span className="pill subtle">Fiktive Patientin</span></div><div className="patient-meta">{encounter.age} Jahre <span>·</span> {encounter.id} <span>·</span> {encounter.department}</div></div></div>
              <div className="stay"><span>STATIONÄRER AUFENTHALT</span><strong>{encounter.admitted} <ArrowRight size={13} /> {encounter.discharge}</strong></div>
              <span className={`pill ${encounter.status === 'approved' ? 'teal' : 'amber'}`}><span className="status-dot" />{presentation && hasProposal && agentRun?.base_revision === encounter.revision
                ? story?.stage === 'responsibility' ? 'Aufgabe zur Bestätigung' : 'Vorschlag zur Prüfung' : stateLabels[encounter.status]}</span>
            </section>
            <section className="workflow" aria-label="Bearbeitungsschritte">
              <div className="workflow-step done"><span><Database size={17} /></span><div><strong>Quellen zusammenführen</strong><small>{encounter.documents.length} Demo-Quellen · Stand {encounter.source_version}</small></div><Check size={16} /></div>
              <ChevronRight size={18} className="step-arrow" />
              <div className={`workflow-step ${encounter.draft ? 'done' : 'current'}`}><span><Sparkles size={17} /></span><div><strong>Entwurf erstellen</strong><small>{encounter.draft ? (encounter.draft.mode === 'foundry' ? 'Mit Microsoft Foundry erstellt' : 'Probenmodus · Textbausteine') : 'Quellenbasiert, nicht frei erfunden'}</small></div></div>
              <ChevronRight size={18} className="step-arrow" />
              <div className={`workflow-step ${encounter.status === 'approved' ? 'done' : ''}`}><span><ClipboardCheck size={17} /></span><div><strong>Prüfen & freigeben</strong><small>{openFindings ? `${openFindings} Prüfpunkte offen` : 'Keine unbewerteten Prüfpunkte'}</small></div></div>
            </section>

            {story && <GuidedStory story={story} encounter={encounter} run={agentRun} />}
            <div className={guided ? 'guided-content' : undefined} data-story-stage={story?.stage}>
            {story?.stage === 'start' && !story.waiting && !agentRun && <SourceOverview encounter={encounter}
              onShowSource={id => { setDocumentId(id); setCitation(null); setTab('sources'); setInspectionOpen(true) }} />}
            {story?.chapter === 1 && agentRun?.source_version === encounter.source_version
              && (story.stage === 'investigation' || story.waiting && !story.loading || agentRun.status === 'failed' && story.stage === 'start')
              && <SourceInvestigation encounter={encounter} run={agentRun} previousRun={previousAgentRun}
                blocked={Boolean(busy) || dirty || Boolean(modal) || intakeConfirmation || agentConfirmation}
                onShowSource={id => { setDocumentId(id); setCitation(null); setTab('sources'); setInspectionOpen(true) }}
                onContinue={story.stage === 'investigation' ? continueInvestigation : undefined} />}
            {story?.chapter === 1 && agentRun?.source_version === encounter.source_version
              && !story.waiting && story.stage !== 'investigation' && agentRun.proposal && <details className="guided-source-results">
                <summary>Ergebnis der Quellenprüfung ansehen</summary>
                <SourceInvestigation encounter={encounter} run={agentRun} previousRun={previousAgentRun}
                  blocked={Boolean(busy) || dirty || Boolean(modal) || intakeConfirmation || agentConfirmation}
                  onShowSource={id => { setDocumentId(id); setCitation(null); setTab('sources'); setInspectionOpen(true) }} />
              </details>}
            {story?.stage === 'medication' && !encounter.kis.medication_released && !story.waiting && <section className="guided-result">
              <h2>Freigabe im Medikationsmodul erforderlich</h2>
              <p>Der Briefvorschlag enthält noch keine Entlassmedikation aus diesem Plan. Die Freigabe erfolgt im Quellsystem; anschließend kann der Plan in die Quellenprüfung einbezogen werden.</p>
              <a className="button primary" href={`/demo-kis?case=${encounter.id}&view=presentation`}>
                <Database size={16} />Medikationsmodul öffnen
              </a>
            </section>}
            {story?.stage === 'initial-done' && <section className="guided-result">
              <h2>Briefablage und weitere Unterlagen</h2>
              <p>Die übergebene Briefkopie bleibt unverändert. Später eingehende Unterlagen können separat zugeordnet und geprüft werden.</p>
              <button className="button primary" disabled={Boolean(busy) || dirty || intakeConfirmation || agentConfirmation}
                onClick={() => { setStoryStarted(true); setScene('sources') }}>Dokumenteingang öffnen<ArrowRight size={16} /></button>
              <a className="text-button" href={`/demo-kis?case=${encounter.id}&view=presentation#briefablage`}>Erste Briefkopie im Demo-KIS ansehen →</a>
            </section>}
            <details className={guided ? `guided-intake${story?.intakeFocus ? ' is-current' : ''}` : 'intake-container'}
              hidden={guided && story?.chapter === 1 && !intakeConfirmation}
              data-intake-focus={story?.intakeFocus}
              open={!guided || Boolean(story?.intakeFocus) || intakeConfirmation}>
              <summary hidden={!guided || Boolean(story?.intakeFocus)}>Scan und Nachverfolgung ansehen</summary>
            <IntakeWorkbench key={`intake-${encounter.id}`} encounter={encounter} health={health} run={agentRun}
              blocked={Boolean(busy) || dirty || Boolean(modal) || agentConfirmation}
              guided={guided} focus={story?.intakeFocus ?? undefined} onOpen={() => setStoryStarted(true)}
              onBusy={setBusy} onChange={acceptCase} onEnsureCurrent={() => checkCurrent(true)}
              onActionChange={setIntakeConfirmation} onCitation={showCitation} />
            </details>
            <AgentWorkbench key={encounter.id} encounter={encounter} health={health} dirty={dirty}
              externalPending={intakeConfirmation}
              guided={guided} guidedWaiting={Boolean(story?.waiting)} guidedStage={story?.stage}
              needsAgent={Boolean(story?.needsAgent)} focusSection={story?.focusSection ?? 'medication'}
              onHistoryReady={setAgentHistoryReady}
              presentation={presentation} scene={viewScene} onSceneChange={setScene} onRunChange={onAgentRunChange}
              busy={Boolean(busy)} onBusy={setBusy} onReload={() => void reload()} onCitation={showCitation}
              onShowFinding={showFinding}
              onShowSource={id => { setDocumentId(id); setCitation(null); setTab('sources'); setInspectionOpen(true) }}
              onEnsureCurrent={() => checkCurrent(true)} onActionChange={setAgentConfirmation}
              onChange={data => { acceptCase(data); setSourceStart(false); void api<CaseSummary[]>('/cases').then(setCases).catch((err: Error) => setError(err.message)) }} />
            {story && (story.stage === 'result' || story.stage === 'done') && <section className="guided-result">
              <h2>{story.stage === 'done' ? 'Briefstände in der Ablage' : 'Laborstatus im Quellsystem'}</h2>
              <p>{story.stage === 'done' ? `${encounter.kis.letters.length} unveränderliche Briefkopie(n) im Demo-KIS. Es wurde kein alter Brief nachträglich verändert.`
                : 'Im Demo-KIS „Abschlussbefund bereitstellen“ ausdrücklich bestätigen. Anschließend über „Zum Cockpit“ hierher zurückkehren.'}</p>
              {!encounter.event_automation.enabled && story.stage === 'result' && <p className="agent-warning">Ereignisprüfung ist ausgeschaltet. Nach dem Befundeingang den Agenten manuell starten.</p>}
              <a className="button primary" href={`/demo-kis?case=${encounter.id}&view=presentation${story.stage === 'done' ? '#briefablage' : ''}`}>
                <Database size={16} />{story.stage === 'done' ? 'Briefkopien im Demo-KIS ansehen' : 'Zum Demo-KIS · Abschlussbefund bereitstellen'}
              </a>
            </section>}

            <details className="direct-generation-info"><summary>Alternative: einfache Direktgenerierung ohne Agentenwerkzeuge</summary><p>Die bisherigen „Mit KI erstellen“-Schaltflächen senden alle Quellen in einem Aufruf. Für die agentische Demo oben „Agentenauftrag starten“ verwenden: Dort beschafft der Agent Inhalte über echte Werkzeuge und liefert zunächst nur einen Vorschlag.</p>
              {hasExtendedContext && <p>Für diesen Scan-/Aufgabenfall ist die einfache Direktgenerierung gesperrt. Der Agent muss zusätzlich Laborstatus und Zuständigkeiten prüfen.</p>}
            </details>
            <section className="demo-story" aria-label="Demo-Ablauf">
              <div><span className="eyebrow">VORHER → NACHHER</span><strong>Verteilte Quellen → KI-Entwurf → nachvollziehbare Prüfung</strong><p>{sourceStart
                ? 'Quellenansicht für die Demo. Der gespeicherte Entwurf ist nur ausgeblendet, nicht gelöscht. Erst der nächste KI-Aufruf erzeugt einen neuen Text.'
                : encounter.draft
                  ? 'Sie sehen einen bereits gespeicherten Entwurf, keinen neuen KI-Aufruf. Beginnen Sie mit den Quellen, um die Entstehung live zu zeigen.'
                  : 'Noch kein Brief vorhanden. Sehen Sie zuerst die Quellen an und lassen Sie anschließend einen Entwurf mit KI erstellen.'}</p></div>
              {sourceStart && encounter.draft
                ? <button className="button" disabled={Boolean(busy)} onClick={() => setSourceStart(false)}><FileText size={15} />Gespeicherten Entwurf anzeigen</button>
                : <button className="button" disabled={Boolean(busy) || dirty} title={dirty ? 'Textänderungen zuerst speichern.' : 'Demo-Ansicht ändern, ohne gespeicherte Daten zu löschen'} onClick={beginWithSources}><Database size={15} />Mit Quellen beginnen</button>}
            </section>

            <div className="workbench" hidden={presentation && !(showSavedLetter || inspectionOpen || viewScene === 'handover')}>
              <section className="letter-panel" hidden={presentation && !showSavedLetter}>
                <div className="panel-header"><div className="panel-title"><FileText size={18} /><h2>Entlassbrief</h2><span className="pill subtle">{letterVisible ? 'ENTWURF' : 'QUELLEN → BRIEF'}</span></div><div className="inline-actions">
                  {presentation && <button className="text-button" onClick={() => setExpandedLetter(value => !value)}>{expandedLetter ? 'Kompakt anzeigen' : 'Alle Abschnitte öffnen'}</button>}
                  <button className="icon-button" title="Aktuellen Fall neu laden" aria-label="Aktuellen Fall neu laden" disabled={Boolean(busy)} onClick={() => void reload()}><RefreshCw size={16} /></button><button className="button small-button" disabled={!encounter.draft || dirty || Boolean(busy)} title={dirty ? 'Textänderungen zuerst speichern.' : 'Gespeicherten Entwurf als Textvorschau öffnen und herunterladen'} onClick={() => void download()}><ArrowDownToLine size={15} /> Export</button></div></div>
                <div className="generation-bar">
                  <div><span className={`engine-dot ${encounter.draft?.mode === 'foundry' ? 'connected' : ''}`} /><span>{generating ? 'Neuer Aufruf läuft …' : sourceStart ? 'Quellen zuerst · Brief ausgeblendet' : encounter.draft ? (encounter.draft.mode === 'foundry' ? 'Gespeicherter Live-KI-Entwurf' : 'Probenmodus · keine KI-Inferenz') : 'Bereit für den ersten Entwurf'}</span></div>
                  <div className="inline-actions"><button className="text-button" disabled={Boolean(busy)} onClick={() => generate('rehearsal')}>Probenmodus</button><button className="button primary" disabled={Boolean(busy) || !health?.foundry.configured} title={health?.foundry.configured ? 'Die Quellen dieses Falls an Foundry senden und einen neuen Entwurf generieren' : 'FOUNDRY_MODEL in .env konfigurieren und Server neu starten'} onClick={() => generate('foundry')}>{generating ? <LoaderCircle size={15} className="spin" /> : <Sparkles size={15} />}{encounter.draft ? 'KI-Entwurf neu erstellen' : 'Mit KI erstellen'}</button></div>
                </div>
                {!generating && <div className="generation-explainer"><Sparkles size={15} /><span>Ein Klick sendet die {encounter.documents.length} synthetischen Quellen dieses Falls an Foundry. Die KI formuliert daraus sechs Briefabschnitte; der Server prüft die Quellenreferenzen. Kein Abruf eines fertigen Musterbriefs.</span></div>}
                {!health?.foundry.configured && <div className="setup-note"><CircleAlert size={14} /> Live-KI noch nicht konfiguriert. Der Probenmodus nutzt vorbereitete Textbausteine, nicht Foundry.</div>}
                {stale && <div className="stale-note"><CircleAlert size={17} /><div><strong>Neue Quelle verfügbar – Entwurf veraltet.</strong><br />Der bestehende Text wurde nicht überschrieben. Neu erstellen und erneut prüfen; Änderungen vorher exportieren.</div></div>}
                {generating ? <div className="generation-progress" role="status">
                  <span className="generation-symbol"><LoaderCircle size={34} className="spin" /></span>
                  <div className="eyebrow">{generationMode === 'foundry' ? 'LIVE-AUFRUF AN MICROSOFT FOUNDRY' : 'PROBENMODUS · KEINE KI-INFERENZ'}</div>
                  <h3>{generationMode === 'foundry' ? 'Aus den Quellen entsteht ein Brief.' : 'Vorbereitete Textbausteine werden zusammengestellt.'}</h3>
                  <p>{generationMode === 'foundry' ? `Das Modell ${health?.foundry.model} erhält die ${encounter.documents.length} Quellen dieses Aufenthalts und erstellt einen neuen strukturierten Entwurf. Anschließend werden die Quellenreferenzen serverseitig geprüft.` : 'Dieser ausdrücklich gewählte Modus verwendet vorbereitete Inhalte und ruft kein Modell auf.'}</p>
                  <div className="generation-sources">{encounter.documents.map(doc => <span key={doc.id}><FileText size={13} />{doc.kind}{doc.status === 'pending' && <Clock3 size={12} />}</span>)}</div>
                  <strong>{elapsed} Sekunden</strong><small>Die vollständige Antwort erscheint nach Abschluss. Keine simulierte Textausgabe oder künstliche Fortschrittsanzeige.</small>
                  {encounter.draft && <p className="muted small">Der bisherige Entwurf bleibt bis zur erfolgreichen Speicherung erhalten. Bei einem Fehler wird nichts ersetzt.</p>}
                </div> : letterVisible && encounter.draft ? <>
                  <div className="paper">
                    <div className="paper-letterhead"><div><span className="hospital-logo"><Plus size={17} /> UNIVERSITÄTSKLINIKUM</span><strong>Musterstadt</strong><small>Fiktives Universitätsklinikum · Innere Medizin</small></div><div className="paper-stamp">SYNTHETISCHE DEMO<br /><strong>{encounter.id}</strong></div></div>
                    <div className="letter-intro"><span className="eyebrow">VORLÄUFIGER ENTLASSBRIEF</span><h3>{encounter.name}</h3><p>Stationärer Aufenthalt vom {encounter.admitted} bis {encounter.discharge} (vorgesehen)</p></div>
                    {sections.map((section, index) => {
                      const warnings = findingsForSection(encounter.findings, section.id)
                      const needsAttention = warnings.length > 0 || stale
                      return <details className={`letter-section${needsAttention ? ' has-section-warnings' : ''}`} key={section.id}
                        open={!presentation || expandedLetter}>
                        <summary className="section-heading"><span className="section-number">{String(index + 1).padStart(2, '0')}</span><h4>{section.title}</h4>
                          {needsAttention && <span className="section-warning-badge"><CircleAlert size={12} aria-hidden="true" />{stale ? 'Quellenstand prüfen' : 'Offener Sachverhalt'}</span>}
                          <EvidenceShortcut citations={section.citations} onCitation={showCitation} />
                          <span className="section-editable">BEARBEITBAR</span></summary>
                        <SectionWarnings findings={warnings} stale={stale} onShowFinding={showFinding} />
                        <LetterText section={section} disabled={Boolean(busy)} onChange={text => { setSections(items => items.map(item => item.id === section.id ? { ...item, text } : item)); setDirty(true) }} />
                        <CitationLinks citations={section.citations} documents={encounter.documents} onCitation={showCitation} />
                      </details>
                    })}
                    <div className="paper-disclaimer"><ShieldCheck size={15} /><span>KI- oder Textbaustein-Entwurf, fachlich zu prüfen. Quellenreferenzen zeigen die Herkunft, bestätigen aber nicht automatisch die Richtigkeit der Zusammenfassung oder manueller Änderungen.</span></div>
                  </div>
                  <div className="letter-footer"><div>{dirty ? <span className="amber-text">Ungespeicherte Änderungen</span> : <span><CheckCheck size={14} /> Lokal gespeichert</span>}{externalChange && <small className="amber-text">Anderer Fallstand: Texteingaben sichern und Fall neu laden.</small>}{encounter.draft.edited && <small>Manuell bearbeitet</small>}</div><button className="button" disabled={!dirty || externalChange || Boolean(busy) || sections.some(s => !s.text.trim())} onClick={() => void mutate('/draft', { sections }, 'Entwurf speichern', 'PUT')}><Save size={15} />Änderungen speichern</button></div>
                </> : <div className="empty-letter"><div className="empty-illustration"><div className="illustration-paper"><FileText size={35} /><span /><span /><span /></div><span className="illustration-spark"><Sparkles size={22} /></span><span className="illustration-check"><Check size={17} /></span></div><div className="eyebrow">VON QUELLEN ZU KLARHEIT</div><h3>{sourceStart ? <>Hier stehen zunächst<br />nur die Quellen.</> : <>Der erste Entwurf beginnt<br />mit dem, was wir wissen.</>}</h3><p>Rechts liegen {encounter.documents.length} getrennte Quellen vor: Aufnahme, Befunde, Verlauf und Weiterbehandlung. Die KI führt ihre dokumentierten Inhalte zu einem bearbeitbaren Brief zusammen.</p><div className="empty-features"><span><Link2 size={14} />Mit Quellenbezug</span><span><CircleAlert size={14} />Mit offenen Punkten</span><span><ShieldCheck size={14} />Unter Ihrer Kontrolle</span></div><button className="button primary" disabled={Boolean(busy)} onClick={() => generate(health?.foundry.configured ? 'foundry' : 'rehearsal')}><Sparkles size={16} />{health?.foundry.configured ? 'Aus Quellen mit KI erstellen' : 'Probenentwurf erstellen'}<ArrowRight size={16} /></button><small>{health?.foundry.configured ? 'Neuer Live-Aufruf im ausgewählten Foundry-Projekt' : 'Vorbereitete synthetische Textbausteine · keine KI-Inferenz'}</small>{sourceStart && encounter.draft && <p className="presentation-note">Vorhandener Entwurf für die Demo ausgeblendet. Beim Neuerstellen wird das Ersetzen ausdrücklich bestätigt.</p>}<div className="preview-sections">{titles.slice(0, 3).map((title, i) => <div key={title}><span>0{i + 1}</span>{title}<span className="preview-line" /></div>)}</div></div>}
              </section>

              <aside className="inspector" ref={inspectorRef} aria-label="Prüfung und Quellen"
                hidden={presentation && !inspectionOpen && (viewScene !== 'handover' || (guided && encounter.status === 'approved'))}>
                {presentation && viewScene !== 'handover' && <div className="inspection-drawer-heading"><strong>Prüfung & Quellen</strong>
                  <button className="icon-button" aria-label="Detailansicht schließen" onClick={() => setInspectionOpen(false)}><X size={20} /></button>
                </div>}
                <div className="inspector-tabs" role="tablist" aria-label="Prüfbereich">
                  <button role="tab" hidden={!revealFindings} aria-selected={tab === 'quality'} className={tab === 'quality' ? 'active' : ''} onClick={() => setTab('quality')}><ClipboardCheck size={16} />Prüfung{openFindings > 0 && <span>{openFindings}</span>}</button>
                  <button role="tab" aria-selected={tab === 'sources'} className={tab === 'sources' ? 'active' : ''} onClick={() => setTab('sources')}><BookOpen size={16} />Quellen</button>
                  <button role="tab" aria-selected={tab === 'audit'} className={tab === 'audit' ? 'active' : ''} onClick={() => setTab('audit')} aria-label="Prüfprotokoll"><History size={16} /></button>
                  <button role="tab" aria-selected={tab === 'platform'} className={tab === 'platform' ? 'active' : ''} onClick={() => setTab('platform')} aria-label="Plattformdetails"><Activity size={16} /></button>
                </div>
                {tab === 'quality' && revealFindings && <div className="inspector-content">
                  <div className="eyebrow">DOKUMENTATIONSQUALITÄT</div><h3>{openFindings ? 'Hier braucht es Ihren Blick.' : 'Alle Prüfpunkte bearbeitet.'}</h3><p className="muted small">Regelbasierte Demo-Prüfung auf bekannte Quellenlücken, Terminwidersprüche und ausstehende Befunde. Keine vollständige klinische Prüfung.</p>
                  <div className={`quality-summary ${openFindings ? '' : 'clear'}`}><span>{openFindings ? <CircleAlert size={22} /> : <CheckCheck size={22} />}</span><div><strong>{openFindings} unbewertete Prüfpunkte</strong><small>{encounter.findings.length} Hinweise insgesamt · keine Entlassentscheidung</small></div></div>
                  <div className="findings">{encounter.findings.map(finding => <article id={`finding-${finding.id}`} className={`finding ${finding.review ? 'reviewed' : ''}`} key={finding.id}>
                    <div className="finding-label"><span>{finding.resolved ? 'GEKLÄRT' : finding.type === 'conflict' ? 'WIDERSPRUCH' : finding.type === 'pending' ? 'AUSSTEHEND' : 'QUELLE FEHLT'}</span>{finding.review ? <span className="reviewed-badge"><Check size={12} />{finding.resolved ? 'Bestätigt' : 'Bewertet'}</span> : <span className="finding-dot" />}</div>
                    <h4>{finding.title}</h4><p>{finding.description}</p><div className="finding-action">{finding.action}</div>
                    <div className="finding-sources">{finding.document_ids.map(id => <button key={id} onClick={() => { setDocumentId(id); setCitation(null); setTab('sources') }}><Link2 size={12} />{encounter.documents.find(doc => doc.id === id)?.kind}<ChevronRight size={11} /></button>)}</div>
                    {finding.review && <div className="review-note"><strong>{finding.review.decision === 'acknowledged' ? 'Zur Kenntnis genommen / Umgang dokumentiert' : 'Hinweis begründet verworfen'}</strong><p>{finding.review.note}</p><small>{finding.review.reviewer} · {time(finding.review.at)}</small></div>}
                    {finding.id === 'conflicting-followup' && <><button className="button full-width" disabled={Boolean(busy) || dirty} onClick={() => { setFollowupDate(encounter.followup_resolution?.date ?? ''); setNote(encounter.followup_resolution?.note ?? finding.review?.note ?? ''); void beginModal({ type: 'resolve-followup' }) }}>{finding.resolved ? 'Bestätigten Termin ändern' : encounter.draft ? 'Termin klären & Abschnitt aktualisieren' : 'Kontrolltermin bestätigen'}<ArrowRight size={14} /></button>{dirty && <small className="validation-help">Bitte zuerst die Textänderungen im Brief speichern.</small>}</>}
                    {!finding.resolved && <button className={`${presentation && !finding.review && encounter.findings.find(item => !item.review)?.id === finding.id ? 'button primary' : 'text-button'} review-button`} disabled={Boolean(busy) || dirty} onClick={() => { setNote(finding.review?.note ?? ''); setDecision(finding.review?.decision ?? 'acknowledged'); void beginModal({ type: 'review', finding }) }}>{finding.review ? 'Bewertung ändern' : 'Prüfpunkt bewerten'}<ArrowRight size={14} /></button>}
                  </article>)}</div>
                  {encounter.findings.length === 0 && <div className="all-clear"><ShieldCheck size={32} /><strong>Keine Hinweise in den definierten Demo-Regeln.</strong><p>Dies bestätigt weder klinische Richtigkeit noch Vollständigkeit. Der Brief muss weiterhin fachlich geprüft werden.</p></div>}
                  {pendingReport && !presentation && <div className="late-report"><Clock3 size={18} /><div><strong>Ein Befund kommt später.</strong><p>Zeigen Sie, wie der Workflow auf eine neue Quelle reagiert.</p><button className="button small-button" disabled={Boolean(busy) || dirty} onClick={() => void mutate('/release-report', {}, 'Demo-Befund ergänzen')}><Plus size={14} />Demo-Befund bereitstellen</button></div></div>}
                  <div className="approval-card"><div><ShieldCheck size={18} /><strong>Bewusste Freigabe statt Autopilot</strong></div><p>Bewertungen dokumentieren den Umgang mit Hinweisen. Sie ersetzen keine fehlenden Daten und keine ärztliche Entscheidung.</p>{encounter.approval && <div className="approved-label"><CheckCheck size={17} />Demo-freigegeben durch {encounter.approval.reviewer}<small>{time(encounter.approval.at)}</small></div>}<button className="button primary full-width" disabled={Boolean(busy) || !encounter.draft || dirty || stale || openFindings > 0 || encounter.status === 'approved'} onClick={() => void beginModal({ type: 'approve' })}><FileCheck2 size={16} />Demo-Entwurf freigeben</button>{dirty && <small className="amber-text">Bitte zuerst Textänderungen speichern.</small>}</div>
                  {presentation && approvalReason && <p className="approval-reason" role="status">{approvalReason}</p>}
                </div>}
                {tab === 'sources' && <div className="inspector-content"><div className="eyebrow">VERFÜGBARE INFORMATIONEN</div><h3>Jede Aussage hat eine Herkunft.</h3><p className="muted small">{visibleDocuments.length} sichtbare Quellen für diesen Aufenthalt. {presentation && !encounter.draft && !agentRun?.proposal ? 'Zwei Einstiegsquellen und tatsächlich gelesene Dokumente. ' : ''}Simulierte Systemanbindungen; keine Suche in echten Patientenakten.</p>
                  <div className="document-list">{visibleDocuments.map(doc => <button key={doc.id} className={`document-row ${documentId === doc.id ? 'selected' : ''}`} onClick={() => { setDocumentId(doc.id); setCitation(null) }}><span className={`doc-icon ${doc.status === 'pending' ? 'pending' : ''}`}>{doc.status === 'pending' ? <Clock3 size={17} /> : <FileText size={17} />}</span><span><strong>{doc.title}</strong><small>{doc.system} · {time(doc.date)}</small></span><ChevronRight size={15} /></button>)}</div>
                  {activeDoc ? <article className="source-viewer" ref={sourceViewerRef}><div className="source-viewer-heading"><span className="pill subtle">{activeDoc.status === 'pending' ? 'AUSSTEHEND' : 'VERFÜGBAR'}</span><button className="icon-button" aria-label="Dokumentansicht schließen" onClick={() => { setDocumentId(''); setCitation(null) }}><PanelRightClose size={16} /></button></div><h4>{activeDoc.title}</h4><p className="source-metadata">{activeDoc.system}<br />{activeDoc.id} · {time(activeDoc.date)}</p>
                    {activeDoc.intake_id && (() => {
                      const scan = encounter.intakes.find(item => item.id === activeDoc.intake_id)
                      return scan ? <ScanPreview caseId={encounter.id} intake={scan}
                        regions={activeDoc.paragraphs.find(item => item.id === citation?.paragraph_id)?.regions} /> : null
                    })()}
                    {activeDoc.paragraphs.map(p => <div className={`source-paragraph ${citation?.paragraph_id === p.id ? 'highlighted' : ''}`} key={p.id}><span>{p.id.toUpperCase()}</span><p>{citation?.paragraph_id === p.id && p.text.includes(citation.quote) ? <>{p.text.slice(0, p.text.indexOf(citation.quote))}<mark>{citation.quote}</mark>{p.text.slice(p.text.indexOf(citation.quote) + citation.quote.length)}</> : p.text}</p></div>)}<div className="source-watermark">SYNTHETISCHES ORIGINAL · NICHT FÜR DIE VERSORGUNG</div></article> : <div className="source-empty"><BookOpen size={25} /><p>Quelle auswählen oder einen Herkunftsbeleg im Brief anklicken.</p></div>}
                </div>}
                {tab === 'audit' && <div className="inspector-content"><div className="eyebrow">NACHVOLLZIEHBARKEIT</div><h3>Was ist passiert – und warum?</h3><p className="muted small">Lokal in SQLite gespeichert. Namen sind Demo-Eingaben, keine verifizierten Identitäten. Kein manipulationssicheres klinisches Audit.</p><div className="audit-list">{[...encounter.audit].reverse().map(event => <article className="audit-item" key={event.id}><span className="audit-dot"><Check size={11} /></span><small>{time(event.at)} · {event.reviewer}</small><h4>{event.action}</h4><p>{event.detail}</p></article>)}</div>{encounter.audit.length === 0 && <div className="source-empty"><History size={28} /><p>Noch keine Aktionen. Erstellung, Änderungen und Bewertungen erscheinen hier.</p></div>}</div>}
                {tab === 'platform' && <div className="inspector-content"><div className="eyebrow">UNTER DER OBERFLÄCHE</div><h3>Einfach in der Anwendung.<br />Transparent im Hintergrund.</h3><div className="platform-details"><div><Database size={19} /><span><strong>Daten</strong><p>Drei synthetische Aufenthalte. KIS, RIS und LIS sind simuliert. Keine echten Gesundheitsdaten eingeben.</p></span></div><div><Sparkles size={19} /><span><strong>Microsoft Foundry</strong><p>{health?.foundry.project}</p><p>Bereitstellung: {health?.foundry.model || 'Noch nicht konfiguriert'}</p><small>Globale Verarbeitung ist für diese synthetische Demo erlaubt.</small></span></div><div><ShieldCheck size={19} /><span><strong>Vertrauensgrenzen</strong><p>Quellen-IDs und wörtliche Zitate werden serverseitig geprüft. Das garantiert keine semantische Richtigkeit. Freigabe nur nach menschlicher Prüfung.</p></span></div><div><Activity size={19} /><span><strong>Letzte Erstellung</strong>{encounter.draft ? <><p>{encounter.draft.model}</p><p>{encounter.draft.duration_seconds.toFixed(2)} s · Quellenstand {encounter.draft.source_version}</p><p>{encounter.draft.usage ? `${encounter.draft.usage.input_tokens} Input- / ${encounter.draft.usage.output_tokens} Output-Token` : 'Keine Token-Nutzung · Probenmodus'}</p></> : <p>Noch kein Entwurf erstellt.</p>}<small>Keine Kostenschätzung ohne verifizierte Modellpreise.</small></span></div></div><div className="technical-note"><strong>Technik</strong><p>React + TypeScript · Python / FastAPI · SQLite · Foundry Responses API</p><p>Lokale Demo ohne SSO. Nicht ohne zusätzliche Authentifizierung und Datenschutzprüfung veröffentlichen.</p></div></div>}
              </aside>
            </div>
            {presentation && viewScene === 'review' && !(guided ? story?.currentProposal : hasProposal) && encounter.draft && story?.intakeFocus !== 'complete' && <div className="scene-next">
              <button className="button primary" disabled={dirty || Boolean(busy) || intakeConfirmation || agentConfirmation}
                onClick={() => setScene('handover')}>Weiter zur menschlichen Freigabe<ArrowRight size={16} /></button>
            </div>}
            </div>
            <footer className="page-footer"><span><ShieldCheck size={13} />Quellen sichtbar. Lücken ausdrücklich benannt. Verantwortung beim Menschen.</span><span>Microsoft EBC · Klinik Studio / 01</span></footer>
          </>}
        </main>
      </div>
      <dialog ref={dialogRef} onCancel={event => { event.preventDefault(); if (!busy) setModal(null) }} onClose={() => { if (!busy) setModal(null) }}>
        {modalChanged && modal && <div className="message error" role="alert">
          <span>Der Fallstand hat sich geändert. Ihre Eingaben bleiben erhalten. Vor dem Speichern den aktuellen Inhalt und die Aktion erneut prüfen.</span>
          <button type="button" className="button" disabled={Boolean(busy)} onClick={() => void reload().then(loaded => {
            if (loaded) { setModalChanged(false); setConfirmed(false); setError('') }
          })}>Aktuellen Stand laden & erneut prüfen</button>
        </div>}
        {modal?.type === 'reset' && <form onSubmit={event => { event.preventDefault(); void resetDemo() }}>
          <div className="modal-header"><span className="modal-icon"><RefreshCw size={23} /></span><button type="button" className="icon-button" aria-label="Dialog schließen" disabled={Boolean(busy)} onClick={() => setModal(null)}><X size={20} /></button></div>
          <div className="eyebrow">NEUE VORFÜHRUNG · ALLE DREI FÄLLE</div><h2>Demo vollständig zurücksetzen?</h2>
          <p className="muted">Marlene Beispiel, Clara Muster und Nora Testfall starten wieder mit ihren ursprünglichen Quellen – ohne Entlassbrief-Entwürfe, Textänderungen, Bewertungen, Terminklärungen, Demo-Freigaben oder bisherige Prüfprotokolle. Nachgereichte Demo-Befunde werden wieder ausstehend, soweit sie es im ursprünglichen Szenario waren.</p>
          <p className="muted">Auch Agentenaufträge, Vorschläge, Demo-KIS-Briefkopien, Scanquellen, Nachverfolgungsaufgaben, Ereignisprüfungs-Einwilligung und Abrufstörungen werden zurückgesetzt. Noras vorbereiteter Plan ist danach wieder nicht freigegeben. Scanoriginale bleiben für die lokalen Sicherungen erhalten, sind im frischen Fall aber nicht mehr zugänglich.</p>
          <p className="muted">Vor dem Zurücksetzen wird der bisher gespeicherte Stand aller drei Fälle samt Agentenprotokollen als Sicherung in derselben lokalen SQLite-Datenbank aufbewahrt. Es gibt keine Wiederherstellen-Schaltfläche. Foundry-Konfiguration, Agentenversion und Modell bleiben unverändert. Es wird kein KI-Aufruf ausgeführt.</p>
          {dirty && <div className="stale-note"><CircleAlert size={18} /><span>Ungespeicherte Textänderungen werden verworfen und sind nicht in der Sicherung enthalten. Zum Behalten erst abbrechen und speichern.</span></div>}
          <label className="checkbox-label"><input required type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>Ich möchte alle drei Demo-Fälle einschließlich ihrer Bearbeitungen auf den ursprünglichen Anfang zurücksetzen.</span></label>
          {error && <p className="modal-error" role="alert">{error}</p>}
          <div className="modal-actions"><button className="button" type="button" disabled={Boolean(busy)} onClick={() => setModal(null)}>Abbrechen</button><button className="button primary" type="submit" disabled={Boolean(busy) || modalChanged || !confirmed}>{busy ? <LoaderCircle size={16} className="spin" /> : <RefreshCw size={16} />}Alle drei Fälle zurücksetzen</button></div>
        </form>}
        {modal?.type === 'resolve-followup' && <form onSubmit={event => { event.preventDefault(); void mutate('/resolve-followup', { date: followupDate, note, reviewer, confirmed }, 'Termin bestätigen') }}>
          <div className="modal-header"><span className="modal-icon"><ClipboardCheck size={23} /></span><button type="button" className="icon-button" aria-label="Dialog schließen" disabled={Boolean(busy)} onClick={() => setModal(null)}><X size={20} /></button></div>
          <div className="eyebrow">AUSDRÜCKLICHE TERMINKLÄRUNG</div><h2>Gültigen Kontrolltermin bestätigen</h2>
          <p className="muted">{hasExtendedContext
            ? `Die Bestätigung wird als zusätzliche Quelle gespeichert. Scanempfehlungen, Zuständigkeiten und Originalangaben bleiben erhalten. ${encounter?.event_automation.enabled ? 'Die aktivierte Ereignisprüfung startet anschließend einen weiteren echten Foundry-Aufruf.' : 'Anschließend den Agenten mit den neuen Quellen erneut starten.'} Keine Änderung in einem echten KIS oder Terminsystem.`
            : 'Die Bestätigung wird als zusätzliche Quelle gespeichert. Originalangaben und Prüfprotokoll bleiben erhalten. Kein neuer KI-Aufruf und keine Änderung im KIS oder Terminsystem.'}</p>
          <label className="form-label">Gültiger Termin<select required value={followupDate} onChange={event => setFollowupDate(event.target.value)}><option value="" disabled>Termin ausdrücklich auswählen</option><option value="29.10.2026">29.10.2026</option><option value="30.10.2026">30.10.2026</option></select></label>
          <label className="form-label">Prüfername (mindestens 2 Zeichen)<input required minLength={2} maxLength={100} value={reviewer} onChange={event => setReviewer(event.target.value)} /></label>
          <label className="form-label">Begründung / erfolgte Klärung<textarea required minLength={8} maxLength={2000} rows={3} aria-describedby="followup-note-help" value={note} onChange={event => setNote(event.target.value)} /><small id="followup-note-help" className="validation-help">Mindestens 8 Zeichen, ohne führende oder abschließende Leerzeichen. Aktuell: {note.trim().length}. Beispiel: „Termin nach Rücksprache bestätigt.“</small></label>
          <div className="stale-note"><CircleAlert size={18} /><span>{hasExtendedContext
            ? 'Der bestehende Entwurf bleibt vollständig erhalten und muss mit dem Agenten neu geprüft werden. Kein automatisches Ersetzen eines Abschnitts. Eine Demo-Freigabe wird aufgehoben.'
            : encounter?.draft
            ? 'Nur „Weiterbehandlung und offene Befunde“ wird neu aus der Bestätigung und den aktuellen Quellen zusammengestellt. Manuelle Änderungen in diesem Abschnitt werden ersetzt; die übrigen fünf Abschnitte bleiben unverändert. Eine Demo-Freigabe wird aufgehoben.'
            : 'Noch kein Entwurf vorhanden. Der Termin wird als zusätzliche Quelle gespeichert und beim ersten KI-Entwurf berücksichtigt. Es wird jetzt kein Brief erstellt.'}</span></div>
          <label className="checkbox-label"><input required type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>{hasExtendedContext ? 'Ich bestätige den ausgewählten Termin als neue Quelle und werde den neuen Agentenvorschlag ausdrücklich prüfen.' : encounter?.draft ? 'Ich bestätige den ausgewählten Termin und das Ersetzen dieses Abschnitts. Ich werde den aktualisierten Text prüfen.' : 'Ich bestätige den ausgewählten Termin zur Übernahme in den späteren Entwurf.'}</span></label>
          <p id="followup-requirements" className={`validation-help ${followupRequirements.length ? 'amber-text' : 'teal-text'}`} aria-live="polite">{followupRequirements.length ? `Noch erforderlich: ${followupRequirements.join(' ')}` : 'Alle Pflichtangaben vollständig. Der Termin kann bestätigt werden.'}</p>
          {error && <p className="modal-error" role="alert">{error}</p>}
          <div className="modal-actions"><button className="button" type="button" disabled={Boolean(busy)} onClick={() => setModal(null)}>Abbrechen</button><button className="button primary" type="submit" aria-describedby="followup-requirements" disabled={Boolean(busy) || modalChanged || followupRequirements.length > 0}>{busy ? <LoaderCircle size={16} className="spin" /> : <Check size={16} />}{hasExtendedContext ? 'Termin als neue Quelle bestätigen' : encounter?.draft ? 'Termin bestätigen & Abschnitt aktualisieren' : 'Kontrolltermin bestätigen'}</button></div>
        </form>}
        {modal?.type === 'generate' && <form onSubmit={event => { event.preventDefault(); startGeneration(modal.mode) }}>
          <div className="modal-header"><span className="modal-icon"><Sparkles size={23} /></span><button type="button" className="icon-button" aria-label="Dialog schließen" onClick={() => setModal(null)}><X size={20} /></button></div>
          <div className="eyebrow">{modal.mode === 'foundry' ? 'NEUER LIVE-KI-AUFRUF' : 'PROBENMODUS · KEINE KI-INFERENZ'}</div>
          <h2>Vorhandenen Entwurf neu erstellen?</h2>
          <p className="muted">{modal.mode === 'foundry' ? `Die ${encounter?.documents.length} aktuellen Quellen werden an Microsoft Foundry gesendet. Die KI erstellt daraus einen neuen Brief, statt den vorhandenen Text zu öffnen.` : 'Vorbereitete Textbausteine werden ohne Modellaufruf neu zusammengestellt.'}</p>
          <div className="stale-note"><CircleAlert size={18} /><span>Der bisherige Brieftext einschließlich manueller Änderungen wird bei Erfolg ersetzt. Eine Demo-Freigabe wird aufgehoben. Das Prüfprotokoll bleibt erhalten. Exportieren Sie Änderungen, die Sie behalten möchten.</span></div>
          <div className="modal-actions"><button type="button" className="button" onClick={() => setModal(null)}>Abbrechen</button><button className="button primary" type="submit" disabled={Boolean(busy) || modalChanged}><Sparkles size={16} />{modal.mode === 'foundry' ? 'Jetzt mit KI neu erstellen' : 'Probenentwurf neu erstellen'}</button></div>
        </form>}
        {modal?.type === 'export' && encounter && <div className="export-dialog">
          <div className="modal-header"><span className="modal-icon"><ArrowDownToLine size={23} /></span><button type="button" className="icon-button" aria-label="Export schließen" onClick={() => setModal(null)}><X size={20} /></button></div>
          <div className="eyebrow">EXPORTVORSCHAU · {encounter.id}</div><h2>Der gespeicherte Brief zum Mitnehmen</h2>
          <p className="muted">Textdatei mit Brief, Quellenbelegen, Bewertungen und Demo-Prüfprotokoll. Kein Versand an ein KIS und keine klinische Signatur.</p>
          <textarea ref={exportRef} className="export-preview" aria-label="Exportierter Entlassbrief" readOnly value={modal.text} />
          <p className="small muted">Falls der eingebettete Browser keinen Download anbietet: Text markieren und mit Strg+C kopieren. Alternativ die App in Edge oder Chrome öffnen und dort herunterladen.</p>
          <div className="modal-actions"><button className="button" onClick={() => { exportRef.current?.focus(); exportRef.current?.select() }}>Text markieren (Strg+C)</button><a className="button primary" href={`/api/cases/${encounter.id}/export`} download={`${encounter.id}-Entwurf.txt`}><ArrowDownToLine size={16} />TXT herunterladen</a></div>
        </div>}
        {modal && (modal.type === 'review' || modal.type === 'approve') && <form onSubmit={event => { event.preventDefault(); if (modal.type === 'review') void mutate(`/findings/${modal.finding.id}`, { decision, note, reviewer }, 'Prüfpunkt bewerten'); else void mutate('/approve', { reviewer, confirmed }, 'Demo-Entwurf freigeben') }}>
          <div className="modal-header"><span className="modal-icon"><ClipboardCheck size={23} /></span><button type="button" className="icon-button" aria-label="Dialog schließen" disabled={Boolean(busy)} onClick={() => setModal(null)}><X size={20} /></button></div>
          <div className="eyebrow">{modal.type === 'review' ? 'MENSCHLICHE BEWERTUNG' : 'BEWUSSTE DEMO-FREIGABE'}</div>
          <h2>{modal.type === 'review' ? modal.finding.title : 'Den geprüften Entwurf freigeben'}</h2>
          <p className="muted">{modal.type === 'review' ? 'Dokumentieren Sie, wie mit diesem Hinweis umgegangen wurde. Eine Bewertung ändert weder die Originalquelle noch automatisch den Brieftext.' : 'Diese lokale Freigabe ist keine klinische Signatur, kein Versand und keine Entscheidung über die Entlassung.'}</p>
          <label className="form-label">Prüfername (mindestens 2 Zeichen)<input required minLength={2} maxLength={100} value={reviewer} onChange={event => setReviewer(event.target.value)} /></label>
          {modal.type === 'review' ? <><label className="form-label">Bewertung<select value={decision} onChange={event => setDecision(event.target.value === 'rejected' ? 'rejected' : 'acknowledged')}><option value="acknowledged">Zur Kenntnis genommen / Umgang dokumentiert</option><option value="rejected">Hinweis begründet verwerfen</option></select><ChevronDown className="select-arrow" size={15} /></label><label className="form-label">Begründung / Klärung<textarea autoFocus required minLength={8} maxLength={2000} rows={4} placeholder="Was wurde geklärt? Was bleibt offen, und wer verfolgt es nach?" value={note} onChange={event => setNote(event.target.value)} /></label></> : <label className="checkbox-label"><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>Ich habe Brieftext, Quellen und Bewertungen geprüft. Offene Sachverhalte sind ausdrücklich dokumentiert. Dies ist ausschließlich eine synthetische Demo.</span></label>}
          {error && <p className="modal-error" role="alert">{error}</p>}
          <div className="modal-actions"><button type="button" className="button" disabled={Boolean(busy)} onClick={() => setModal(null)}>Abbrechen</button><button className="button primary" type="submit" disabled={Boolean(busy) || modalChanged || reviewer.trim().length < 2 || (modal.type === 'review' ? note.trim().length < 8 : !confirmed)}>{busy ? <LoaderCircle size={16} className="spin" /> : <Check size={16} />}{modal.type === 'review' ? 'Bewertung speichern' : 'Demo-Freigabe speichern'}</button></div>
        </form>}
      </dialog>
    </div>
  )
}
