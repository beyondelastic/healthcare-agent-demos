import assert from 'node:assert/strict'
import test from 'node:test'
import { agentActivity } from '../src/agentActivitySummary.ts'

const run = () => ({ id: 'run', case_id: 'DEMO-031', source_version: 4, events: [], proposal: null })
const event = (kind, title, result) => ({ kind, title, result })
const source = (id, status) => ({ id, title: id, kind: 'Labor', system: 'LIS',
  status, paragraphs: [{ id: 'p1', text: 'Original.' }] })
const result = document => ({ case_id: 'DEMO-031', source_version: 4, document })

test('activity counts actual model and tool events, not inferred thinking steps', () => {
  const r = run()
  assert.equal(agentActivity(r).modelCalls, 0)
  r.events.push(event('model_call', 'Modellaufruf 1'), event('model_result', 'Antwort'),
    event('tool_call', 'get_laboratory_status'), event('tool_result', 'get_laboratory_status'),
    event('tool_call', 'read_case_document'), event('tool_error', 'read_case_document'),
    event('model_call', 'Modellaufruf 2'))
  const activity = agentActivity(r)
  assert.equal(activity.modelCalls, 2)
  assert.equal(activity.modelResponses, 1)
  assert.equal(activity.toolCalls, 2)
  assert.equal(activity.toolResponses, 1)
  assert.equal(activity.toolErrors, 1)
  assert.equal(activity.sourcesRead, 0)
  assert.equal(activity.tools.find(t => t.name === 'read_case_document').errors, 1)
  assert.equal(activity.tools.some(t => t.name === 'get_followup_context'), false)
})

test('inventory and unreleased replies are answers, not successful content reads', () => {
  const r = run()
  r.events.push(event('tool_result', 'list_case_documents', {
    case_id: r.case_id, source_version: 4, documents: [source('lab', 'pending'), source('plan', 'not_released')],
  }))
  r.events.push(event('tool_result', 'read_case_document', result(source('lab', 'pending'))))
  r.events.push(event('tool_result', 'read_case_document', result(source('lab', 'pending'))))
  r.events.push(event('tool_result', 'read_case_document', result(source('plan', 'not_released'))))
  const activity = agentActivity(r)
  assert.equal(activity.toolResponses, 4)
  assert.equal(activity.sourcesRead, 1)
  assert.equal(activity.pendingNotices, 1)
  assert.equal(activity.modelCalls, 0)
})

test('changed-section labels come only from the actual proposal and its change IDs', () => {
  const r = run()
  r.events.push(event('validation', 'No invented model call'))
  r.proposal = { sections: [{ id: 'medication', title: 'Entlassmedikation' },
    { id: 'followup', title: 'Weiterbehandlung' }], changed_section_ids: ['followup'] }
  assert.deepEqual(agentActivity(r).changedSections.map(s => s.title), ['Weiterbehandlung'])
  assert.equal(agentActivity(r).modelCalls, 0)
})
