export interface Citation {
  document_id: string
  paragraph_id: string
  quote: string
}

export interface Section {
  id: string
  title: string
  text: string
  citations: Citation[]
}

export interface SourceDocument {
  id: string
  title: string
  kind: string
  system: string
  date: string
  status: 'available' | 'pending'
  paragraphs: { id: string; text: string; regions?: ScanRegion[] }[]
  intake_id?: string
}

export interface Review {
  decision: 'acknowledged' | 'rejected'
  note: string
  reviewer: string
  at: string
}

export interface Finding {
  id: string
  type: 'missing' | 'conflict' | 'pending'
  severity: 'blocking'
  title: string
  description: string
  action: string
  document_ids: string[]
  section_ids: string[]
  review: Review | null
  resolved?: boolean
}

export interface CaseSummary {
  id: string
  name: string
  age: number
  initials: string
  department: string
  label: string
  status: 'new' | 'draft' | 'approved'
  revision: number
  open_findings: number
  documents: number
}

export interface Encounter {
  id: string
  name: string
  age: number
  initials: string
  department: string
  admitted: string
  discharge: string
  label: string
  revision: number
  source_version: number
  intakes: DocumentIntake[]
  followup_tasks: FollowupTask[]
  event_automation: { enabled: boolean; events: SourceEvent[] }
  kis: {
    medication_released: boolean
    retrieval_fault: boolean
    letters: { id: string; at: string; reviewer: string; source_version: number; sections: Section[]; label: string }[]
  }
  documents: SourceDocument[]
  findings: Finding[]
  status: 'new' | 'draft' | 'approved'
  draft: {
    sections: Section[]
    mode: 'foundry' | 'rehearsal'
    model: string
    usage: { input_tokens: number; output_tokens: number; total_tokens: number } | null
    duration_seconds: number
    source_version: number
    edited: boolean
  } | null
  approval: { reviewer: string; at: string } | null
  followup_resolution?: { date: string; note: string; reviewer: string; at: string; document_id: string }
  audit: { id: string; at: string; action: string; detail: string; reviewer: string }[]
}

export interface Health {
  status: string
  synthetic_only: boolean
  foundry: { project: string; model: string; configured: boolean; authentication: string; note: string }
  agent: { name: string; version: string; configured: boolean; tools: string; tracing: string }
  document_analysis: { configured: boolean; service: string; synthetic_only: boolean; note: string }
  followup_roles: { id: string; label: string; system: string }[]
}

export interface AgentRun {
  id: string
  case_id: string
  created_at: string
  status: 'running' | 'awaiting_approval' | 'applied' | 'rejected' | 'failed'
  base_revision: number
  source_version: number
  base_sections: Section[]
  trigger?: { id: string; kind: string; title: string }
  error: string | null
  events: { at: string; kind: string; title: string; response_id?: string; arguments?: string; result?: unknown; error?: string }[]
  proposal: {
    sections: Section[]
    summary: string
    next_actions: string[]
    changed_section_ids: string[]
    duration_seconds: number
    response_ids: string[]
    followup?: {
      action: 'create' | 'review' | 'none'; title: string; reason: string
      role_id: string | null; citations: Citation[]
    } | null
  } | null
}

export interface ScanRegion {
  page: number; x: number; y: number; width: number; height: number
}

export interface DocumentIntake {
  id: string; at: string; filename: string; sha256: string; page_count: number
  status: 'analyzing' | 'ready' | 'accepted' | 'failed'
  error: string | null; document_id: string | null; reviewer: string | null
  extraction: {
    fields: Record<string, { value: string; confidence: number | null; regions: ScanRegion[] }>
    paragraphs: { id: string; text: string; regions: ScanRegion[] }[]
    matched: boolean; match_note: string
  } | null
}

export interface FollowupTask {
  id: string; title: string; reason: string; role_id: string; role_label: string
  status: 'waiting_for_result' | 'awaiting_review' | 'completed'
  created_at: string; reviewer: string; citations: Citation[]
  completed_at: string | null; completed_by: string | null
}

export interface SourceEvent {
  id: string; at: string; title: string; kind: string
  status: 'queued' | 'running' | 'ready' | 'failed' | 'superseded'
  run_id: string | null; error: string | null
}
