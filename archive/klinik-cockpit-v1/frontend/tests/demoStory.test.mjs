import assert from 'node:assert/strict'
import test from 'node:test'
import { currentLetterCopy, deriveStory, derivePresentationStory, deriveKisGuide } from '../src/demoStory.ts'

function encounter() {
  return {
    id: 'DEMO-031', revision: 4, source_version: 4, status: 'new', draft: null,
    intakes: [{ id: 'scan', status: 'accepted' }],
    followup_tasks: [{ id: 'task', role_label: 'Entlassmanagement', status: 'waiting_for_result' }],
    documents: [{ id: 'microbiology', kind: 'Mikrobiologie', status: 'pending' }],
    event_automation: { enabled: true, events: [] }, kis: { letters: [] },
  }
}

function proposal(c, action = 'none') {
  return { id: 'run', source_version: c.source_version, base_revision: c.revision,
    status: 'awaiting_approval', proposal: { followup: { action, title: 'Keine offene Aufgabe zur Befundprüfung' } } }
}

function draft(c) {
  c.draft = { source_version: c.source_version, sections: [{ id: 'followup', text: 'Originaltext', citations: [] }] }
}

function handover(c) {
  draft(c)
  c.status = 'approved'
  c.kis.letters.push({ id: `copy-${c.source_version}`, source_version: c.source_version,
    sections: structuredClone(c.draft.sections) })
}

test('current real scenario focuses the letter, not a second responsibility action or model-written status', () => {
  const c = encounter()
  const state = deriveStory(c, proposal(c), 'sources')
  assert.equal(state.stage, 'letter')
  assert.equal(state.scene, 'review')
  assert.equal(state.intakeFocus, null)
  assert.match(state.happened, /Entlassmanagement/)
  assert.match(state.happened, /aktuellen Quellenprüfung berücksichtigt/)
  assert.doesNotMatch(state.title, /Keine offene Aufgabe/)
  assert.equal(state.milestones[2], false)
})

test('a ready but unconfirmed scan remains the only active step', () => {
  const c = encounter()
  c.intakes[0].status = 'ready'
  const state = deriveStory(c, null, 'handover')
  assert.equal(state.stage, 'scan')
  assert.equal(state.intakeFocus, 'scan')
  assert.equal(state.scene, 'sources')
  assert.match(state.next, /Original/)
})

test('a new unconfirmed scan does not become a source merely because an older scan was accepted', () => {
  const c = encounter()
  c.intakes.push({ id: 'new-scan', status: 'analyzing' })
  assert.equal(deriveStory(c, null, 'review').stage, 'scan')
})

test('the first completed investigation shows responsibility, not its competing letter proposal', () => {
  const c = encounter()
  c.followup_tasks = []
  const state = deriveStory(c, proposal(c, 'create'), 'review')
  assert.equal(state.stage, 'responsibility')
  assert.equal(state.intakeFocus, 'responsibility')
  assert.equal(state.scene, 'sources')
})

test('queued source events are waiting, not an already completed second investigation', () => {
  const c = encounter()
  c.event_automation.events.push({ status: 'queued' })
  const old = proposal(c)
  old.source_version--
  old.base_revision--
  const state = deriveStory(c, old, 'review')
  assert.equal(state.waiting, true)
  assert.equal(state.scene, 'agent')
  assert.match(state.next, /warten/)
})

test('reloading waits for saved history and does not pretend a model call was started', () => {
  const c = encounter()
  const state = deriveStory(c, null, 'sources', false)
  assert.equal(state.loading, true)
  assert.equal(state.waiting, true)
  assert.match(state.next, /kein neuer Modellaufruf/)
})

test('a stale proposal is not the current review action', () => {
  const c = encounter()
  const r = proposal(c)
  r.base_revision--
  const state = deriveStory(c, r, 'review')
  assert.equal(state.currentProposal, false)
  assert.equal(state.scene, 'agent')
})

test('explicit approval without a copy still requires a separate handover', () => {
  const c = encounter()
  draft(c)
  c.status = 'approved'
  const state = deriveStory(c, null, 'review')
  assert.equal(state.stage, 'letter')
  assert.equal(state.scene, 'handover')
  assert.equal(state.copy, undefined)
})

