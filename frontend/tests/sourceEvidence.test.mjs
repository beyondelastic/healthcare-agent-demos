import assert from 'node:assert/strict'
import test from 'node:test'
import { readSources, sourceEvidence } from '../src/sourceEvidence.ts'

const doc = (id, status = 'available') => ({
  id, title: id, system: 'LIS · Demo', kind: 'Labor', status,
  paragraphs: [{ id: 'p1', text: 'Synthetischer Originalvermerk.' }],
})
const run = () => ({ case_id: 'DEMO-031', source_version: 1, events: [] })
const result = (title, data) => ({ kind: 'tool_result', title,
  result: { case_id: 'DEMO-031', source_version: 1, ...data } })

test('inventory discovery does not claim document content was read', () => {
  const r = run()
  r.events.push(result('list_case_documents', { documents: [doc('lab'), doc('plan', 'not_released')] }))
  assert.equal(sourceEvidence(r).length, 2)
  assert.equal(sourceEvidence(r).every(item => !item.read), true)
  assert.deepEqual(readSources(r), [])
  assert.equal(sourceEvidence(r)[1].availability, 'not_released')
})

test('actual reads appear incrementally and a pending notice is not a final report', () => {
  const r = run()
  r.events.push(result('list_case_documents', { documents: [doc('lab'), doc('microbiology', 'pending')] }))
  r.events.push(result('read_case_document', { document: doc('lab') }))
  assert.deepEqual(readSources(r).map(item => item.id), ['lab'])
  assert.equal(sourceEvidence(r).find(item => item.id === 'microbiology').read, false)
  r.events.push(result('read_case_document', { document: doc('microbiology', 'pending') }))
  assert.deepEqual(readSources(r).map(item => item.status), ['available', 'pending'])
  assert.equal(sourceEvidence(r)[1].availability, 'pending')
})

test('unreleased read responses never become content or successful reads', () => {
  const r = run()
  r.events.push(result('list_case_documents', { documents: [doc('plan', 'not_released')] }))
  r.events.push({ kind: 'tool_result', title: 'read_case_document',
    result: { case_id: 'DEMO-031', document_id: 'plan', status: 'not_released' } })
  r.events.push(result('read_case_document', { document: doc('plan', 'not_released') }))
  assert.deepEqual(readSources(r), [])
  assert.equal(sourceEvidence(r)[0].read, false)
  assert.equal('paragraphs' in sourceEvidence(r)[0], false)
})

test('foreign case and source-version results cannot contaminate the source collection', () => {
  const r = run()
  r.events.push(result('list_case_documents', { case_id: 'DEMO-014', documents: [doc('foreign')] }))
  r.events.push(result('read_case_document', { source_version: 2, document: doc('future') }))
  assert.deepEqual(sourceEvidence(r), [])
})

test('a repeated inventory or read does not double-count sources or erase read evidence', () => {
  const r = run()
  r.events.push(result('read_case_document', { document: doc('lab') }))
  r.events.push(result('list_case_documents', { documents: [doc('lab')] }))
  r.events.push(result('read_case_document', { document: doc('lab') }))
  assert.equal(sourceEvidence(r).length, 1)
  assert.equal(readSources(r).length, 1)
})

test('errors and malformed responses cannot masquerade as successful content retrieval', () => {
  const r = run()
  r.events.push(result('list_case_documents', { documents: [doc('lab'), null, { id: 'broken' }] }))
  r.events.push({ kind: 'tool_error', title: 'read_case_document', error: 'Abruf fehlgeschlagen' })
  r.events.push(result('read_case_document', { document: { ...doc('lab'), paragraphs: undefined } }))
  r.events.push(result('read_case_document', { document: { ...doc('unknown'), status: 'invented' } }))
  r.events.push(result('list_case_documents', { documents: 'malformed' }))
  assert.equal(sourceEvidence(r).length, 1)
  assert.deepEqual(readSources(r), [])
  assert.deepEqual(sourceEvidence(null), [])
})
