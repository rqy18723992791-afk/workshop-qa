<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  answerDiagnosis,
  backDiagnosis,
  getDiagTopics,
  reportMarkdownUrl,
  startDiagnosis,
} from '../lib/api'
import type {
  DiagConclusion,
  DiagNode,
  DiagReport,
  DiagTopic,
} from '../lib/types'
import Icon from './Icon.vue'

interface HistoryItem {
  step: number
  title: string
  question: string
  answer: string
}

const topics = ref<DiagTopic[]>([])
const topicsLoading = ref(true)
const topicsError = ref('')

const sessionId = ref('')
const topicTitle = ref('')
const device = ref('')
const node = ref<DiagNode | null>(null)
const history = ref<HistoryItem[]>([])
const conclusion = ref<DiagConclusion | null>(null)
const report = ref<DiagReport | null>(null)
const starting = ref(false)
const submitting = ref(false)
const error = ref('')

const done = computed(() => Boolean(conclusion.value && report.value))
const progress = computed(() => Math.min(100, Math.round((history.value.length / 6) * 100)))
const levelClass = computed(() => {
  const level = conclusion.value?.level ?? ''
  if (level.includes('立即') || level.includes('安全')) return 'danger'
  if (level.includes('停机') || level.includes('计划')) return 'warn'
  return 'info'
})

async function loadTopics() {
  topicsLoading.value = true
  topicsError.value = ''
  try {
    const data = await getDiagTopics()
    topics.value = data.topics
  } catch (err) {
    topicsError.value = err instanceof Error ? err.message : '加载故障主题失败'
  } finally {
    topicsLoading.value = false
  }
}

async function start(topicId: string) {
  if (starting.value) return
  starting.value = true
  error.value = ''
  try {
    const data = await startDiagnosis(topicId)
    sessionId.value = data.session_id
    topicTitle.value = data.topic.title
    device.value = data.topic.device
    node.value = data.node
    history.value = []
    conclusion.value = null
    report.value = null
  } catch (err) {
    error.value = err instanceof Error ? err.message : '开始诊断失败'
  } finally {
    starting.value = false
  }
}