test('only an exact approved current copy advances to the late-report step', () => {
  const c = encounter()
  handover(c)
  assert.equal(deriveStory(c, null, 'handover').stage, 'result')
  c.draft.sections[0].text = 'Changed'
  assert.equal(currentLetterCopy(c), undefined)
  assert.equal(deriveStory(c, null, 'handover').stage, 'letter')
})

test('old copies stay separate and cannot satisfy an update', () => {
  const c = encounter()
  handover(c)
  c.source_version++
  c.status = 'draft'
  c.documents[0].status = 'available'
  c.followup_tasks[0].status = 'awaiting_review'
  const state = deriveStory(c, null, 'handover')
  assert.equal(state.stage, 'update')
  assert.equal(state.copy, undefined)
  assert.equal(state.scene, 'agent')
  assert.equal(state.intakeFocus, null)
})

test('a new proposal must be accepted before human task completion is the next action', () => {
  const c = encounter()
  c.documents[0].status = 'available'
  c.followup_tasks[0].status = 'awaiting_review'
  assert.equal(deriveStory(c, proposal(c, 'review'), 'review').intakeFocus, null)
  draft(c)
  const state = deriveStory(c, null, 'handover')
  assert.equal(state.intakeFocus, 'complete')
  assert.equal(state.scene, 'review')
  assert.match(state.next, /fachlich prüfen/)
})

test('task completion never implies approval or handover', () => {
  const c = encounter()
  c.documents[0].status = 'available'
  c.followup_tasks[0].status = 'completed'
  draft(c)
  const state = deriveStory(c, null, 'review')
  assert.equal(state.stage, 'update')
  assert.equal(state.scene, 'review')
  assert.equal(state.intakeFocus, null)
})

test('completion requires a current copy and explicit human task completion', () => {
  const c = encounter()
  c.documents[0].status = 'available'
  c.followup_tasks[0].status = 'awaiting_review'
  handover(c)
  assert.notEqual(deriveStory(c, null, 'handover').stage, 'done')
  c.followup_tasks[0].status = 'completed'
  assert.equal(deriveStory(c, null, 'handover').stage, 'done')
})

test('a new review proposal prevents premature completion even when a prior current copy exists', () => {
  const c = encounter()
  c.documents[0].status = 'available'
  c.followup_tasks[0].status = 'completed'
  handover(c)
  assert.equal(deriveStory(c, proposal(c), 'review').stage, 'update')
})

test('event failures remain visible and do not look like successful inference', () => {
  const c = encounter()
  c.event_automation.events.push({ status: 'failed', error: 'Actual Azure error' })
  const state = deriveStory(c, null, 'review')
  assert.equal(state.waiting, false)
  assert.equal(state.error, 'Actual Azure error')
  assert.equal(state.scene, 'agent')
  assert.doesNotMatch(state.title, /gespeichert/)
})

test('a completed current run supersedes a briefly stale running-event snapshot', () => {
  const c = encounter()
  const r = proposal(c)
  c.event_automation.events.push({ status: 'running', run_id: r.id })
  const state = deriveStory(c, r, 'agent')
  assert.equal(state.waiting, false)
  assert.equal(state.scene, 'review')
})

test('cases without a microbiology source do not invent a pending report after handover', () => {
  const c = encounter()
  c.documents = []
  c.followup_tasks = []
  handover(c)
  const state = deriveStory(c, null, 'review')
  assert.equal(state.stage, 'done')
  assert.doesNotMatch(state.title, /Befund/)
})

function baseline() {
  const c = encounter()
  c.intakes = []
  c.followup_tasks = []
  c.event_automation.enabled = false
  c.kis.medication_released = false
  c.findings = [{ id: 'pending', review: null }]
  return c
}

test('a fresh demo starts with the source investigation, not scan upload or plan release', () => {
  const c = baseline()
  const state = derivePresentationStory(c, null, 'sources')
  assert.equal(state.chapter, 1)
  assert.equal(state.stage, 'start')
  assert.equal(state.scene, 'sources')
  assert.equal(state.needsAgent, true)
  assert.equal(state.intakeFocus, null)
  assert.match(state.next, /Quellen mit Agent prüfen/)
  assert.doesNotMatch(state.title + state.happened, /Medikationsplan.*fehlt|Der Agent erkennt|Demo/)
})

