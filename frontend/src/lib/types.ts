// 前后端共享数据结构（与 backend/app/services 的返回字段保持一致）

export type RouteMode = 'auto' | 'kb_only'
export type RouteKind = 'local' | 'cloud'

export interface HealthInfo {
  status: string
  service: string
  version: string
  ollama_base_url: string
  llm_model: string
  embed_model: string
  retrieval_min_sim: number
  route_mode: RouteMode
  cloud_configured: boolean
  frontend_built: boolean
}

export interface Source {
  index: number
  doc_id: string
  doc_title: string
  doc_no: string
  category: string
  heading_path: string
  score: number
  text: string
}

export interface ChatMeta {
  route: RouteKind
  route_reason: string
  model: string
  max_score: number
  min_sim: number
  refused: boolean
  grounded: boolean
  sources: Source[]
}

export interface ChatDone {
  type: 'done'
  route: RouteKind
  route_reason: string
  model: string
  answer: string
  refused: boolean
  grounded: boolean
  sources: Source[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming: boolean
  meta: ChatMeta | null
  sources: Source[]
  route: RouteKind
  routeReason: string
  model: string
  refused: boolean
  grounded: boolean
  error: string
  notice: string
  maxScore: number | null
  minSim: number | null
  firstTokenMs: number | null
  elapsedMs: number | null
}

export type ChatEvent =
  | ({ type: 'meta' } & ChatMeta)
  | { type: 'route'; route: RouteKind; route_reason: string; model: string; grounded: boolean; sources: Source[] }
  | { type: 'delta'; content: string }
  | ChatDone
  | { type: 'error'; message: string }

export interface DocRecord {
  doc_id: string
  title: string
  category: string
  version: string
  date: string
  doc_no: string
  file: string
  chunk_count: number
  content_sha256: string
  imported_at: string
}

export interface DocumentsResponse {
  count: number
  documents: DocRecord[]
}

export interface SearchResult {
  query: string
  hits: Source[]
  max_score: number
  min_sim: number
  has_relevant: boolean
}

export interface DiagTopic {
  id: string
  title: string
  device: string
  summary: string
  estimated_steps: string
}

export interface DiagBasis {
  doc_title: string
  doc_no: string
  heading: string
  quote: string
}

export interface DiagOption {
  id: string
  label: string
  tone: 'default' | 'safe' | 'warn' | 'danger'
}

export interface DiagNode {
  id: string
  step_no: number
  type: 'question' | 'info'
  title: string
  question: string
  hint: string
  body: string
  basis: DiagBasis[]
  options: DiagOption[]
}

export interface DiagConclusion {
  id: string
  title: string
  level: string
  summary: string
  actions: string[]
  safety: string
  basis: DiagBasis[]
}

export interface DiagProcessItem {
  step: number
  node_id: string
  title: string
  question: string
  answer: string
  basis: DiagBasis[]
}

export interface DiagReference {
  doc_title: string
  doc_no: string
  heading: string
  quote: string
}

export interface DiagReport {
  report_no: string
  created_at: string
  completed_at: string | null
  topic: { id: string; title: string; device: string }
  symptom: string
  process: DiagProcessItem[]
  conclusion: {
    title: string
    level: string
    summary: string
    actions: string[]
    safety: string
  }
  references: DiagReference[]
}

export interface DiagStart {
  session_id: string
  topic: { id: string; title: string; device: string }
  node: DiagNode
  step_no: number
  done: false
}

export interface DiagStep {
  session_id: string
  done: false
  step_no: number
  node: DiagNode
}

export interface DiagFinished {
  session_id: string
  done: true
  step_no: number
  conclusion: DiagConclusion
  report: DiagReport
}

export type DiagAnswer = DiagStep | DiagFinished

export interface DiagSession {
  session_id: string
  topic: { id: string; title: string; device: string }
  status: 'active' | 'done'
  step_no: number
  done: boolean
  node?: DiagNode
  conclusion?: DiagConclusion
  report?: DiagReport
  history: { step: number; title: string; question: string; answer: string }[]
}