async function choose(optionId: string, label: string) {
  const current = node.value
  if (!current || !sessionId.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    const res = await answerDiagnosis(sessionId.value, current.id, optionId)
    history.value.push({
      step: current.step_no,
      title: current.title,
      question: current.question,
      answer: label,
    })
    if (res.done) {
      conclusion.value = res.conclusion
      report.value = res.report
      node.value = null
    } else {
      node.value = res.node
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '提交失败，请重试'
  } finally {
    submitting.value = false
  }
}

async function back() {
  if (!sessionId.value || submitting.value || !history.value.length) return
  submitting.value = true
  error.value = ''
  try {
    const res = await backDiagnosis(sessionId.value)
    history.value.pop()
    conclusion.value = null
    report.value = null
    if (!res.done) node.value = res.node
  } catch (err) {
    error.value = err instanceof Error ? err.message : '回退失败'
  } finally {
    submitting.value = false
  }
}

function restart() {
  sessionId.value = ''
  topicTitle.value = ''
  device.value = ''
  node.value = null
  history.value = []
  conclusion.value = null
  report.value = null
  error.value = ''
}

function printReport() {
  window.print()
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

onMounted(loadTopics)
</script>

<template>
  <div class="diag-view">
    <!-- 主题选择 -->
    <template v-if="!sessionId">
      <header class="diag-hero">
        <div class="hazard-line" />
        <div class="eyebrow">GUIDED DIAGNOSIS · STATEFUL WORKFLOW</div>
        <h1>故障排查向导</h1>
        <p class="hero-sub">
          从现场症状出发，按设备手册逐步判断。每一步都给出原文依据，支持回退；
          走完整条链后自动生成可打印的「设备故障处置单」。
        </p>
        <div class="hero-tags">
          <span class="tag"><Icon name="wrench" :size="13" /> 状态机流程</span>
          <span class="tag"><Icon name="book" :size="13" /> 每步引用手册</span>
          <span class="tag"><Icon name="print" :size="13" /> 处置单可打印</span>
        </div>
      </header>

      <div v-if="topicsLoading" class="empty">
        <span class="spinner" />
        <span>正在加载诊断主题…</span>
      </div>

      <div v-else-if="topicsError" class="panel panel-pad empty">
        <Icon name="alert" :size="26" />
        <p>{{ topicsError }}</p>
        <button class="btn btn-sm" type="button" @click="loadTopics">重试</button>
      </div>

      <div v-else class="topic-grid">
        <button
          v-for="item in topics"
          :key="item.id"
          class="topic-card panel"
          type="button"
          :disabled="starting"
          @click="start(item.id)"
        >
          <div class="topic-top">
            <span class="topic-icon"><Icon name="activity" :size="24" /></span>
            <span class="tag accent">可用</span>
          </div>
          <h2>{{ item.title }}</h2>
          <p>{{ item.summary }}</p>
          <div class="topic-meta">
            <span><Icon name="cpu" :size="13" /> {{ item.device }}</span>
            <span><Icon name="route" :size="13" /> 预计 {{ item.estimated_steps }}</span>
          </div>
          <span class="topic-cta">
            <span>{{ starting ? '正在创建会话…' : '开始诊断' }}</span>
            <Icon name="chevron-right" :size="17" />
          </span>
        </button>

        <div class="topic-card panel planned">
          <div class="topic-top">
            <span class="topic-icon muted-icon"><Icon name="plus" :size="22" /></span>
            <span class="tag">规划中</span>
          </div>
          <h2>更多故障主题</h2>
          <p>顶出故障、液压异常、模具保护报警的完整诊断链将在后续版本接入同一状态机。</p>
          <div class="topic-meta">
            <span><Icon name="layers" :size="13" /> 同一引擎</span>
            <span><Icon name="clock" :size="13" /> 持续补充</span>
          </div>
        </div>
      </div>

      <div class="diag-principles">
        <div>
          <span class="principle-no mono">01</span>
          <strong>先安全，后排查</strong>
          <p>未断电挂牌、未冷却到 50 ℃ 以下时，流程会直接中止并给出安全处置。</p>
        </div>
        <div>
          <span class="principle-no mono">02</span>
          <strong>每一步都有依据</strong>
          <p>问题与选项来自故障案例卡，底部同步展示文档编号、章节和原文。</p>
        </div>
        <div>
          <span class="principle-no mono">03</span>
          <strong>结论可追溯</strong>
          <p>处置单记录完整问答过程、结论、建议和全部引用，可打印或导出 Markdown。</p>
        </div>
      </div>
    </template>

    <!-- 诊断进行中 -->
    <template v-else-if="!done && node">
      <div class="diag-work">
        <aside class="steps-panel panel">
          <div class="steps-head">
            <div class="eyebrow">SESSION</div>
            <h2>{{ topicTitle }}</h2>
            <p>{{ device }}</p>
          </div>

          <div class="progress-block">
            <div class="progress-top">
              <span>排查进度</span>
              <span class="mono">第 {{ node.step_no }} 步</span>
            </div>
            <div class="progress-track"><i :style="{ width: progress + '%' }" /></div>
          </div>

          <ol class="steps-list">
            <li v-for="item in history" :key="item.step" class="step done">
              <span class="step-dot"><Icon name="check" :size="12" /></span>
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.answer }}</p>
              </div>
            </li>
            <li class="step current">
              <span class="step-dot"><span class="pulse-dot" /></span>
              <div>
                <strong>{{ node.title }}</strong>
                <p>进行中</p>
              </div>
            </li>
          </ol>

          <div class="steps-foot">
            <button class="btn btn-ghost btn-sm" type="button" :disabled="!history.length || submitting" @click="back">
              <Icon name="arrow-left" :size="14" />
              回退上一步
            </button>
            <button class="btn btn-ghost btn-sm" type="button" :disabled="submitting" @click="restart">
              重新开始
            </button>
          </div>
        </aside>

        <section class="question-panel panel">
          <div class="safety-strip">
            <Icon name="shield" :size="15" />
            <span>涉及电气、高温或模具区域检查时，必须停机断电挂牌，由持证人员操作。</span>
          </div>

          <div class="question-inner">
            <div class="question-top">
              <span class="step-badge mono">STEP {{ String(node.step_no).padStart(2, '0') }}</span>
              <span class="tag">{{ node.type === 'info' ? '操作指引' : '诊断问题' }}</span>
            </div>

            <h2>{{ node.title }}</h2>
            <p class="question-text">{{ node.question }}</p>
            <p v-if="node.hint" class="question-hint">
              <Icon name="info" :size="14" />
              <span>{{ node.hint }}</span>
            </p>
            <pre v-if="node.body" class="info-body">{{ node.body }}</pre>

            <div class="options">
              <button
                v-for="option in node.options"
                :key="option.id"
                class="option-btn"
                :class="option.tone"
                type="button"
                :disabled="submitting"
                @click="choose(option.id, option.label)"
              >
                <span class="option-mark" />
                <span class="option-label">{{ option.label }}</span>
                <Icon name="chevron-right" :size="17" class="option-arrow" />
              </button>
            </div>

            <div v-if="error" class="inline-error">
              <Icon name="alert" :size="15" />
              <span>{{ error }}</span>
            </div>

            <div class="basis-panel">
              <div class="basis-head">
                <Icon name="book" :size="15" />
                <strong>手册依据</strong>
                <span class="mono">{{ node.basis[0]?.doc_no }}</span>
              </div>
              <blockquote v-for="(basis, i) in node.basis" :key="i">
                {{ basis.quote }}
                <footer>《{{ basis.doc_title }}》 · {{ basis.heading }}</footer>
              </blockquote>
            </div>
          </div>
        </section>
      </div>
    </template>

    <!-- 处置单 -->
    <template v-else-if="done && report && conclusion">
      <div class="report-actions no-print">
        <div class="row">
          <button class="btn btn-ghost" type="button" :disabled="submitting" @click="back">
            <Icon name="arrow-left" :size="15" />
            返回上一步修改
          </button>
          <button class="btn btn-ghost" type="button" @click="restart">
            <Icon name="refresh" :size="15" />
            重新诊断
          </button>
        </div>
        <div class="row">
          <a class="btn btn-ghost" :href="reportMarkdownUrl(sessionId)" download>
            <Icon name="download" :size="15" />
            导出 Markdown
          </a>
          <button class="btn btn-primary" type="button" @click="printReport">
            <Icon name="print" :size="15" />
            打印处置单
          </button>
        </div>
      </div>

      <article class="print-sheet panel">
        <header class="sheet-head">
          <div class="sheet-brand">
            <span class="sheet-logo">智</span>
            <div>
              <strong>车间智答</strong>
              <span>设备故障处置单 · FAULT DISPOSITION SHEET</span>
            </div>
          </div>
          <div class="sheet-no">
            <span>处置单编号</span>
            <strong class="mono">{{ report.report_no }}</strong>
          </div>
        </header>

        <div class="sheet-title">
          <span class="level-badge" :class="levelClass">{{ conclusion.level }}</span>
          <h1>{{ conclusion.title }}</h1>
          <p>{{ conclusion.summary }}</p>
        </div>

        <dl class="meta-grid">
          <div>
            <dt>设备</dt>
            <dd>{{ report.topic.device }}</dd>
          </div>
          <div>
            <dt>故障主题</dt>
            <dd>{{ report.topic.title }}</dd>
          </div>
          <div>
            <dt>故障现象</dt>
            <dd>{{ report.symptom }}</dd>
          </div>
          <div>
            <dt>生成时间</dt>
            <dd class="mono">{{ formatTime(report.completed_at) }}</dd>
          </div>
        </dl>

        <section class="sheet-section">
          <h2><span class="mono">01</span> 排查过程</h2>
          <table class="process-table">
            <thead>
              <tr>
                <th class="col-step">步骤</th>
                <th>检查项</th>
                <th>结果</th>
                <th>手册依据</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in report.process" :key="item.step">
                <td class="mono">{{ item.step }}</td>
                <td>{{ item.title }}</td>
                <td>{{ item.answer }}</td>
                <td class="basis-cell">
                  <span v-for="b in item.basis" :key="b.doc_no + b.heading" class="basis-ref">
                    {{ b.doc_no }} · {{ b.heading }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="sheet-section">
          <h2><span class="mono">02</span> 诊断结论</h2>
          <p class="conclusion-text">{{ conclusion.summary }}</p>
        </section>

        <section class="sheet-section">
          <h2><span class="mono">03</span> 处置建议</h2>
          <ol class="action-list">
            <li v-for="(action, i) in conclusion.actions" :key="i">{{ action }}</li>
          </ol>
        </section>

        <section class="sheet-section">
          <h2><span class="mono">04</span> 安全提示</h2>
          <div class="safety-box">
            <Icon name="shield" :size="18" />
            <span>{{ conclusion.safety }}</span>
          </div>
        </section>

        <section class="sheet-section">
          <h2><span class="mono">05</span> 依据出处</h2>
          <ol class="ref-list">
            <li v-for="(ref, i) in report.references" :key="i">
              <strong>《{{ ref.doc_title }}》（{{ ref.doc_no }}）</strong>
              <span>{{ ref.heading }}</span>
              <p>{{ ref.quote }}</p>
            </li>
          </ol>
        </section>

        <footer class="sheet-sign">
          <div>处置人：<span class="sign-line" /></div>
          <div>审核人：<span class="sign-line" /></div>
          <div>日期：<span class="sign-line short" /></div>
        </footer>

        <div class="sheet-foot">
          本处置单由「车间智答」故障排查向导依据厂内知识库生成，处置前请由设备主管复核。
        </div>
      </article>
    </template>

    <div v-if="error && !node && !done" class="panel panel-pad empty">
      <Icon name="alert" :size="26" />
      <p>{{ error }}</p>
      <button class="btn btn-sm" type="button" @click="restart">返回</button>
    </div>
  </div>
</template>

<style scoped>
.diag-view {
  max-width: 1280px;
  margin: 0 auto;
}

.diag-hero {
  position: relative;
  padding: 26px 4px 8px;
}

.hazard-line {
  width: 96px;
  height: 5px;
  margin-bottom: 18px;
  border-radius: 2px;
  background: repeating-linear-gradient(
    -45deg,
    var(--accent) 0 10px,
    #1a1a1a 10px 20px
  );
  opacity: 0.9;
}

.diag-hero h1 {
  margin-top: 8px;
  font-size: clamp(30px, 4vw, 44px);
  letter-spacing: 0.05em;
}

.hero-sub {
  max-width: 820px;
  margin-top: 12px;
  color: var(--text-2);
  font-size: 15.5px;
  line-height: 1.85;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}

.topic-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 26px;
}

