<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { getDocuments, getHealth, streamChat } from '../lib/api'
import { renderMarkdown } from '../lib/markdown'
import type { ChatEvent, ChatMessage, HealthInfo, RouteMode } from '../lib/types'
import Icon from './Icon.vue'
import RouteBadge from './RouteBadge.vue'
import SourceCard from './SourceCard.vue'

const messages = ref<ChatMessage[]>([])
const input = ref('')
const routeMode = ref<RouteMode>('auto')
const sending = ref(false)
const scrollEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)
const activeSource = ref<Record<string, number | null>>({})
const health = ref<HealthInfo | null>(null)
const docCount = ref(0)
const chunkCount = ref(0)
let abortController: AbortController | null = null

const suggestions = [
  { icon: 'shield', title: '开机前检查', text: '注塑机开机前需要检查什么？' },
  { icon: 'alert', title: '温度异常', text: '料筒温度异常（A-101）怎么排查？' },
  { icon: 'spark', title: '产品缺陷', text: '产品飞边怎么调整工艺？' },
  { icon: 'book', title: '安全应急', text: '注塑车间触电怎么应急处理？' },
]

const lastAssistant = computed(
  () => [...messages.value].reverse().find((m) => m.role === 'assistant') ?? null,
)

const modeHint = computed(() =>
  routeMode.value === 'auto'
    ? '本地优先；检索不命中或本地模型判断资料不足时，自动升级云端复核'
    : '只查厂内知识库；资料不足直接拒答，不调用云端',
)

const thresholdPct = computed(() => `${Math.round((health.value?.retrieval_min_sim ?? 0.6) * 100)}%`)
const scorePct = computed(() => {
  const score = lastAssistant.value?.maxScore
  return score == null ? '0%' : `${Math.round(Math.max(0, Math.min(1, score)) * 100)}%`
})

onMounted(async () => {
  try {
    health.value = await getHealth()
  } catch {
    health.value = null
  }
  try {
    const data = await getDocuments()
    docCount.value = data.count
    chunkCount.value = data.documents.reduce((sum, d) => sum + d.chunk_count, 0)
  } catch {
    docCount.value = 0
  }
})

onBeforeUnmount(() => abortController?.abort())

function blankMessage(role: 'user' | 'assistant', content = ''): ChatMessage {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    role,
    content,
    streaming: role === 'assistant',
    meta: null,
    sources: [],
    route: 'local',
    routeReason: '',
    model: '',
    refused: false,
    grounded: true,
    error: '',
    notice: '',
    maxScore: null,
    minSim: null,
    firstTokenMs: null,
    elapsedMs: null,
  }
}

async function scrollToBottom() {
  await nextTick()
  const el = scrollEl.value
  if (el) el.scrollTop = el.scrollHeight
}

/** 回答结束后把最后一轮问答对齐到视野顶部，避免引用卡片把答案顶出屏幕 */
async function focusLastExchange() {
  await nextTick()
  const el = scrollEl.value
  if (!el) return
  const list = el.querySelectorAll<HTMLElement>('.message.user')
  const last = list[list.length - 1]
  if (!last) return
  const offset = last.getBoundingClientRect().top - el.getBoundingClientRect().top + el.scrollTop
  el.scrollTo({ top: Math.max(0, offset - 12), behavior: 'smooth' })
}

function applyMeta(msg: ChatMessage, ev: Extract<ChatEvent, { type: 'meta' }>) {
  msg.meta = {
    route: ev.route,
    route_reason: ev.route_reason,
    model: ev.model,
    max_score: ev.max_score,
    min_sim: ev.min_sim,
    refused: ev.refused,
    grounded: ev.grounded,
    sources: ev.sources,
  }
  msg.route = ev.route
  msg.routeReason = ev.route_reason
  msg.model = ev.model
  msg.maxScore = ev.max_score
  msg.minSim = ev.min_sim
  msg.refused = ev.refused
  msg.grounded = ev.grounded
  msg.sources = ev.sources
}

