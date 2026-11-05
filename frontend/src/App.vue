<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ChatView from './components/ChatView.vue'
import DiagnosisView from './components/DiagnosisView.vue'
import Icon from './components/Icon.vue'
import KnowledgeView from './components/KnowledgeView.vue'
import { getHealth } from './lib/api'
import type { HealthInfo } from './lib/types'

type ViewKey = 'chat' | 'diag' | 'kb'

const views = { chat: ChatView, diag: DiagnosisView, kb: KnowledgeView }
const navItems: { key: ViewKey; label: string; icon: string }[] = [
  { key: 'chat', label: '智能问答', icon: 'chat' },
  { key: 'diag', label: '故障排查', icon: 'wrench' },
  { key: 'kb', label: '知识库', icon: 'database' },
]

function readHash(): ViewKey {
  const hash = window.location.hash.replace('#', '')
  return hash === 'diag' || hash === 'kb' ? hash : 'chat'
}

const active = ref<ViewKey>(readHash())
const health = ref<HealthInfo | null>(null)
const healthError = ref('')
let timer: number | undefined

function setView(key: ViewKey) {
  active.value = key
  if (window.location.hash !== `#${key}`) window.location.hash = key
}

function onHashChange() {
  active.value = readHash()
}

async function refreshHealth() {
  try {
    health.value = await getHealth()
    healthError.value = ''
  } catch (err) {
    health.value = null
    healthError.value = err instanceof Error ? err.message : '后端未连接'
  }
}

watch(active, (value) => {
  if (window.location.hash !== `#${value}`) window.location.hash = value
})

onMounted(() => {
  refreshHealth()
  timer = window.setInterval(refreshHealth, 30000)
  window.addEventListener('hashchange', onHashChange)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
  window.removeEventListener('hashchange', onHashChange)
})
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="logo-mark" aria-hidden="true">智</div>
        <div class="brand-text">
          <div class="brand-name">车间智答</div>
          <div class="brand-sub">WORKSHOP QA · LOCAL KNOWLEDGE ENGINE</div>
        </div>
      </div>

      <nav class="nav" aria-label="主导航">
        <button
          v-for="item in navItems"
          :key="item.key"
          class="nav-btn"
          :class="{ active: active === item.key }"
          type="button"
          @click="setView(item.key)"
        >
          <Icon :name="item.icon" :size="18" />
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="top-status">
        <span v-if="health" class="status-pill ok" title="FastAPI 与 Ollama 连接正常">
          <i class="dot" />
          <span class="status-text">本地引擎在线</span>
        </span>
        <span v-else class="status-pill danger" :title="healthError">
          <i class="dot" />
          <span class="status-text">后端未连接</span>
        </span>
        <span
          class="status-pill"
          :class="health?.cloud_configured ? 'cloud' : 'muted-pill'"
          :title="health?.cloud_configured ? 'DeepSeek 云端兜底已配置' : '未配置 DeepSeek Key'"
        >
          <Icon name="cloud" :size="14" />
          <span class="status-text">{{ health?.cloud_configured ? '云端兜底就绪' : '云端未配置' }}</span>
        </span>
      </div>
    </header>

    <main class="main">
      <KeepAlive>
        <component :is="views[active]" />
      </KeepAlive>
    </main>

    <footer class="footer">
      <div class="foot-left">
        <span>数据不出厂</span>
        <i class="sep" />
        <span>离线可用</span>
        <i class="sep" />
        <span>回答可溯源</span>
      </div>
      <div class="foot-right">
        <span class="mono">v{{ health?.version ?? '0.3.0' }}</span>
        <i class="sep" />
        <a href="https://github.com/rqy18723992791-afk/workshop-qa" target="_blank" rel="noreferrer">
          开源仓库
        </a>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.app-shell {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 26px;
  height: 74px;
  padding: 0 28px;
  border-bottom: 1px solid var(--border);
  background: rgba(8, 12, 17, 0.82);
  backdrop-filter: blur(16px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 250px;
}

.logo-mark {
  position: relative;
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid rgba(246, 178, 60, 0.55);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(246, 178, 60, 0.22), rgba(246, 178, 60, 0.03)),
    var(--panel);
  color: var(--accent-2);
  font-size: 21px;
  font-weight: 800;
  box-shadow: inset 0 0 18px rgba(246, 178, 60, 0.08);
}

.logo-mark::after {
  content: '';
  position: absolute;
  right: -4px;
  bottom: -4px;
  width: 10px;
  height: 10px;
  border-right: 2px solid var(--accent);
  border-bottom: 2px solid var(--accent);
}

.brand-name {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.14em;
  line-height: 1.2;
}

.brand-sub {
  margin-top: 3px;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.16em;
}

.nav {
  display: flex;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(17, 25, 33, 0.75);
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 8px 15px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font-size: 14px;
  font-weight: 600;
  transition: all 0.16s ease;
}

.nav-btn:hover {
  color: var(--text);
  background: var(--panel-2);
}

.nav-btn.active {
  border-color: rgba(246, 178, 60, 0.32);
  background: linear-gradient(180deg, rgba(246, 178, 60, 0.18), rgba(246, 178, 60, 0.07));
  color: var(--accent-2);
}

.top-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 11px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--panel);
  color: var(--text-2);
  font-size: 12px;
  white-space: nowrap;
}

.status-pill .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--muted);
}

.status-pill.ok {
  border-color: rgba(54, 211, 153, 0.34);
  color: #8df0c8;
}

.status-pill.ok .dot {
  background: var(--ok);
  box-shadow: 0 0 0 4px rgba(54, 211, 153, 0.12);
}

.status-pill.danger {
  border-color: rgba(239, 91, 91, 0.4);
  color: #ffabab;
}

.status-pill.danger .dot {
  background: var(--danger);
}

.status-pill.cloud {
  border-color: rgba(142, 168, 255, 0.34);
  color: #b9c8ff;
}

.status-pill.muted-pill {
  color: var(--muted);
}

.main {
  flex: 1;
  width: min(1440px, 100%);
  margin: 0 auto;
  padding: 26px 28px 44px;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 28px 22px;
  border-top: 1px solid rgba(34, 48, 61, 0.6);
  color: var(--muted);
  font-size: 12px;
}

.foot-left,
.foot-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sep {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--border-strong);
}

.foot-right a {
  color: var(--muted);
}

.foot-right a:hover {
  color: var(--accent-2);
}

@media (max-width: 1080px) {
  .topbar {
    gap: 14px;
    padding: 0 18px;
  }

  .brand {
    min-width: auto;
  }

  .brand-sub {
    display: none;
  }

  .status-text {
    display: none;
  }
}

@media (max-width: 760px) {
  .topbar {
    flex-wrap: wrap;
    height: auto;
    padding: 12px 14px;
    gap: 10px;
  }

  .brand {
    flex: 1;
  }

  .logo-mark {
    width: 36px;
    height: 36px;
    font-size: 18px;
  }

  .brand-name {
    font-size: 18px;
  }

  .nav {
    order: 3;
    width: 100%;
    justify-content: space-between;
  }

  .nav-btn {
    flex: 1;
    justify-content: center;
    padding: 8px 6px;
    font-size: 13px;
  }

  .top-status {
    margin-left: 0;
  }

  .main {
    padding: 16px 14px 32px;
  }

  .footer {
    flex-direction: column;
    gap: 8px;
    padding: 14px;
  }
}
</style>