.topic-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 24px;
  color: var(--text);
  text-align: left;
  transition: all 0.2s ease;
}

button.topic-card:hover {
  transform: translateY(-2px);
  border-color: rgba(246, 178, 60, 0.5);
  box-shadow: 0 20px 55px rgba(0, 0, 0, 0.4);
}

.topic-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  width: 100%;
}

.topic-icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border: 1px solid rgba(246, 178, 60, 0.35);
  border-radius: 12px;
  background: var(--accent-soft);
  color: var(--accent-2);
}

.muted-icon {
  border-color: var(--border);
  background: var(--panel-2);
  color: var(--muted);
}

.topic-card h2 {
  margin-top: 16px;
  font-size: 21px;
  line-height: 1.4;
}

.topic-card p {
  margin-top: 9px;
  color: var(--text-2);
  font-size: 13.5px;
  line-height: 1.75;
}

.topic-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 16px;
  color: var(--muted);
  font-size: 11.5px;
}

.topic-meta span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.topic-cta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 20px;
  padding-top: 14px;
  border-top: 1px dashed var(--border);
  width: 100%;
  color: var(--accent-2);
  font-size: 13px;
  font-weight: 600;
}

.topic-cta :deep(.icon) {
  margin-left: auto;
  transition: transform 0.18s ease;
}

