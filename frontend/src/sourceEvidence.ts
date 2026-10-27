import type { AgentRun, SourceDocument } from './types'

export interface SourceEvidence {
  id: string
  title: string
  kind: string
  system: string
  availability: 'available' | 'pending' | 'not_released'
  read: boolean
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object'
}

function source(value: unknown): SourceEvidence | null {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.title !== 'string'
    || typeof value.kind !== 'string' || typeof value.system !== 'string'
    || !['available', 'pending', 'not_released'].includes(String(value.status))) return null
  const availability = value.status === 'available' ? 'available' : value.status === 'pending' ? 'pending' : 'not_released'
  return { id: value.id, title: value.title, kind: value.kind, system: value.system, availability, read: false }
}

export function sourceEvidence(run: AgentRun | null | undefined): SourceEvidence[] {
  const sources = new Map<string, SourceEvidence>()
  for (const event of run?.events ?? []) {
    if (event.kind !== 'tool_result' || !isRecord(event.result)
      || event.result.case_id !== run?.case_id || event.result.source_version !== run?.source_version) continue
    if (event.title === 'list_case_documents' && Array.isArray(event.result.documents)) {
      for (const raw of event.result.documents) {
        const doc = source(raw)
        if (doc) sources.set(doc.id, { ...doc, read: sources.get(doc.id)?.read ?? false })
      }
    }
    if (event.title === 'read_case_document') {
      const doc = source(event.result.document)
      if (doc && doc.availability !== 'not_released' && isRecord(event.result.document)
        && Array.isArray(event.result.document.paragraphs)) sources.set(doc.id, { ...doc, read: true })
    }
  }
  return [...sources.values()]
}

export function readSources(run: AgentRun | null | undefined): Pick<SourceDocument, 'id' | 'title' | 'status'>[] {
  return sourceEvidence(run).filter(doc => doc.read).map(doc => ({
    id: doc.id, title: doc.title, status: doc.availability === 'pending' ? 'pending' : 'available',
  }))
}
