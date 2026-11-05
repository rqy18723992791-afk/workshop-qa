<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Icon from './Icon.vue'
import type { Source } from '../lib/types'

const props = defineProps<{ source: Source; active?: boolean; defaultOpen?: boolean }>()
const emit = defineEmits<{ select: [index: number] }>()

const expanded = ref(Boolean(props.defaultOpen))

/** 引用卡片展示纯文本：去掉标题井号、加粗/斜体星号等 Markdown 标记，避免原文符号干扰阅读 */
const plainText = computed(() =>
  props.source.text
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/^\s*>\s?/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim(),
)

const scoreClass = computed(() => {
  if (props.source.score >= 0.72) return 'high'
  if (props.source.score >= 0.6) return 'mid'
  return 'low'
})

watch(
  () => props.active,
  (active) => {
    if (active) expanded.value = true
  },
)

function toggle() {
  expanded.value = !expanded.value
  emit('select', props.source.index)
}
</script>

<template>
  <div class="source-card" :class="{ active }" @click="toggle">
    <div class="src-head">
      <span class="src-index mono">{{ String(source.index).padStart(2, '0') }}</span>
      <div class="src-title">
        <strong>{{ source.doc_title }}</strong>
        <span class="src-meta">
          <span class="mono">{{ source.doc_no }}</span>
          <i class="dot-sep" />
          <span>{{ source.heading_path || '全文' }}</span>
        </span>
      </div>
      <span class="src-score mono" :class="scoreClass">{{ source.score.toFixed(2) }}</span>
    </div>
    <p class="src-text" :class="{ expanded }">{{ plainText }}</p>
    <button class="src-toggle" type="button" @click.stop="toggle">
      <Icon name="chevron-right" :size="13" :class="{ rotated: expanded }" />
      {{ expanded ? '收起原文' : '展开原文' }}
    </button>
  </div>
</template>

<style scoped>
.source-card {
  padding: 12px 13px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(10, 15, 21, 0.55);
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease;
}

.source-card:hover {
  border-color: var(--border-strong);
  background: rgba(16, 24, 33, 0.8);
}

.source-card.active {
  border-color: rgba(246, 178, 60, 0.6);
  background: rgba(246, 178, 60, 0.06);
  box-shadow: inset 3px 0 0 var(--accent);
}

.src-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.src-index {
  display: grid;
  place-items: center;
  flex: none;
  width: 26px;
  height: 26px;
  border: 1px solid rgba(246, 178, 60, 0.35);
  border-radius: 6px;
  background: var(--accent-soft);
  color: var(--accent-2);
  font-size: 11px;
  font-weight: 700;
}

.src-title {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  flex: 1;
}

.src-title strong {
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.45;
}

.src-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.4;
}

.dot-sep {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--border-strong);
}

.src-score {
  flex: none;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
}

.src-score.high {
  background: var(--ok-soft);
  color: #7ef0c4;
}

.src-score.mid {
  background: var(--warn-soft);
  color: #ffd08a;
}

.src-score.low {
  background: var(--panel-3);
  color: var(--muted);
}

.src-text {
  display: -webkit-box;
  margin-top: 9px;
  overflow: hidden;
  color: var(--text-2);
  font-size: 12.5px;
  line-height: 1.72;
  white-space: pre-wrap;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.src-text.expanded {
  display: block;
  -webkit-line-clamp: unset;
  color: var(--text-2);
}

.src-toggle {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-top: 6px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 11px;
}

.src-toggle:hover {
  color: var(--accent-2);
}

.rotated {
  transform: rotate(90deg);
}

.src-toggle :deep(.icon) {
  transition: transform 0.16s ease;
}
</style>