button.topic-card:hover .topic-cta :deep(.icon) {
  transform: translateX(4px);
}

.planned {
  opacity: 0.72;
}

.diag-principles {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin-top: 30px;
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  background: var(--border);
}

.diag-principles > div {
  padding: 20px;
  background: var(--panel);
}

.principle-no {
  color: var(--accent);
  font-size: 11px;
  letter-spacing: 0.1em;
}

.diag-principles strong {
  display: block;
  margin-top: 8px;
  font-size: 14px;
}

.diag-principles p {
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.7;
}

/* ===== 进行中 ===== */

.diag-work {
  display: grid;
  grid-template-columns: 310px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.steps-panel {
  position: sticky;
  top: 94px;
  padding: 20px;
}

.steps-head h2 {
  margin-top: 5px;
  font-size: 18px;
  line-height: 1.45;
}

.steps-head p {
  margin-top: 4px;
  color: var(--muted);
  font-size: 11.5px;
}

.progress-block {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.progress-top {
  display: flex;
  justify-content: space-between;
  color: var(--muted);
  font-size: 11.5px;
}

.progress-track {
  height: 5px;
  margin-top: 7px;
  border-radius: 99px;
  background: var(--panel-3);
  overflow: hidden;
}

.progress-track i {
  display: block;
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
  transition: width 0.3s ease;
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-top: 18px;
  list-style: none;
}

.step {
  position: relative;
  display: flex;
  gap: 11px;
  padding-bottom: 16px;
}

.step:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 11px;
  top: 24px;
  bottom: 0;
  width: 1px;
  background: var(--border);
}

.step-dot {
  display: grid;
  place-items: center;
  flex: none;
  width: 23px;
  height: 23px;
  border: 1px solid var(--border-strong);
  border-radius: 50%;
  background: var(--panel-2);
  color: var(--muted);
}

.step.done .step-dot {
  border-color: rgba(54, 211, 153, 0.45);
  background: var(--ok-soft);
  color: var(--ok);
}

.step.current .step-dot {
  border-color: rgba(246, 178, 60, 0.55);
  background: var(--accent-soft);
}

.step strong {
  display: block;
  color: var(--text-2);
  font-size: 12.5px;
  font-weight: 600;
}

.step.current strong {
  color: var(--accent-2);
}

.step p {
  margin-top: 2px;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.55;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1.5s infinite;
}

.steps-foot {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 8px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.question-panel {
  overflow: hidden;
}

.safety-strip {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 11px 20px;
  border-bottom: 1px solid rgba(245, 166, 35, 0.25);
  background: var(--warn-soft);
  color: #ffd08a;
  font-size: 12px;
  line-height: 1.6;
}

.safety-strip :deep(.icon) {
  margin-top: 1px;
}

.question-inner {
  padding: 26px 28px 28px;
}

.question-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.step-badge {
  color: var(--accent);
  font-size: 11px;
  letter-spacing: 0.14em;
}

.question-inner h2 {
  margin-top: 14px;
  font-size: 26px;
  line-height: 1.4;
  letter-spacing: 0.02em;
}

.question-text {
  margin-top: 10px;
  color: var(--text);
  font-size: 18px;
  line-height: 1.8;
}

.question-hint {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin-top: 10px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
}

.question-hint :deep(.icon) {
  margin-top: 3px;
  flex: none;
}

.info-body {
  margin-top: 14px;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-2);
  color: var(--text-2);
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.9;
  white-space: pre-wrap;
}

.options {
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin-top: 22px;
}

.option-btn {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 15px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--panel-2);
  color: var(--text);
  text-align: left;
  transition: all 0.16s ease;
}

