<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  deleteDocument,
  getDocuments,
  getHealth,
  importDocuments,
  reindexDocuments,
  searchKnowledge,
  uploadDocument,
} from '../lib/api'
import type { DocRecord, HealthInfo, SearchResult } from '../lib/types'
import Icon from './Icon.vue'
import SourceCard from './SourceCard.vue'

const documents = ref<DocRecord[]>([])
const loading = ref(true)
const error = ref('')
const busy = ref('')
const filter = ref('')
const health = ref<HealthInfo | null>(null)

const searchQuery = ref('')
const searching = ref(false)
const searchResult = ref<SearchResult | null>(null)
const searchError = ref('')

const fileInput = ref<HTMLInputElement | null>(null)
const deleteTarget = ref<DocRecord | null>(null)
const modalType = ref<'delete' | 'reindex' | null>(null)

const toast = ref<{ type: 'ok' | 'warn' | 'error'; message: string } | null>(null)
let toastTimer: number | undefined

const totalChunks = computed(() => documents.value.reduce((sum, d) => sum + d.chunk_count, 0))
const categories = computed(() => new Set(documents.value.map((d) => d.category)).size)
const lastImported = computed(() => {
  const times = documents.value.map((d) => d.imported_at).filter(Boolean).sort()
  return times.length ? times[times.length - 1].replace('T', ' ') : '—'
})
const filtered = computed(() => {
  const keyword = filter.value.trim().toLowerCase()
  if (!keyword) return documents.value
  return documents.value.filter((d) =>
    [d.title, d.doc_no, d.category, d.file].some((v) => v.toLowerCase().includes(keyword)),
  )
})

function showToast(type: 'ok' | 'warn' | 'error', message: string) {
  toast.value = { type, message }
  if (toastTimer) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toast.value = null
  }, 3600)
}

async function loadDocuments() {
  loading.value = true
  error.value = ''
  try {
    const data = await getDocuments()
    documents.value = data.documents
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载文档清单失败'
  } finally {
    loading.value = false
  }
}

async function runImport(rebuild = false) {
  busy.value = rebuild ? 'reindex' : 'import'
  try {
    const result = rebuild ? await reindexDocuments() : await importDocuments(false)
    const suffix = result.errors.length ? `，${result.errors.length} 份失败` : ''
    showToast(result.errors.length ? 'warn' : 'ok', `已导入 ${result.count} 份文档${suffix}`)
    await loadDocuments()
  } catch (err) {
    showToast('error', err instanceof Error ? err.message : '导入失败')
  } finally {
    busy.value = ''
    modalType.value = null
  }
}

async function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  busy.value = 'upload'
  try {
    await uploadDocument(file)
    showToast('ok', `已上传并入库：${file.name}`)
    await loadDocuments()
  } catch (err) {
    showToast('error', err instanceof Error ? err.message : '上传失败')
  } finally {
    busy.value = ''
  }
}

async function confirmDelete() {
  const target = deleteTarget.value
  if (!target) return
  busy.value = 'delete'
  try {
    await deleteDocument(target.doc_id)
    showToast('ok', `已删除：${target.title}`)
    deleteTarget.value = null
    modalType.value = null
    await loadDocuments()
  } catch (err) {
    showToast('error', err instanceof Error ? err.message : '删除失败')
  } finally {
    busy.value = ''
  }
}

function askDelete(doc: DocRecord) {
  deleteTarget.value = doc
  modalType.value = 'delete'
}

function askReindex() {
  modalType.value = 'reindex'
}

function closeModal() {
  if (busy.value) return
  modalType.value = null
  deleteTarget.value = null
}

async function runSearch() {
  const query = searchQuery.value.trim()
  if (!query || searching.value) return
  searching.value = true
  searchError.value = ''
  try {
    searchResult.value = await searchKnowledge(query, 4)
  } catch (err) {
    searchError.value = err instanceof Error ? err.message : '检索失败'
    searchResult.value = null
  } finally {
    searching.value = false
  }
}

function categoryClass(category: string): string {
  if (category.includes('故障')) return 'danger'
  if (category.includes('安全')) return 'warn'
  if (category.includes('点检') || category.includes('保养')) return 'local'
  if (category.includes('工艺')) return 'cloud'
  return 'accent'
}

onMounted(async () => {
  await loadDocuments()
  try {
    health.value = await getHealth()
  } catch {
    health.value = null
  }
})

onBeforeUnmount(() => {
  if (toastTimer) window.clearTimeout(toastTimer)
})
</script>

