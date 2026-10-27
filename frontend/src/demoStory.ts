import type { AgentRun, Encounter } from './types'
import type { Scene } from './Presentation'

export type StoryStage = 'start' | 'investigation' | 'medication' | 'initial-letter' | 'initial-copy' | 'initial-done'
  | 'scan' | 'responsibility' | 'letter' | 'result' | 'update' | 'done'
export type IntakeFocus = 'scan' | 'responsibility' | 'complete'

export function currentLetterCopy(encounter: Encounter) {
  if (encounter.status !== 'approved' || !encounter.draft
    || encounter.draft.source_version !== encounter.source_version) return undefined
  const draft = encounter.draft
  return [...encounter.kis.letters].reverse().find(letter => letter.source_version === draft.source_version
    && JSON.stringify(letter.sections) === JSON.stringify(draft.sections))
}

export function deriveStory(encounter: Encounter, run: AgentRun | null, requestedScene: Scene, historyReady = true) {
  const scan = encounter.intakes.at(-1)
  const accepted = encounter.intakes.some(item => item.status === 'accepted')
  const laboratory = encounter.documents.find(doc => doc.kind === 'Mikrobiologie')
  const reportAvailable = laboratory?.status === 'available'
  const task = encounter.followup_tasks[0]
  const event = encounter.event_automation.events.at(-1)
  const eventWaiting = (event?.status === 'queued' || event?.status === 'running')
    && !(event.run_id && event.run_id === run?.id && run.status !== 'running')
  const waiting = !historyReady || (run?.status === 'running' && run.source_version === encounter.source_version) || eventWaiting
  const currentProposal = run?.status === 'awaiting_approval' && run.base_revision === encounter.revision
  const currentDraft = encounter.draft?.source_version === encounter.source_version
  const copy = currentLetterCopy(encounter)
  const taskReviewed = encounter.followup_tasks.every(item => item.status === 'completed')
  const followupSourceIds = new Set(encounter.documents.filter(doc => doc.intake_id
    || doc.kind === 'Aufgabenbestätigung').map(doc => doc.id))
  const scanLetterHandedOver = accepted && (Boolean(copy) || encounter.kis.letters.some(letter =>
    letter.sections.some(section => section.citations.some(citation => followupSourceIds.has(citation.document_id)))))
  const noAssignmentProposed = run?.source_version === encounter.source_version
    && (currentProposal || run.status === 'applied') && run.proposal?.followup?.action === 'none'
  let stage: StoryStage
  if (!accepted || (scan && scan.status !== 'accepted')) stage = 'scan'
  else if (reportAvailable || (!laboratory && copy)) stage = copy && taskReviewed && !currentProposal && !waiting ? 'done' : 'update'
  else if (!task && !noAssignmentProposed) stage = 'responsibility'
  else stage = copy && !currentProposal && !waiting ? 'result' : 'letter'

  const reviewingLetter = stage === 'letter' || stage === 'update'
  const needsTaskReview = stage === 'update' && currentDraft && task?.status === 'awaiting_review'
    && !currentProposal && !waiting
  const intakeFocus: IntakeFocus | null = stage === 'scan' ? 'scan'
    : stage === 'responsibility' && !waiting && currentProposal ? 'responsibility'
      : needsTaskReview ? 'complete' : null
  const scene: Scene = waiting ? 'agent'
    : reviewingLetter ? currentProposal ? 'review'
      : currentDraft ? needsTaskReview ? 'review'
        : encounter.status === 'approved' || requestedScene === 'handover'
          || encounter.findings?.every(finding => Boolean(finding.review)) ? 'handover' : 'review'
        : 'agent'
      : stage === 'responsibility' && !currentProposal ? 'agent' : 'sources'

  let title = ''
  let happened = ''
  let next = ''
  if (stage === 'scan') {
    title = scan?.status === 'analyzing' ? 'Dokumentanalyse läuft' : scan?.status === 'ready' ? 'Dokumentanalyse zur Prüfung bereit' : 'Dokumenteingang'
    happened = scan?.status === 'ready'
      ? 'Azure hat Text und Fundstellen erkannt. Das Dokument ist noch nicht als Quelle bestätigt.'
      : scan?.status === 'failed' ? 'Die Dokumentanalyse ist fehlgeschlagen. Es wurde keine Quelle übernommen.'
        : 'Ein externes Dokument kann diesem Aufenthalt als zusätzliche Quelle zugeordnet werden.'
    next = scan?.status === 'analyzing' ? 'Auf das Analyseergebnis warten.'
      : scan?.status === 'ready' ? 'Original und erkannte Angaben vergleichen. Danach den Scan ausdrücklich als Quelle bestätigen.'
        : scan?.status === 'failed' ? 'Fehlermeldung prüfen; einen erneuten Azure-Aufruf ausdrücklich bestätigen.'
          : 'Dokument auswählen und die Verarbeitung synthetischer Daten bestätigen.'
  } else if (stage === 'responsibility') {
    title = waiting ? 'Befundnachverfolgung wird abgeglichen' : 'Zuständigkeit für die Befundnachverfolgung offen'
    happened = 'Der geprüfte Scan ist eine neue Quelle. Der Abschlussbefund steht noch aus; eine Aufgabe ist noch nicht bestätigt.'
    next = waiting ? 'Der Agent gleicht Scan, Labor und vorhandene Aufgaben ab. Noch nichts bestätigen.'
      : currentProposal ? 'Vorgeschlagene Nachverfolgung prüfen und eine zuständige Rolle ausdrücklich bestätigen.'
        : 'Den Agentenauftrag starten oder den fehlgeschlagenen Lauf prüfen. Es wird keine Verantwortung automatisch zugeordnet.'
  } else if (stage === 'result') {
    title = 'Abschlussbefund ausstehend'
    happened = `Eine unveränderliche Briefkopie liegt im Demo-KIS. ${task
      ? 'Die bestätigte Aufgabe wartet weiterhin auf den Abschlussbefund.'
      : 'Der Abschlussbefund steht weiterhin aus. Eine Nachverfolgungsaufgabe wurde nicht zugeordnet.'}`
    next = 'Den Laborstatus im Quellsystem öffnen. Ein neuer Befundeingang wird dort bereitgestellt.'
  } else if (stage === 'done') {
    title = reportAvailable ? 'Befund dokumentiert und Brief aktualisiert' : 'Entlassbrief abgelegt'
    happened = `Der aktuelle Brief wurde separat übergeben. ${task ? 'Die Nachverfolgung ist menschlich abgeschlossen; ' : ''}Ältere Briefkopien bleiben unverändert.`
    next = 'Aktueller und früherer Briefstand können in der Briefablage eingesehen werden.'
  } else {
    const updating = stage === 'update'
    title = waiting ? 'Briefvorschlag wird aktualisiert'
      : needsTaskReview ? 'Befundprüfung und Aufgabenabschluss'
        : currentProposal ? updating ? 'Aktualisierten Brief prüfen' : 'Briefvorschlag mit bestätigter Zuständigkeit'
          : scene === 'handover' ? encounter.status === 'approved' ? 'Brief zur Übergabe bereit' : 'Brief zur Freigabe prüfen'
            : currentDraft ? 'Briefentwurf gespeichert' : 'Aktueller Briefvorschlag ausstehend'
    happened = updating
      ? 'Der Abschlussbefund liegt jetzt vor. Das ändert die Quellenlage, schließt aber keine Aufgabe automatisch ab.'
      : task ? `${task.role_label} ist als zuständige Stelle bestätigt. Diese Bestätigung ist eine neue Quelle; ${run?.source_version === encounter.source_version
        ? 'sie wird in der aktuellen Quellenprüfung berücksichtigt.' : 'der Brief muss diesen neuen Quellenstand noch berücksichtigen.'}`
        : 'Der Agent hat keine zusätzliche Zuordnung vorgeschlagen. Der Brief bleibt menschlich zu prüfen.'
    if (!waiting && !currentProposal && currentDraft) {
      happened = encounter.status === 'approved'
        ? 'Der aktuelle Brief ist ausdrücklich demo-freigegeben. Eine Briefkopie wurde für diesen Stand noch nicht übergeben.'
        : needsTaskReview
          ? 'Der aktualisierte Vorschlag wurde als Entwurf übernommen. Der Befund liegt vor; die Nachverfolgungsaufgabe ist noch nicht menschlich abgeschlossen.'
          : updating && task && taskReviewed
            ? 'Die Nachverfolgung ist menschlich abgeschlossen. Der aktuelle Brief muss noch separat geprüft, freigegeben und übergeben werden.'
            : 'Der Vorschlag wurde als bearbeitbarer Entwurf übernommen. Das ist noch keine Demo-Freigabe und keine KIS-Übergabe.'
    }
    next = waiting ? 'Auf den neuen Vorschlag warten. Der bestehende Brief wird nicht automatisch überschrieben.'
      : currentProposal ? 'Zuerst „Weiterbehandlung und offene Befunde“, dann alle sechs Abschnitte prüfen. Den Vorschlag anschließend ausdrücklich übernehmen.'
        : needsTaskReview ? 'Abschlussbefund und Dokumentation fachlich prüfen und die Nachverfolgungsaufgabe ausdrücklich abschließen.'
          : scene === 'handover' ? encounter.status === 'approved' ? 'Die Kopie separat mit „Geprüften Entwurf ins Demo-KIS“ bestätigen.'
            : 'Offene Prüfpunkte bewerten und anschließend die Demo-Freigabe ausdrücklich bestätigen.'
            : currentDraft ? 'Brieftext und Quellen fachlich prüfen. Danach weiter zur menschlichen Freigabe.'
              : 'Es gibt noch keinen aktuellen Entwurf. Den Agentenlauf prüfen oder einen neuen Auftrag starten.'
  }
  if (!historyReady) {
    title = 'Gespeicherten Fallstand laden'
    next = 'Aufgaben und Agentenprotokoll werden geladen. Dadurch wird kein neuer Modellaufruf gestartet.'
  }
  return { stage, scene, title, happened, next, intakeFocus, waiting, loading: !historyReady, currentProposal, reportAvailable, task, copy,
    milestones: [accepted, Boolean(task) || Boolean(noAssignmentProposed), Boolean(scanLetterHandedOver),
      reportAvailable, stage === 'done'], error: event?.status === 'failed' ? event.error : null }
}