.option-btn:hover:not(:disabled) {
  transform: translateX(3px);
  border-color: rgba(246, 178, 60, 0.5);
  background: rgba(246, 178, 60, 0.07);
}

.option-btn:disabled {
  opacity: 0.55;
  cursor: wait;
}

.option-mark {
  flex: none;
  width: 9px;
  height: 9px;
  border: 1px solid var(--border-strong);
  border-radius: 50%;
  background: var(--panel-3);
}

.option-btn.safe .option-mark {
  border-color: rgba(54, 211, 153, 0.6);
  background: var(--ok);
}

.option-btn.warn .option-mark {
  border-color: rgba(245, 166, 35, 0.6);
  background: var(--warn);
}

.option-btn.danger .option-mark {
  border-color: rgba(239, 91, 91, 0.6);
  background: var(--danger);
}

.option-label {
  flex: 1;
  font-size: 14.5px;
  line-height: 1.55;
}

.option-arrow {
  color: var(--muted);
  transition: transform 0.16s ease;
}

.option-btn:hover .option-arrow {
  transform: translateX(3px);
  color: var(--accent);
}

.inline-error {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  color: #ffabab;
  font-size: 13px;
}

.basis-panel {
  margin-top: 24px;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 0 10px 10px 0;
  background: rgba(10, 15, 21, 0.5);
}