<template>
  <div class="kb-view">
    <header class="kb-hero">
      <div>
        <div class="eyebrow">KNOWLEDGE BASE · CHROMA + BGE-M3</div>
        <h1>知识库管理</h1>
        <p>
          导入厂内 Markdown / txt 文档，系统自动切分、向量化并写入本地 Chroma。
          文档以「文档编号」为唯一键，重复导入自动覆盖，删除时源文件移入回收目录。
        </p>
      </div>
      <div class="kb-actions">
        <button class="btn btn-ghost" type="button" :disabled="Boolean(busy)" @click="askReindex">
          <Icon name="refresh" :size="15" />
          重建索引
        </button>
        <button class="btn btn-ghost" type="button" :disabled="Boolean(busy)" @click="fileInput?.click()">
          <Icon name="upload" :size="15" />
          上传文档
        </button>
        <button class="btn btn-primary" type="button" :disabled="Boolean(busy)" @click="runImport(false)">
          <span v-if="busy === 'import'" class="spinner" />
          <Icon v-else name="layers" :size="15" />
          扫描导入
        </button>
        <input ref="fileInput" type="file" accept=".md,.txt" hidden @change="onFileChange" />
      </div>
    </header>

    <div class="stat-grid">
      <div class="stat-card panel">
        <span class="stat-label">文档数量</span>
        <strong class="mono">{{ documents.length }}</strong>
        <span class="stat-foot">份厂内手册</span>
      </div>
      <div class="stat-card panel">
        <span class="stat-label">知识切片</span>
        <strong class="mono">{{ totalChunks }}</strong>
        <span class="stat-foot">Chroma 向量条目</span>
      </div>
      <div class="stat-card panel">
        <span class="stat-label">覆盖类别</span>
        <strong class="mono">{{ categories }}</strong>
        <span class="stat-foot">操作 / 点检 / 故障 / 安全 / 工艺</span>
      </div>
      <div class="stat-card panel">
        <span class="stat-label">检索阈值</span>
        <strong class="mono">{{ (health?.retrieval_min_sim ?? 0.6).toFixed(2) }}</strong>
        <span class="stat-foot">低于阈值拒答或升级云端</span>
      </div>
    </div>

    <section class="panel doc-panel">
      <header class="panel-head">
        <div>
          <div class="eyebrow">DOCUMENTS</div>
          <h2>文档清单</h2>
        </div>
        <div class="doc-tools">
          <span class="updated mono">最近入库 {{ lastImported }}</span>
          <div class="search-box">
            <Icon name="search" :size="15" />
            <input v-model="filter" class="input filter-input" placeholder="筛选标题 / 编号 / 类别" />
          </div>
        </div>
      </header>

      <div v-if="loading" class="empty">
        <span class="spinner" />
        <span>正在读取文档清单…</span>
      </div>
      <div v-else-if="error" class="empty">
        <Icon name="alert" :size="24" />
        <p>{{ error }}</p>
        <button class="btn btn-sm" type="button" @click="loadDocuments">重试</button>
      </div>
      <div v-else-if="!filtered.length" class="empty">
        <Icon name="database" :size="26" />
        <p>{{ documents.length ? '没有匹配的文档' : '知识库还是空的，先扫描导入示例文档' }}</p>
      </div>

      <div v-else class="doc-table">
        <div class="doc-row doc-head">
          <span>文档</span>
          <span>编号</span>
          <span>类别</span>
          <span>版本</span>
          <span class="num">切片</span>
          <span class="num">入库时间</span>
          <span class="actions-col">操作</span>
        </div>
        <div v-for="doc in filtered" :key="doc.doc_id" class="doc-row">
          <div class="doc-name">
            <span class="doc-icon"><Icon name="file" :size="15" /></span>
            <div>
              <strong>{{ doc.title }}</strong>
              <span class="mono">{{ doc.file }}</span>
            </div>
          </div>
          <span class="mono doc-no">{{ doc.doc_no }}</span>
          <span><span class="tag" :class="categoryClass(doc.category)">{{ doc.category }}</span></span>
          <span class="mono muted">{{ doc.version }}</span>
          <span class="mono num">{{ doc.chunk_count }}</span>
          <span class="mono num muted">{{ doc.imported_at.replace('T', ' ').slice(5, 16) }}</span>
          <span class="actions-col">
            <button class="btn btn-danger btn-sm" type="button" :disabled="Boolean(busy)" @click="askDelete(doc)">
              <Icon name="trash" :size="13" />
              删除
            </button>
          </span>
        </div>
      </div>
    </section>

    <section class="panel search-panel">
      <div class="search-head">
        <div>
          <div class="eyebrow">RETRIEVAL LAB</div>
          <h2>检索测试台</h2>
          <p>直接观察向量检索的命中片段与相似度，用于调试阈值和验证知识库覆盖。</p>
        </div>
        <div class="retrieval-input">
          <input
            v-model="searchQuery"
            class="input"
            placeholder="输入一条设备问题，例如：料筒温度异常怎么排查"
            @keydown.enter="runSearch"
          />
          <button class="btn btn-primary" type="button" :disabled="searching || !searchQuery.trim()" @click="runSearch">
            <span v-if="searching" class="spinner" />
            <Icon v-else name="search" :size="15" />
            检索
          </button>
        </div>
      </div>

      <div v-if="searchError" class="inline-error">
        <Icon name="alert" :size="15" />
        <span>{{ searchError }}</span>
      </div>

      <div v-if="searchResult" class="search-result">
        <div class="result-meta">
          <span class="tag" :class="searchResult.has_relevant ? 'local' : 'warn'">
            {{ searchResult.has_relevant ? '命中知识库' : '低于阈值' }}
          </span>
          <span class="mono">top1 {{ searchResult.max_score.toFixed(3) }}</span>
          <span class="mono muted">阈值 {{ searchResult.min_sim.toFixed(2) }}</span>
          <span class="muted">返回 {{ searchResult.hits.length }} 个片段</span>
        </div>
        <div class="result-list">
          <SourceCard v-for="hit in searchResult.hits" :key="hit.index" :source="hit" />
        </div>
      </div>
      <div v-else class="search-tip">
        <Icon name="activity" :size="22" />
        <span>检索结果会显示相似度、文档编号、章节和原文片段。</span>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="modalType" class="modal-backdrop" @click.self="closeModal">
        <div class="modal panel">
          <template v-if="modalType === 'delete' && deleteTarget">
            <div class="modal-icon danger"><Icon name="trash" :size="20" /></div>
            <h3>删除文档？</h3>
            <p>
              将删除《{{ deleteTarget.title }}》的 {{ deleteTarget.chunk_count }} 个向量切片，
              源文件会移入 <code>data/docs/.trash</code>，不会直接丢失。
            </p>
            <div class="modal-actions">
              <button class="btn btn-ghost" type="button" :disabled="Boolean(busy)" @click="closeModal">取消</button>
              <button class="btn btn-danger" type="button" :disabled="Boolean(busy)" @click="confirmDelete">
                <span v-if="busy === 'delete'" class="spinner" />
                确认删除
              </button>
            </div>
          </template>

          <template v-else>
            <div class="modal-icon warn"><Icon name="refresh" :size="20" /></div>
            <h3>重建全部索引？</h3>
            <p>
              将清空 Chroma 中的全部向量并重新扫描 <code>data/docs</code>。
              文档数较多时需要重新调用 bge-m3，耗时约数秒到数十秒。
            </p>
            <div class="modal-actions">
              <button class="btn btn-ghost" type="button" :disabled="Boolean(busy)" @click="closeModal">取消</button>
              <button class="btn btn-primary" type="button" :disabled="Boolean(busy)" @click="runImport(true)">
                <span v-if="busy === 'reindex'" class="spinner" />
                开始重建
              </button>
            </div>
          </template>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <Transition name="toast">
        <div v-if="toast" class="toast" :class="toast.type">
          <Icon :name="toast.type === 'ok' ? 'check' : 'alert'" :size="16" />
          <span>{{ toast.message }}</span>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.kb-view {
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.kb-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 10px 4px 6px;
}