async function send(text?: string) {
  const query = (text ?? input.value).trim()
  if (!query || sending.value) return

  input.value = ''
  if (inputEl.value) inputEl.value.style.height = 'auto'
  messages.value.push(blankMessage('user', query))
  const assistant = reactive(blankMessage('assistant'))
  messages.value.push(assistant)

  sending.value = true
  abortController = new AbortController()
  const started = performance.now()
  let finished = false
  await scrollToBottom()

  try {
    await streamChat(
      { query, route_mode: routeMode.value },
      (ev) => {
        if (ev.type === 'meta') {
          applyMeta(assistant, ev)
        } else if (ev.type === 'route') {
          assistant.route = ev.route
          assistant.routeReason = ev.route_reason
          assistant.model = ev.model
          assistant.grounded = ev.grounded
          assistant.sources = ev.sources
        } else if (ev.type === 'delta') {
          if (assistant.firstTokenMs == null) {
            assistant.firstTokenMs = Math.round(performance.now() - started)
          }
          assistant.content += ev.content
        } else if (ev.type === 'done') {
          finished = true
          assistant.content = ev.answer
          assistant.route = ev.route
          assistant.routeReason = ev.route_reason
          assistant.model = ev.model
          assistant.refused = ev.refused
          assistant.grounded = ev.grounded
          assistant.sources = ev.sources
          assistant.streaming = false
          assistant.elapsedMs = Math.round(performance.now() - started)
        } else if (ev.type === 'error') {
          assistant.error = ev.message
          assistant.streaming = false
        }
        scrollToBottom()
      },
      abortController.signal,
    )
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      assistant.notice = '已停止生成，以上内容可能不完整。'
    } else {
      assistant.error = err instanceof Error ? err.message : '请求失败，请稍后重试'
    }
  } finally {
    if (!finished) assistant.elapsedMs = Math.round(performance.now() - started)
    assistant.streaming = false
    sending.value = false
    abortController = null
    if (finished) {
      focusLastExchange()
    } else {
      scrollToBottom()
    }
  }
}

function stop() {
  abortController?.abort()
}

function clearConversation() {
  if (sending.value) stop()
  messages.value = []
  activeSource.value = {}
}

function selectSource(messageId: string, index: number) {
  activeSource.value[messageId] = activeSource.value[messageId] === index ? null : index
}

function onProseClick(event: MouseEvent, msg: ChatMessage) {
  const target = (event.target as HTMLElement).closest('[data-cite]') as HTMLElement | null
  if (!target) return
  const index = Number(target.dataset.cite)
  if (!Number.isFinite(index)) return
  activeSource.value[msg.id] = index
  nextTick(() => {
    document.getElementById(`src-${msg.id}-${index}`)?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
    })
  })
}