.basis-head {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-2);
  font-size: 12.5px;
}

.basis-head strong {
  color: var(--text);
}

.basis-head .mono {
  margin-left: auto;
  color: var(--accent-2);
  font-size: 11px;
}

.basis-panel blockquote {
  margin-top: 10px;
  color: var(--text-2);
  font-size: 13px;
  line-height: 1.8;
}

.basis-panel blockquote + blockquote {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border);
}

.basis-panel footer {
  margin-top: 5px;
  color: var(--muted);
  font-size: 11px;
}

/* ===== 处置单 ===== */

.report-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.print-sheet {
  max-width: 980px;
  margin: 0 auto;
  padding: 36px 42px 30px;
  background:
    linear-gradient(180deg, rgba(22, 33, 44, 0.96), rgba(17, 25, 33, 0.98));
}

.sheet-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 18px;
  border-bottom: 2px solid var(--accent);
}

.sheet-brand {
  display: flex;
  align-items: center;
  gap: 11px;
}

.sheet-logo {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border: 1px solid rgba(246, 178, 60, 0.5);
  border-radius: 7px;
  background: var(--accent-soft);
  color: var(--accent-2);
  font-size: 18px;
  font-weight: 800;
}

.sheet-brand strong {
  display: block;
  font-size: 17px;
  letter-spacing: 0.12em;
}

.sheet-brand span {
  display: block;
  margin-top: 2px;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.12em;
}

.sheet-no {
  text-align: right;
}

.sheet-no span {
  display: block;
  color: var(--muted);
  font-size: 10.5px;
}

.sheet-no strong {
  display: block;
  margin-top: 3px;
  color: var(--accent-2);
  font-size: 13px;
}

.sheet-title {
  padding: 24px 0 18px;
}

.level-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.level-badge.danger {
  background: var(--danger-soft);
  color: #ff9b9b;
}

.level-badge.warn {
  background: var(--warn-soft);
  color: #ffd08a;
}

.level-badge.info {
  background: var(--cloud-soft);
  color: #bccaff;
}

.sheet-title h1 {
  margin-top: 10px;
  font-size: clamp(23px, 3vw, 30px);
  line-height: 1.4;
}

.sheet-title p {
  margin-top: 9px;
  color: var(--text-2);
  font-size: 14px;
  line-height: 1.8;
}

.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  margin: 4px 0 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--border);
}

.meta-grid > div {
  padding: 11px 14px;
  background: var(--panel);
}

.meta-grid dt {
  color: var(--muted);
  font-size: 10.5px;
}

.meta-grid dd {
  margin-top: 3px;
  color: var(--text);
  font-size: 13px;
  line-height: 1.55;
}

.sheet-section {
  margin-top: 24px;
}

.sheet-section h2 {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 16px;
  letter-spacing: 0.04em;
}

.sheet-section h2 .mono {
  color: var(--accent);
  font-size: 11px;
}

.process-table {
  width: 100%;
  margin-top: 10px;
  border-collapse: collapse;
  font-size: 12.5px;
}

.process-table th,
.process-table td {
  padding: 9px 10px;
  border: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
  line-height: 1.6;
}

.process-table th {
  background: var(--panel-2);
  color: var(--text-2);
  font-size: 11.5px;
  font-weight: 600;
}

.col-step {
  width: 46px;
  text-align: center !important;
}

.process-table td:first-child {
  text-align: center;
  color: var(--accent);
}

.basis-cell {
  color: var(--muted);
  font-size: 11px;
}

.basis-ref {
  display: block;
}

.conclusion-text {
  margin-top: 9px;
  color: var(--text-2);
  font-size: 13.5px;
  line-height: 1.8;
}

.action-list {
  margin-top: 9px;
  padding-left: 1.4em;
  color: var(--text-2);
  font-size: 13.5px;
  line-height: 1.85;
}

.action-list li {
  margin: 5px 0;
}

.action-list li::marker {
  color: var(--accent);
}