.kb-hero h1 {
  margin-top: 7px;
  font-size: clamp(28px, 3.4vw, 40px);
  letter-spacing: 0.05em;
}

.kb-hero p {
  max-width: 720px;
  margin-top: 10px;
  color: var(--text-2);
  font-size: 14.5px;
  line-height: 1.8;
}

.kb-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex: none;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 18px;
}

.stat-label {
  color: var(--muted);
  font-size: 11.5px;
}

.stat-card strong {
  color: var(--text);
  font-size: 30px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-foot {
  color: var(--muted);
  font-size: 10.5px;
}

.doc-panel {
  overflow: hidden;
}

.panel-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
}

.panel-head h2 {
  margin-top: 3px;
  font-size: 19px;
}

.doc-tools {
  display: flex;
  align-items: center;
  gap: 12px;
}

.updated {
  color: var(--muted);
  font-size: 10.5px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-2);
  color: var(--muted);
}

.filter-input {
  width: 210px;
  padding: 8px 0;
  border: none;
  background: transparent;
  font-size: 12.5px;
  box-shadow: none !important;
}

.doc-table {
  display: flex;
  flex-direction: column;
}

.doc-row {
  display: grid;
  grid-template-columns: minmax(220px, 2.4fr) 110px 118px 58px 52px 112px 86px;
  gap: 12px;
  align-items: center;
  padding: 11px 20px;
  border-bottom: 1px solid rgba(34, 48, 61, 0.65);
  font-size: 12.5px;
}

