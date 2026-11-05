<script setup lang="ts">
// 脚手架占位页：验证前后端链路跑通。
// 真正的问答界面 11-09 ~ 11-10 成型（大字、少层级、触控友好）。
import { onMounted, ref } from 'vue'

interface HealthInfo {
  status: string
  service: string
  version: string
}

const health = ref<HealthInfo | null>(null)
const healthError = ref('')

onMounted(async () => {
  try {
    const res = await fetch('/health')
    health.value = await res.json()
  } catch {
    healthError.value = '后端未启动：请先在 backend/ 下启动 uvicorn'
  }
})
</script>

<template>
  <main class="shell">
    <header class="header">
      <h1>车间智答</h1>
      <p class="sub">面向智能制造一线的本地化 AI 知识与故障排查助手</p>
    </header>

    <section class="card">
      <h2>系统状态</h2>
      <p v-if="health">
        <span class="dot ok" />
        后端已连接（{{ health.service }} v{{ health.version }}）
      </p>
      <p v-else-if="healthError">
        <span class="dot danger" />
        {{ healthError }}
      </p>
      <p v-else>
        <span class="dot warn" />
        正在检查后端连接…
      </p>
    </section>
  </main>
</template>

<style scoped>
.shell {
  max-width: 720px;
  margin: 48px auto;
  padding: 0 20px;
}

.header {
  border-left: 6px solid var(--accent);
  padding-left: 16px;
  margin-bottom: 32px;
}

.header h1 {
  font-size: 34px;
  letter-spacing: 2px;
}

.sub {
  color: var(--muted);
  margin-top: 6px;
}

.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 20px;
}

.card h2 {
  font-size: 18px;
  margin-bottom: 12px;
}

.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 8px;
}

.ok { background: var(--ok); }
.warn { background: var(--warn); }
.danger { background: var(--danger); }
</style>