export function derivePresentationStory(encounter: Encounter, run: AgentRun | null, requestedScene: Scene,
  historyReady = true, scanStarted = false, previousRun: AgentRun | null = null, investigationReviewed = false) {
  const extended = scanStarted || encounter.intakes.length > 0 || encounter.followup_tasks.length > 0
  const scanSteps = ['Scan prüfen', 'Verantwortung klären', 'Brief übergeben', 'Befund nachreichen', 'Aktualisierung prüfen']
  if (extended) {
    const story = deriveStory(encounter, run, requestedScene, historyReady)
    const active = ['scan', 'responsibility', 'letter', 'result', 'update', 'done'].indexOf(story.stage)
    return { ...story, chapter: 2, steps: scanSteps, active: Math.min(active, 4), focusSection: 'followup',
      needsAgent: !story.waiting && story.scene === 'agent' }
  }

  const currentProposal = run?.status === 'awaiting_approval' && run.base_revision === encounter.revision
    && run.source_version === encounter.source_version
  const waiting = !historyReady || run?.status === 'running'
  const currentDraft = encounter.draft?.source_version === encounter.source_version
  const copy = currentLetterCopy(encounter)
  const reportAvailable = encounter.documents.some(doc => doc.kind === 'Mikrobiologie' && doc.status === 'available')
  const released = encounter.kis.medication_released
  const sourceChanged = Boolean(run && run.source_version !== encounter.source_version)
  const openFindings = encounter.findings.filter(finding => !finding.review).length
  const hadInvestigation = Boolean(run?.proposal || previousRun?.proposal || encounter.draft)
  const medicationUpdate = released && !currentDraft && (sourceChanged
    || Boolean(!run?.proposal && previousRun?.proposal && previousRun.source_version !== encounter.source_version))
  const stage: StoryStage = copy && !currentProposal && !waiting ? 'initial-done'
    : currentProposal && !encounter.draft && !investigationReviewed ? 'investigation'
      : (!released && hadInvestigation) || (medicationUpdate && !currentProposal) ? 'medication'
        : currentProposal || currentDraft ? encounter.status === 'approved' ? 'initial-copy' : 'initial-letter'
          : hadInvestigation ? 'initial-letter' : 'start'
  let scene: Scene = waiting ? 'agent'
    : stage === 'initial-done' || stage === 'investigation' ? 'sources'
      : stage === 'initial-copy' ? 'handover'
        : stage === 'medication' ? !released && currentProposal ? 'review' : 'agent'
          : currentProposal ? 'review'
            : currentDraft ? requestedScene === 'handover' || openFindings === 0 ? 'handover' : 'review'
              : 'agent'
  let title = ''
  let happened = ''
  let next = ''
  if (stage === 'start') {
    title = waiting ? 'Quellen werden geprüft' : 'Entlassdokumentation vorbereiten'
    happened = 'Aufnahme, Verlauf und Befunde liegen in getrennten Dokumenten. Noch kein Brief wurde übernommen.'
    next = waiting ? 'Verfügbare Dokumente und ihr Abrufstatus erscheinen unten. Auf das Ergebnis der Quellenprüfung warten.'
      : '„Quellen mit Agent prüfen“ wählen, um verfügbare Dokumente und offene Punkte zu ermitteln.'
    if (!waiting) scene = 'sources'
  } else if (stage === 'investigation') {
    title = 'Quellenprüfung abgeschlossen'
    happened = 'Die abgerufenen Dokumente und ihre Verfügbarkeit sind unten aufgeführt. Der Briefvorschlag wurde noch nicht übernommen.'
    next = released ? 'Quellen und offene Punkte sichten. Anschließend den Briefvorschlag öffnen.'
      : 'Quellen und offene Punkte sichten. Anschließend „Medikationsplan prüfen“ wählen.'
  } else if (stage === 'medication') {
    title = waiting ? 'Quellenprüfung mit freigegebenem Medikationsplan'
      : released ? 'Medikationsplan verfügbar'
        : 'Medikationsplan nicht verfügbar'
    happened = released
      ? 'Der Medikationsplan wurde im Quellsystem freigegeben. Der bisherige Vorschlag bleibt gespeichert; die Quellenprüfung muss den neuen Stand noch berücksichtigen.'
      : 'Im Medikationsmodul liegt ein noch nicht freigegebener Plan vor. Für die Entlassmedikation ist daraus kein freigegebener Inhalt verfügbar.'
    next = waiting ? 'Auf den neuen Vorschlag warten. Der bisherige Text wird nicht automatisch übernommen.'
      : released ? '„Neue Quelle mit Agent prüfen“ wählen, um den freigegebenen Plan einzubeziehen.'
        : 'Das Medikationsmodul öffnen und die Freigabe des Plans prüfen. Danach zum Cockpit zurückkehren.'
  } else if (stage === 'initial-done') {
    title = 'Entlassbrief abgelegt'
    happened = 'Vorschlag übernommen, Prüfpunkte bewertet, Demo-Freigabe erteilt und eine unveränderliche Kopie separat übergeben. Der Abschlussbefund kann weiterhin ausstehen.'
    next = 'Die Briefkopie ist in der Ablage einsehbar. Weitere Unterlagen können über „Dokumenteingang öffnen“ ergänzt werden.'
  } else {
    title = waiting ? 'Briefvorschlag wird erstellt'
      : currentProposal ? 'Briefvorschlag zur Prüfung bereit'
        : encounter.status === 'approved' ? 'Brief zur Übergabe bereit'
          : scene === 'handover' ? openFindings ? 'Offene Prüfpunkte bewerten' : 'Brief zur Freigabe bereit'
            : currentDraft ? 'Briefentwurf gespeichert · Freigabe ausstehend' : 'Erneute Quellenprüfung erforderlich'
    happened = currentProposal
      ? 'Der Agent hat die aktuell verfügbaren Quellen gelesen. Der Vorschlag ist noch kein gespeicherter Entwurf und keine Freigabe.'
      : encounter.status === 'approved'
        ? 'Die menschliche Demo-Freigabe ist gespeichert. Im KIS liegt für diesen Stand noch keine Briefkopie.'
        : currentDraft ? 'Alle sechs Abschnitte sind als bearbeitbarer Entwurf gespeichert. Offene Befunde bleiben ausdrücklich gekennzeichnet.'
          : 'Es gibt noch keinen übernehmbaren Vorschlag für den aktuellen Fallstand. Der vorhandene Brief bleibt unverändert.'
    next = waiting ? 'Auf den Briefvorschlag warten. Keine automatische Briefübernahme.'
      : currentProposal ? 'Zuerst „Entlassmedikation“, dann alle sechs Abschnitte und Quellen prüfen. Danach den Vorschlag ausdrücklich übernehmen.'
        : encounter.status === 'approved' ? '„Geprüften Entwurf ins Demo-KIS“ wählen und die separate Kopie bestätigen.'
          : scene === 'handover' ? openFindings
            ? 'Jeden unbewerteten Prüfpunkt öffnen und den Umgang damit dokumentieren. Eine Bewertung macht einen ausstehenden Befund nicht verfügbar.'
            : '„Demo-Entwurf freigeben“ wählen. Die Übergabe folgt danach als eigene Aktion.'
            : currentDraft ? 'Brieftext und Quellen prüfen, dann „Weiter zur menschlichen Freigabe“ wählen.'
              : 'Den Agenten erneut mit dem aktuellen Quellenstand beauftragen.'
  }
  if (!historyReady) {
    title = 'Gespeicherten Fallstand laden'
    next = 'Das Agentenprotokoll wird geladen. Dadurch wird kein neuer Modellaufruf gestartet.'
  }
  return { stage, scene, title, happened, next, intakeFocus: null, waiting, loading: !historyReady, currentProposal,
    reportAvailable, task: encounter.followup_tasks[0], copy, error: null,
    milestones: [hadInvestigation, released, Boolean(currentDraft && openFindings === 0), Boolean(copy)],
    chapter: 1, steps: ['Quellen prüfen', 'Medikation ergänzen', 'Brief prüfen', 'Brief übergeben'],
    active: stage === 'start' ? 0 : stage === 'investigation'
      ? released && previousRun?.proposal && previousRun.source_version !== encounter.source_version ? 1 : 0
      : stage === 'medication' ? 1 : stage === 'initial-letter' && scene !== 'handover' ? 2 : 3,
    focusSection: 'medication', needsAgent: !waiting && (stage === 'start' || scene === 'agent') }
}