function handleInput(event: Event) {
  const el = event.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 168)}px`
}

function useSuggestion(text: string) {
  input.value = text
  send()
}
</script>

<template>
  <div class="chat-layout">
    <section class="chat-panel panel">
      <header class="chat-head">
        <div>
          <div class="eyebrow">KNOWLEDGE Q&amp;A</div>
          <h1>设备知识问答</h1>
        </div>
        <div class="chat-head-right">
          <span v-if="health" class="tag">
            <Icon name="database" :size="13" />
            {{ docCount }} 份 · {{ chunkCount }} 切片
          </span>
          <button class="btn btn-ghost btn-sm" type="button" :disabled="!messages.length" @click="clearConversation">
            <Icon name="trash" :size="14" />
            清空
          </button>
        </div>
      </header>

      <div ref="scrollEl" class="messages">
        <div v-if="!messages.length" class="welcome fade-up">
          <div class="welcome-kicker">
            <span class="pulse-dot" />
            LOCAL-FIRST · TRACEABLE ANSWERS
          </div>
          <h2>问设备，问工艺，问安全</h2>
          <p class="welcome-sub">
            答案只来自厂内 {{ docCount || 15 }} 份设备手册与故障案例，句末
            <span class="mono cite-demo">[1]</span> 可点开原文。知识库没有答案时，系统会明确拒答。
          </p>

          <div class="suggest-grid">
            <button
              v-for="item in suggestions"
              :key="item.text"
              class="suggest-card"
              type="button"
              @click="useSuggestion(item.text)"
            >
              <span class="suggest-icon"><Icon :name="item.icon" :size="19" /></span>
              <span class="suggest-body">
                <span class="suggest-title">{{ item.title }}</span>
                <span class="suggest-text">{{ item.text }}</span>
              </span>
              <Icon name="chevron-right" :size="16" class="suggest-arrow" />
            </button>
          </div>

          <div class="welcome-foot">
            <span><Icon name="cpu" :size="14" /> 本地 Qwen2.5-7B</span>
            <span><Icon name="layers" :size="14" /> bge-m3 向量检索</span>
            <span><Icon name="shield" :size="14" /> 数据不出厂</span>
          </div>
        </div>

        <article
          v-for="msg in messages"
          :key="msg.id"
          class="message"
          :class="msg.role"
        >
          <div v-if="msg.role === 'assistant'" class="avatar">智</div>
          <div class="message-main">
            <div class="message-top">
              <template v-if="msg.role === 'user'">
                <span class="speaker">你</span>
              </template>
              <template v-else>
                <RouteBadge :route="msg.route" :refused="msg.refused" />
                <span v-if="msg.model" class="model-name mono">{{ msg.model }}</span>
                <span v-if="msg.maxScore != null" class="score-chip mono">
                  检索 {{ msg.maxScore.toFixed(2) }}
                </span>
                <span v-if="msg.elapsedMs" class="time-chip mono">
                  {{ (msg.elapsedMs / 1000).toFixed(1) }}s
                </span>
              </template>
            </div>

            <div v-if="msg.role === 'user'" class="bubble user-bubble">{{ msg.content }}</div>

            <div v-else class="bubble assistant-bubble">
              <div v-if="msg.error" class="msg-error">
                <Icon name="alert" :size="16" />
                <span>{{ msg.error }}</span>
              </div>

              <div v-else-if="msg.refused" class="refusal-card">
                <div class="refusal-head">
                  <span class="refusal-icon"><Icon name="shield" :size="20" /></span>
                  <div>
                    <strong>{{ msg.content }}</strong>
                    <p v-if="msg.route === 'cloud'">
                      云端模型同样判断该问题超出注塑车间知识范围。
                    </p>
                    <p v-else>
                      请换一种问法，或切换到「智能协同」让云端补充通用建议。
                    </p>
                  </div>
                </div>
                <div class="refusal-note">系统不会在缺少依据时编造答案。</div>
              </div>

              <div
                v-else
                class="prose"
                @click="onProseClick($event, msg)"
                v-html="renderMarkdown(msg.content)"
              />

              <div v-if="msg.streaming" class="thinking-line">
                <span class="spinner" />
                <span>
                  {{ msg.content ? '生成中…' : msg.meta ? '模型生成中…' : '正在检索知识库…' }}
                </span>
                <i class="typing-cursor" />
              </div>

              <div v-if="msg.notice" class="notice-line">{{ msg.notice }}</div>

              <div v-if="msg.routeReason" class="route-line">
                <Icon name="route" :size="14" />
                <span>{{ msg.routeReason }}</span>
                <span v-if="msg.firstTokenMs != null" class="latency mono">
                  首字 {{ (msg.firstTokenMs / 1000).toFixed(2) }}s
                </span>
              </div>

              <div v-if="msg.sources.length" class="sources-block">
                <div class="sources-head">
                  <span class="eyebrow">CITATIONS</span>
                  <span class="sources-count">{{ msg.sources.length }} 条依据</span>
                </div>
                <SourceCard
                  v-for="source in msg.sources"
                  :id="`src-${msg.id}-${source.index}`"
                  :key="source.index"
                  :source="source"
                  :active="activeSource[msg.id] === source.index"
                  @select="selectSource(msg.id, $event)"
                />
                <p v-if="msg.route === 'cloud'" class="cloud-caveat">
                  云端回答未做逐句引用校验，以上片段仅供参考；涉及参数与安全操作请核对原文档。
                </p>
              </div>
            </div>
          </div>
        </article>
      </div>

      <footer class="composer">
        <div class="composer-top">
          <div class="mode-switch" role="group" aria-label="回答模式">
            <button
              type="button"
              :class="{ active: routeMode === 'auto' }"
              :disabled="sending"
              @click="routeMode = 'auto'"
            >
              <Icon name="spark" :size="14" />
              智能协同
            </button>
            <button
              type="button"
              :class="{ active: routeMode === 'kb_only' }"
              :disabled="sending"
              @click="routeMode = 'kb_only'"
            >
              <Icon name="book" :size="14" />
              仅知识库
            </button>
          </div>
          <span class="mode-hint">{{ modeHint }}</span>
        </div>

        <div class="input-row">
          <textarea
            ref="inputEl"
            v-model="input"
            class="textarea chat-input"
            rows="1"
            placeholder="描述设备现象或直接提问，例如：料筒温度异常 A-101 怎么排查？"
            :disabled="sending"
            @input="handleInput"
            @keydown.enter.exact.prevent="send()"
          />
          <button v-if="sending" class="btn btn-danger send-btn" type="button" @click="stop">
            <Icon name="stop" :size="16" />
            停止
          </button>
          <button
            v-else
            class="btn btn-primary send-btn"
            type="button"
            :disabled="!input.trim()"
            @click="send()"
          >
            <Icon name="send" :size="16" />
            发送
          </button>
        </div>
        <div class="composer-foot">
          <span>Enter 发送 · Shift + Enter 换行</span>
          <span class="mono">RETRIEVAL MIN SIM · {{ health?.retrieval_min_sim?.toFixed(2) ?? '0.60' }}</span>
        </div>
      </footer>
    </section>

    <aside class="rail">
      <div class="panel rail-panel">
        <div class="rail-head">
          <div>
            <div class="eyebrow">PIPELINE</div>
            <h3>链路监视</h3>
          </div>
          <span class="rail-live" :class="{ on: sending }">
            <i />{{ sending ? 'RUNNING' : 'IDLE' }}
          </span>
        </div>

        <div v-if="lastAssistant" class="monitor">
          <div class="monitor-step">
            <span class="step-no mono">01</span>
            <div class="step-body">
              <div class="step-title">向量检索</div>
              <div class="score-track">
                <i class="score-fill" :style="{ width: scorePct }" />
                <b class="score-threshold" :style="{ left: thresholdPct }" />
              </div>
              <div class="step-meta mono">
                top1 {{ lastAssistant.maxScore?.toFixed(3) ?? '—' }}
                <span>阈值 {{ (lastAssistant.minSim ?? health?.retrieval_min_sim ?? 0.6).toFixed(2) }}</span>
              </div>
            </div>
          </div>

          <div class="monitor-step">
            <span class="step-no mono">02</span>
            <div class="step-body">
              <div class="step-title">路由决策</div>
              <RouteBadge :route="lastAssistant.route" compact />
              <p class="step-reason">{{ lastAssistant.routeReason || '等待检索结果' }}</p>
            </div>
          </div>

          <div class="monitor-step">
            <span class="step-no mono">03</span>
            <div class="step-body">
              <div class="step-title">生成</div>
              <div class="metric-row">
                <span>首字</span>
                <b class="mono">
                  {{ lastAssistant.firstTokenMs != null ? (lastAssistant.firstTokenMs / 1000).toFixed(2) + 's' : '—' }}
                </b>
              </div>
              <div class="metric-row">
                <span>总耗时</span>
                <b class="mono">
                  {{ lastAssistant.elapsedMs != null ? (lastAssistant.elapsedMs / 1000).toFixed(1) + 's' : '—' }}
                </b>
              </div>
            </div>
          </div>

          <div class="monitor-step">
            <span class="step-no mono">04</span>
            <div class="step-body">
              <div class="step-title">引用</div>
              <div class="metric-row">
                <span>来源条目</span>
                <b class="mono">{{ lastAssistant.sources.length }}</b>
              </div>
              <div class="metric-row">
                <span>回答性质</span>
                <b>{{ lastAssistant.refused ? '无依据拒答' : lastAssistant.grounded ? '有据可查' : '通用建议' }}</b>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="rail-empty">
          <Icon name="activity" :size="26" />
          <p>提问后，这里会实时显示检索得分、路由原因和生成耗时。</p>
        </div>
      </div>

      <div class="panel rail-panel">
        <div class="eyebrow">RUNTIME</div>
        <h3>运行配置</h3>
        <dl class="runtime-list">
          <div>
            <dt>对话模型</dt>
            <dd class="mono">{{ health?.llm_model ?? 'qwen2.5:7b' }}</dd>
          </div>
          <div>
            <dt>向量模型</dt>
            <dd class="mono">{{ health?.embed_model ?? 'bge-m3' }}</dd>
          </div>
          <div>
            <dt>知识库</dt>
            <dd class="mono">{{ docCount }} 份 / {{ chunkCount }} 切片</dd>
          </div>
          <div>
            <dt>默认模式</dt>
            <dd class="mono">{{ health?.route_mode === 'kb_only' ? '仅知识库' : '智能协同' }}</dd>
          </div>
        </dl>
      </div>

      <div class="privacy-note">
        <Icon name="shield" :size="16" />
        <span>检索与本地生成均在厂内完成；仅低置信问题按配置升级云端。</span>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.chat-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 318px;
  gap: 18px;
  align-items: start;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 190px);
  overflow: hidden;
}

.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--border);
}

.chat-head h1 {
  margin-top: 3px;
  font-size: 22px;
  letter-spacing: 0.04em;
}

.chat-head-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.messages {
  flex: 1;
  min-height: 380px;
  max-height: calc(100vh - 360px);
  overflow-y: auto;
  padding: 24px 22px;
  scroll-behavior: smooth;
}

.welcome {
  max-width: 840px;
  margin: 10px auto 0;
  padding: 8px 4px 20px;
}

.welcome-kicker {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.2em;
}

.pulse-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 0 rgba(246, 178, 60, 0.45);
  animation: pulse 2.2s infinite;
}

.welcome h2 {
  margin-top: 14px;
  font-size: clamp(28px, 3.4vw, 40px);
  line-height: 1.25;
  letter-spacing: 0.04em;
}

.welcome-sub {
  max-width: 660px;
  margin-top: 12px;
  color: var(--text-2);
  font-size: 15px;
  line-height: 1.8;
}

.cite-demo {
  padding: 1px 4px;
  border-bottom: 1px dashed var(--accent);
  color: var(--accent-2);
  font-size: 11px;
}

.suggest-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 26px;
}

.suggest-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(17, 25, 33, 0.72);
  color: var(--text);
  text-align: left;
  transition: all 0.18s ease;
}

.suggest-card:hover {
  transform: translateY(-1px);
  border-color: rgba(246, 178, 60, 0.45);
  background: rgba(246, 178, 60, 0.06);
}

.suggest-icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 38px;
  height: 38px;
  border: 1px solid rgba(246, 178, 60, 0.28);
  border-radius: 9px;
  background: var(--accent-soft);
  color: var(--accent-2);
}

.suggest-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  flex: 1;
}

.suggest-title {
  color: var(--text);
  font-size: 14px;
  font-weight: 700;
}

.suggest-text {
  overflow: hidden;
  color: var(--muted);
  font-size: 12.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.suggest-arrow {
  flex: none;
  color: var(--muted);
  transition: transform 0.18s ease;
}

.suggest-card:hover .suggest-arrow {
  transform: translateX(3px);
  color: var(--accent);
}

.welcome-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
}

.welcome-foot span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.message {
  display: flex;
  gap: 11px;
  max-width: 900px;
  margin: 0 auto 22px;
  animation: fadeUp 0.24s ease both;
}

.message.user {
  justify-content: flex-end;
}

.avatar {
  display: grid;
  place-items: center;
  flex: none;
  width: 34px;
  height: 34px;
  margin-top: 2px;
  border: 1px solid rgba(246, 178, 60, 0.4);
  border-radius: 9px;
  background: var(--accent-soft);
  color: var(--accent-2);
  font-size: 15px;
  font-weight: 800;
}

.message-main {
  min-width: 0;
  max-width: 100%;
}

.message.user .message-main {
  max-width: 82%;
}

.message-top {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  margin-bottom: 6px;
  min-height: 22px;
}

.message.user .message-top {
  justify-content: flex-end;
}

.speaker {
  color: var(--muted);
  font-size: 12px;
}

.model-name {
  color: var(--muted);
  font-size: 10.5px;
}

.score-chip,
.time-chip {
  padding: 2px 7px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  font-size: 10.5px;
}

.time-chip {
  color: var(--text-2);
}

.bubble {
  border-radius: 12px;
}

.user-bubble {
  padding: 12px 16px;
  border: 1px solid rgba(246, 178, 60, 0.3);
  border-top-right-radius: 4px;
  background: linear-gradient(180deg, rgba(246, 178, 60, 0.14), rgba(246, 178, 60, 0.08));
  color: #f6e6c8;
  font-size: 15px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.assistant-bubble {
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-top-left-radius: 4px;
  background: rgba(17, 25, 33, 0.82);
}

.msg-error {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid rgba(239, 91, 91, 0.35);
  border-radius: 9px;
  background: var(--danger-soft);
  color: #ffb0b0;
  font-size: 13.5px;
}

.refusal-card {
  padding: 2px;
}

.refusal-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.refusal-icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 40px;
  height: 40px;
  border: 1px solid rgba(245, 166, 35, 0.35);
  border-radius: 10px;
  background: var(--warn-soft);
  color: var(--warn);
}

.refusal-head strong {
  display: block;
  color: var(--text);
  font-size: 17px;
  line-height: 1.5;
}

.refusal-head p {
  margin-top: 5px;
  color: var(--text-2);
  font-size: 13.5px;
  line-height: 1.7;
}

.refusal-note {
  margin-top: 14px;
  padding: 9px 12px;
  border-left: 2px solid var(--warn);
  border-radius: 0 6px 6px 0;
  background: rgba(245, 166, 35, 0.06);
  color: var(--muted);
  font-size: 12.5px;
}

.thinking-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  color: var(--muted);
  font-size: 12.5px;
}

.typing-cursor {
  display: inline-block;
  width: 7px;
  height: 15px;
  background: var(--accent);
  animation: blink 1s step-end infinite;
}

.notice-line {
  margin-top: 12px;
  color: var(--warn);
  font-size: 12.5px;
}

.route-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
  padding-top: 11px;
  border-top: 1px dashed var(--border);
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.6;
}

.route-line .latency {
  margin-left: auto;
  color: var(--text-2);
}

.sources-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}

.sources-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 2px;
}

.sources-count {
  color: var(--muted);
  font-size: 11.5px;
}

.cloud-caveat {
  margin-top: 4px;
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.65;
}

.composer {
  padding: 14px 22px 16px;
  border-top: 1px solid var(--border);
  background: rgba(10, 15, 21, 0.55);
}

.composer-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.mode-switch {
  display: inline-flex;
  gap: 3px;
  padding: 3px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--bg-2);
}

.mode-switch button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
}

.mode-switch button.active {
  border-color: rgba(246, 178, 60, 0.32);
  background: var(--accent-soft);
  color: var(--accent-2);
}

.mode-switch button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.mode-hint {
  overflow: hidden;
  color: var(--muted);
  font-size: 11.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.chat-input {
  min-height: 46px;
  max-height: 168px;
  padding: 12px 15px;
  border-color: var(--border-strong);
  font-size: 15px;
}

.send-btn {
  height: 46px;
  padding: 0 18px;
}

.composer-foot {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 7px;
  color: #61778a;
  font-size: 10.5px;
}

.rail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: sticky;
  top: 94px;
}

.rail-panel {
  padding: 17px 17px 18px;
}

.rail-panel h3 {
  margin-top: 2px;
  font-size: 16px;
}

.rail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.rail-live {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.12em;
}

.rail-live i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--muted);
}

.rail-live.on {
  color: var(--ok);
}

.rail-live.on i {
  background: var(--ok);
  animation: pulse 1.4s infinite;
}

.monitor {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 17px;
}

.monitor-step {
  display: flex;
  gap: 10px;
}

.step-no {
  flex: none;
  width: 24px;
  padding-top: 1px;
  color: var(--accent);
  font-size: 10px;
  letter-spacing: 0.06em;
}

.step-body {
  flex: 1;
  min-width: 0;
}

.step-title {
  margin-bottom: 5px;
  color: var(--text);
  font-size: 12.5px;
  font-weight: 600;
}

.score-track {
  position: relative;
  height: 7px;
  margin: 7px 0 5px;
  border-radius: 99px;
  background: var(--panel-3);
}

.score-fill {
  display: block;
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
  transition: width 0.4s ease;
}

.score-threshold {
  position: absolute;
  top: -3px;
  width: 2px;
  height: 13px;
  border-radius: 2px;
  background: var(--danger);
  box-shadow: 0 0 0 2px rgba(239, 91, 91, 0.15);
}

.step-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--muted);
  font-size: 10.5px;
}

.step-reason {
  margin-top: 6px;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
}

.metric-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-top: 4px;
  color: var(--muted);
  font-size: 11px;
}

.metric-row b {
  color: var(--text-2);
  font-size: 11.5px;
  font-weight: 600;
}

.rail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 30px 12px 20px;
  color: var(--muted);
  text-align: center;
}

.rail-empty p {
  max-width: 210px;
  font-size: 12px;
  line-height: 1.7;
}

.runtime-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin-top: 14px;
}

.runtime-list > div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.runtime-list dt {
  flex: none;
  color: var(--muted);
  font-size: 11.5px;
}

.runtime-list dd {
  margin: 0;
  overflow: hidden;
  color: var(--text-2);
  font-size: 11px;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.privacy-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 14px;
  border: 1px dashed var(--border);
  border-radius: 10px;
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.65;
}

.privacy-note :deep(.icon) {
  margin-top: 1px;
  color: var(--ok);
}

@media (max-width: 1120px) {
  .chat-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .rail {
    display: none;
  }
}

@media (max-width: 720px) {
  .chat-head {
    padding: 14px 16px;
  }

  .messages {
    max-height: none;
    padding: 18px 14px;
  }

  .chat-panel {
    min-height: calc(100vh - 220px);
  }

  .suggest-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .welcome h2 {
    font-size: 28px;
  }

  .composer {
    padding: 12px 14px 14px;
  }

  .composer-top {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }

  .mode-hint {
    white-space: normal;
  }

  .message.user .message-main {
    max-width: 92%;
  }

  .composer-foot span:last-child {
    display: none;
  }
}
</style>