test('a completed first investigation stays on source review regardless of the requested scene', () => {
  const c = baseline()
  for (const scene of ['sources', 'agent', 'review', 'handover']) {
    const state = derivePresentationStory(c, proposal(c), scene)
    assert.equal(state.stage, 'investigation')
    assert.equal(state.active, 0)
    assert.equal(state.scene, 'sources')
    assert.equal(state.needsAgent, false)
    assert.equal(state.title, 'Quellenprüfung abgeschlossen')
    assert.match(state.next, /Quellen und offene Punkte sichten/)
  }
})

test('only explicit source-result continuation opens the medication action', () => {
  const c = baseline()
  const state = derivePresentationStory(c, proposal(c), 'sources', true, false, null, true)
  assert.equal(state.stage, 'medication')
  assert.equal(state.scene, 'review')
  assert.equal(state.needsAgent, false)
  assert.equal(state.title, 'Medikationsplan nicht verfügbar')
  assert.match(state.next, /Medikationsmodul öffnen/)
  assert.equal(c.draft, null)
  assert.equal(c.kis.medication_released, false)
})

test('returning from KIS or reloading after plan release keeps the medication continuation, never Ausgangslage', () => {
  const c = baseline()
  const old = proposal(c)
  c.kis.medication_released = true
  c.source_version++
  c.revision++
  for (const scene of ['sources', 'review', 'agent']) {
    const state = derivePresentationStory(c, old, scene)
    assert.equal(state.stage, 'medication')
    assert.equal(state.active, 1)
    assert.equal(state.currentProposal, false)
    assert.equal(state.needsAgent, true)
    assert.match(state.happened, /bisherige Vorschlag bleibt gespeichert/)
    assert.match(state.next, /Neue Quelle mit Agent prüfen/)
  }
})

test('a refreshed investigation stays on medication until explicit continuation to letter review', () => {
  const c = baseline()
  const previous = proposal(c)
  previous.source_version--
  c.kis.medication_released = true
  const checkpoint = derivePresentationStory(c, proposal(c), 'review', true, false, previous)
  assert.equal(checkpoint.stage, 'investigation')
  assert.equal(checkpoint.active, 1)
  assert.equal(checkpoint.scene, 'sources')
  const state = derivePresentationStory(c, proposal(c), 'sources', true, false, previous, true)
  assert.equal(state.stage, 'initial-letter')
  assert.equal(state.scene, 'review')
  assert.equal(state.focusSection, 'medication')
  assert.equal(state.currentProposal, true)
})

test('the second run keeps medication context while running or failing instead of jumping to step one', () => {
  const c = baseline()
  const old = proposal(c)
  c.kis.medication_released = true
  c.source_version++
  c.revision++
  const running = { id: 'new-run', source_version: c.source_version, base_revision: c.revision, status: 'running', proposal: null }
  const state = derivePresentationStory(c, running, 'agent', true, false, old)
  assert.equal(state.stage, 'medication')
  assert.equal(state.active, 1)
  assert.equal(state.waiting, true)
  assert.equal(state.needsAgent, false)
  assert.match(state.title, /freigegebenem Medikationsplan/)
  running.status = 'failed'
  assert.equal(derivePresentationStory(c, running, 'agent', true, false, old).stage, 'medication')
  assert.equal(derivePresentationStory(c, running, 'agent', true, false, old).needsAgent, true)
})

test('a same-source case change invalidates review without pretending the medication source is new again', () => {
  const c = baseline()
  c.kis.medication_released = true
  const previous = proposal(c)
  previous.source_version--
  const latest = proposal(c)
  c.revision++
  const state = derivePresentationStory(c, latest, 'review', true, false, previous)
  assert.equal(state.stage, 'initial-letter')
  assert.equal(state.currentProposal, false)
  assert.equal(state.needsAgent, true)
  assert.doesNotMatch(state.happened, /alten Quellen/)
})