.doc-row:last-child {
  border-bottom: none;
}

.doc-row:hover:not(.doc-head) {
  background: rgba(246, 178, 60, 0.035);
}

.doc-head {
  padding-top: 9px;
  padding-bottom: 9px;
  background: rgba(10, 15, 21, 0.4);
  color: var(--muted);
  font-size: 10.5px;
  letter-spacing: 0.06em;
}

.doc-name {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.doc-icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 30px;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--panel-2);
  color: var(--muted);
}

.doc-name > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.doc-name strong {
  overflow: hidden;
  color: var(--text);
  font-size: 12.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-name .mono {
  overflow: hidden;
  color: var(--muted);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-no {
  color: var(--accent-2);
  font-size: 11px;
}

.num {
  text-align: right;
}

.actions-col {
  display: flex;
  justify-content: flex-end;
}

.search-panel {
  padding: 20px;
}

.search-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
}

.search-head h2 {
  margin-top: 3px;
  font-size: 19px;
}

.search-head p {
  margin-top: 6px;
  color: var(--muted);
  font-size: 12.5px;
}

.retrieval-input {
  display: flex;
  gap: 8px;
  width: min(560px, 100%);
}

.result-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
  margin-top: 16px;
  color: var(--muted);
  font-size: 11px;
}

.result-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
  margin-top: 10px;
}

.search-tip {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 16px;
  padding: 16px;
  border: 1px dashed var(--border);
  border-radius: 10px;
  color: var(--muted);
  font-size: 12.5px;
}

.inline-error {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  color: #ffabab;
  font-size: 13px;
}

/* ===== 弹窗 ===== */

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(3, 6, 9, 0.72);
  backdrop-filter: blur(4px);
}

.modal {
  width: min(440px, 100%);
  padding: 24px;
  animation: fadeUp 0.18s ease both;
}

.modal-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 10px;
}

.modal-icon.danger {
  background: var(--danger-soft);
  color: var(--danger);
}

.modal-icon.warn {
  background: var(--warn-soft);
  color: var(--warn);
}

.modal h3 {
  margin-top: 14px;
  font-size: 18px;
}

.modal p {
  margin-top: 8px;
  color: var(--text-2);
  font-size: 13px;
  line-height: 1.75;
}

.modal code {
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--bg-2);
  color: var(--accent-2);
  font-family: var(--font-mono);
  font-size: 11.5px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}

/* ===== Toast ===== */

.toast {
  position: fixed;
  left: 50%;
  bottom: 28px;
  z-index: 90;
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: min(520px, calc(100vw - 32px));
  padding: 11px 16px;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  background: var(--panel-2);
  color: var(--text);
  font-size: 13px;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.45);
  transform: translateX(-50%);
}

.toast.ok {
  border-color: rgba(54, 211, 153, 0.4);
  color: #9df3d3;
}

.toast.warn {
  border-color: rgba(245, 166, 35, 0.45);
  color: #ffd08a;
}

.toast.error {
  border-color: rgba(239, 91, 91, 0.45);
  color: #ffb0b0;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.22s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 8px);
}

@media (max-width: 1100px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .doc-row {
    grid-template-columns: minmax(200px, 2.2fr) 100px 110px 54px 48px 80px;
  }

  .doc-row > :nth-child(6) {
    display: none;
  }

  .doc-head > :nth-child(6) {
    display: none;
  }
}

@media (max-width: 860px) {
  .kb-hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .panel-head {
    flex-direction: column;
    align-items: stretch;
  }

  .doc-tools {
    justify-content: space-between;
  }

  .filter-input {
    width: 100%;
  }

  .search-head {
    flex-direction: column;
    align-items: stretch;
  }

  .retrieval-input {
    width: 100%;
  }

  .result-list {
    grid-template-columns: minmax(0, 1fr);
  }

  .doc-row {
    grid-template-columns: minmax(0, 1fr) 74px;
    gap: 8px;
    padding: 12px 16px;
  }

  .doc-row > :nth-child(2),
  .doc-row > :nth-child(3),
  .doc-row > :nth-child(4),
  .doc-row > :nth-child(5),
  .doc-row > :nth-child(6) {
    display: none;
  }

  .doc-head {
    display: none;
  }

  .actions-col {
    grid-column: 2;
    grid-row: 1;
  }
}

@media (max-width: 560px) {
  .stat-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .kb-actions {
    width: 100%;
  }

  .kb-actions .btn {
    flex: 1;
  }
}
</style>
