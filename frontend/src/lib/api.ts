// 后端 API 封装：统一错误处理 + SSE 解析
import type {
  ChatEvent,
  DiagAnswer,
  DiagSession,
  DiagStart,
  DiagTopic,
  DocumentsResponse,
  HealthInfo,
  RouteMode,
  SearchResult,
} from './types'

const BASE = ''

async function errorText(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data?.detail === 'string') return data.detail
    if (Array.isArray(data?.detail)) return data.detail.map((d: { msg?: string }) => d.msg).join('；')
    return JSON.stringify(data)
  } catch {
    return `${res.status} ${res.statusText}`
  }
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init)
  if (!res.ok) throw new Error(await errorText(res))
  return (await res.json()) as T
}

export function getHealth(): Promise<HealthInfo> {
  return jsonFetch<HealthInfo>('/health')
}

export function getDocuments(): Promise<DocumentsResponse> {
  return jsonFetch<DocumentsResponse>('/api/kb/documents')
}

export function importDocuments(rebuild = false): Promise<{ count: number; imported: unknown[]; errors: { file: string; error: string }[] }> {
  return jsonFetch(`/api/kb/import?rebuild=${rebuild ? 'true' : 'false'}`, { method: 'POST' })
}

export function reindexDocuments(): Promise<{ count: number; imported: unknown[]; errors: { file: string; error: string }[] }> {
  return jsonFetch('/api/kb/reindex', { method: 'POST' })
}

export function uploadDocument(file: File): Promise<unknown> {
  const form = new FormData()
  form.append('file', file)
  return jsonFetch('/api/kb/upload', { method: 'POST', body: form })
}

export function deleteDocument(docId: string): Promise<unknown> {
  return jsonFetch(`/api/kb/documents/${encodeURIComponent(docId)}`, { method: 'DELETE' })
}

export function searchKnowledge(query: string, topK = 4): Promise<SearchResult> {
  return jsonFetch<SearchResult>('/api/kb/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK }),
  })
}

export async function streamChat(
  payload: { query: string; route_mode: RouteMode; top_k?: number },
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(BASE + '/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!res.ok) throw new Error(await errorText(res))
  if (!res.body) throw new Error('浏览器不支持流式响应')

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  const consume = (chunk: string) => {
    for (const block of chunk.split('\n\n')) {
      const line = block
        .split('\n')
        .map((l) => l.trimEnd())
        .find((l) => l.startsWith('data:'))
      if (!line) continue
      const raw = line.slice(5).trim()
      if (!raw) continue
      try {
        onEvent(JSON.parse(raw) as ChatEvent)
      } catch {
        // 单个事件解析失败不打断整条流
      }
    }
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    consume(parts.join('\n\n'))
  }
  buffer += decoder.decode()
  if (buffer.trim()) consume(buffer)
}

export function getDiagTopics(): Promise<{ topics: DiagTopic[] }> {
  return jsonFetch('/api/diag/topics')
}

export function startDiagnosis(topicId: string): Promise<DiagStart> {
  return jsonFetch('/api/diag/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic_id: topicId }),
  })
}

export function answerDiagnosis(sessionId: string, nodeId: string, optionId: string): Promise<DiagAnswer> {
  return jsonFetch(`/api/diag/sessions/${encodeURIComponent(sessionId)}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_id: nodeId, option_id: optionId }),
  })
}

export function backDiagnosis(sessionId: string): Promise<DiagAnswer> {
  return jsonFetch(`/api/diag/sessions/${encodeURIComponent(sessionId)}/back`, { method: 'POST' })
}

export function getDiagnosisSession(sessionId: string): Promise<DiagSession> {
  return jsonFetch(`/api/diag/sessions/${encodeURIComponent(sessionId)}`)
}

export function reportMarkdownUrl(sessionId: string): string {
  return `/api/diag/sessions/${encodeURIComponent(sessionId)}/report.md`
}