test('baseline acceptance, finding review, approval and handover remain four separate states', () => {
  const c = baseline()
  c.kis.medication_released = true
  draft(c)
  assert.equal(derivePresentationStory(c, null, 'review').scene, 'review')
  assert.equal(derivePresentationStory(c, null, 'handover').scene, 'handover')
  c.findings[0].review = { decision: 'acknowledged' }
  const reviewed = derivePresentationStory(c, null, 'sources')
  assert.equal(reviewed.scene, 'handover')
  assert.match(reviewed.next, /freigeben/)
  c.status = 'approved'
  assert.equal(derivePresentationStory(c, null, 'sources').stage, 'initial-copy')
  assert.match(derivePresentationStory(c, null, 'sources').next, /separate Kopie/)
  handover(c)
  const handedOver = derivePresentationStory(c, null, 'sources')
  assert.equal(handedOver.stage, 'initial-done')
  assert.match(handedOver.next, /Dokumenteingang öffnen/)
})

test('scan chapter starts only explicitly or when a persisted scan or task exists', () => {
  const c = baseline()
  c.kis.medication_released = true
  handover(c)
  assert.equal(derivePresentationStory(c, null, 'sources').chapter, 1)
  assert.equal(derivePresentationStory(c, null, 'sources', true, true).stage, 'scan')
  c.intakes.push({ id: 'scan', status: 'ready' })
  assert.equal(derivePresentationStory(c, null, 'sources').chapter, 2)
})

test('the baseline handover never checks off the later scan-letter milestone', () => {
  const c = baseline()
  c.kis.medication_released = true
  handover(c)
  c.intakes.push({ id: 'scan', status: 'ready' })
  assert.equal(derivePresentationStory(c, null, 'sources').milestones[2], false)
  c.intakes[0].status = 'accepted'
  c.source_version++
  c.status = 'draft'
  assert.equal(derivePresentationStory(c, null, 'sources').milestones[2], false)
})

test('manual responsibility confirmation does not claim that a new agent run already happened', () => {
  const c = encounter()
  c.event_automation.enabled = false
  const previous = proposal(c)
  previous.source_version--
  previous.base_revision--
  const state = deriveStory(c, previous, 'sources')
  assert.equal(state.waiting, false)
  assert.match(state.happened, /noch berücksichtigen/)
  assert.doesNotMatch(state.happened, /gab es einen weiteren Agentenlauf/)
})

test('an archived responsibility-source letter preserves the handover milestone after a new lab result', () => {
  const c = encounter()
  c.documents.push({ id: 'scan-source', intake_id: 'scan', kind: 'Fremddokument' },
    { id: 'confirmed-task', kind: 'Aufgabenbestätigung' })
  handover(c)
  c.kis.letters[0].sections[0].citations = [{ document_id: 'confirmed-task', paragraph_id: 'p1' }]
  c.source_version++
  c.status = 'draft'
  c.documents[0].status = 'available'
  c.followup_tasks[0].status = 'awaiting_review'
  const state = deriveStory(c, proposal(c, 'review'), 'review')
  assert.equal(state.stage, 'update')
  assert.equal(state.copy, undefined)
  assert.equal(state.milestones[2], true)
  assert.equal(state.milestones[4], false)
})

test('KIS guides only medication first, then return, reserving report publication until the scan letter is handed over', () => {
  const c = baseline()
  assert.equal(deriveKisGuide(c).action, 'medication')
  c.kis.medication_released = true
  assert.equal(deriveKisGuide(c).action, 'return')
  handover(c)
  assert.equal(deriveKisGuide(c).action, 'return')
  c.intakes.push({ status: 'accepted' })
  c.followup_tasks.push({ status: 'waiting_for_result' })
  c.source_version++
  assert.equal(deriveKisGuide(c).action, 'return')
  handover(c)
  assert.equal(deriveKisGuide(c).action, 'report')
  c.documents[0].status = 'available'
  c.event_automation.enabled = true
  const arrived = deriveKisGuide(c)
  assert.equal(arrived.action, 'return')
  assert.match(arrived.next, /automatisch ausgelösten/)
})
