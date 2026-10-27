import type { AgentRun } from './types'
import { sourceEvidence } from './sourceEvidence.ts'

const tools = [
  ['list_case_documents', 'Dokumentenbestand'],
  ['read_case_document', 'Dokumentinhalte'],
  ['get_case_workflow', 'Fallstatus und Prüfpunkte'],
  ['get_laboratory_status', 'Laborstatus'],
  ['get_followup_context', 'Aufgaben und Zuständigkeiten'],
]

export function agentActivity(run: AgentRun) {
  const calls = run.events.filter(event => event.kind === 'tool_call')
  const results = run.events.filter(event => event.kind === 'tool_result')
  const errors = run.events.filter(event => event.kind === 'tool_error')
  const sources = sourceEvidence(run)
  return {
    modelCalls: run.events.filter(event => event.kind === 'model_call').length,
    modelResponses: run.events.filter(event => event.kind === 'model_result').length,
    toolCalls: calls.length,
    toolResponses: results.length,
    toolErrors: errors.length,
    sourcesRead: sources.filter(source => source.read).length,
    pendingNotices: sources.filter(source => source.read && source.availability === 'pending').length,
    tools: tools.map(([name, label]) => ({
      name, label,
      calls: calls.filter(event => event.title === name).length,
      responses: results.filter(event => event.title === name).length,
      errors: errors.filter(event => event.title === name).length,
    })).filter(tool => tool.calls || tool.responses || tool.errors),
    changedSections: run.proposal?.sections.filter(section => run.proposal?.changed_section_ids.includes(section.id)) ?? [],
  }
}