.safety-box {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-top: 9px;
  padding: 12px 14px;
  border: 1px solid rgba(245, 166, 35, 0.3);
  border-radius: 8px;
  background: var(--warn-soft);
  color: #ffd08a;
  font-size: 13px;
  line-height: 1.75;
}

.safety-box :deep(.icon) {
  margin-top: 2px;
  flex: none;
}

.ref-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin-top: 9px;
  padding-left: 1.4em;
}

.ref-list li {
  color: var(--text-2);
  font-size: 12px;
  line-height: 1.7;
}

.ref-list strong {
  color: var(--text);
  font-size: 12.5px;
}

.ref-list span {
  margin-left: 6px;
  color: var(--muted);
}

.ref-list p {
  margin-top: 2px;
  color: var(--muted);
  font-size: 11.5px;
}

.sheet-sign {
  display: flex;
  flex-wrap: wrap;
  gap: 26px;
  margin-top: 32px;
  padding-top: 18px;
  border-top: 1px solid var(--border);
  color: var(--text-2);
  font-size: 12.5px;
}

.sign-line {
  display: inline-block;
  width: 120px;
  height: 1px;
  margin-left: 4px;
  background: var(--border-strong);
  vertical-align: middle;
}

.sign-line.short {
  width: 90px;
}

.sheet-foot {
  margin-top: 20px;
  padding-top: 12px;
  border-top: 1px dashed var(--border);
  color: var(--muted);
  font-size: 10.5px;
  text-align: center;
}

@media (max-width: 980px) {
  .diag-work {
    grid-template-columns: minmax(0, 1fr);
  }

  .steps-panel {
    position: static;
  }

  .topic-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .diag-principles {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .question-inner {
    padding: 18px 16px 20px;
  }

  .question-inner h2 {
    font-size: 21px;
  }

  .question-text {
    font-size: 16px;
  }

  .report-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .report-actions .row {
    justify-content: space-between;
  }

  .print-sheet {
    padding: 20px 16px;
  }

  .meta-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .sheet-head {
    flex-direction: column;
  }

  .sheet-no {
    text-align: left;
  }

  .process-table {
    font-size: 11.5px;
  }
}

/* 打印：处置单切换为白底黑字，A4 可直接交付 */
@media print {
  .diag-view {
    max-width: none;
    gap: 0;
  }

  .print-sheet {
    --panel: #fff;
    --panel-2: #f5f5f5;
    --panel-3: #ececec;
    --bg-2: #f7f7f7;
    --border: #c9c9c9;
    --border-strong: #999;
    --text: #111;
    --text-2: #333;
    --muted: #555;
    --accent: #8a5a00;
    --accent-2: #8a5a00;
    --accent-soft: #f4e8d0;
    --ok-soft: #e7f6ee;
    --warn-soft: #fff8e6;
    --danger-soft: #fde8e8;
    max-width: none;
    margin: 0;
    padding: 14mm;
    border: none;
    border-radius: 0;
    background: #fff !important;
    color: #111 !important;
    box-shadow: none;
  }

  .print-sheet .sheet-head {
    flex-direction: row;
    border-bottom-color: #8a5a00;
  }

  .print-sheet .sheet-no {
    text-align: right;
  }

  .print-sheet .meta-grid {
    grid-template-columns: 1fr 1fr;
  }

  .print-sheet .process-table {
    font-size: 12px;
  }

  .print-sheet .level-badge.danger {
    background: #fde8e8;
    color: #9b1c1c;
  }

  .print-sheet .level-badge.warn {
    background: #fff1cc;
    color: #7a4b00;
  }

  .print-sheet .level-badge.info {
    background: #e8edff;
    color: #263a8a;
  }

  .print-sheet .safety-box {
    border-color: #d8b56a;
    background: #fff8e6;
    color: #7a4b00;
  }

  .print-sheet .sheet-logo {
    border-color: #8a5a00;
    background: #f4e8d0;
    color: #8a5a00;
  }

  .print-sheet a {
    color: inherit;
    text-decoration: none;
  }

  .print-sheet .sheet-section {
    break-inside: avoid;
  }

  .print-sheet .process-table tr {
    break-inside: avoid;
  }
}
</style>