export function deriveKisGuide(encounter: Encounter) {
  const pending = encounter.documents.some(doc => doc.kind === 'Mikrobiologie' && doc.status === 'pending')
  const copy = currentLetterCopy(encounter)
  const readyForReport = Boolean(copy && encounter.intakes.some(item => item.status === 'accepted')
    && (encounter.followup_tasks.length === 0 || encounter.followup_tasks.some(task => task.status === 'waiting_for_result')))
  const action = !encounter.kis.medication_released ? 'medication' : pending && readyForReport ? 'report' : 'return'
  const title = action === 'medication' ? 'Medikationsplan zur Freigabe'
    : action === 'report' ? 'Abschlussbefund zur Bereitstellung'
      : !pending ? 'Abschlussbefund verfügbar' : 'Medikationsplan verfügbar'
  const next = action === 'medication'
    ? 'Nur den vorbereiteten Medikationsplan freigeben. Danach zum Cockpit zurückkehren; der Agent muss die neue Quelle erst lesen.'
    : action === 'report'
      ? 'Den Abschlussbefund ausdrücklich bereitstellen. Die bestätigte Aufgabe wird dadurch nicht abgeschlossen.'
      : !pending
        ? encounter.event_automation.enabled
          ? 'Zum Cockpit zurückkehren. Dort den automatisch ausgelösten Agentenlauf und anschließend den Änderungsvorschlag prüfen.'
          : 'Zum Cockpit zurückkehren und den Agenten mit den neuen Quellen beauftragen.'
        : 'Zum Cockpit zurückkehren und die neue Quelle prüfen. Der Abschlussbefund steht weiterhin aus.'
  return { action, title, next, readyForReport }
}
