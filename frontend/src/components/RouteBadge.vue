<script setup lang="ts">
import Icon from './Icon.vue'

withDefaults(defineProps<{ route: 'local' | 'cloud'; compact?: boolean; refused?: boolean }>(), {
  compact: false,
  refused: false,
})
</script>

<template>
  <span class="route-badge" :class="route">
    <Icon :name="route === 'local' ? 'cpu' : 'cloud'" :size="13" />
    <span class="route-name">{{ route === 'local' ? '本地模型' : '云端模型' }}</span>
    <em v-if="!compact">{{ refused ? '已拒答' : route === 'local' ? '知识库作答' : '通用建议' }}</em>
  </span>
</template>

<style scoped>
.route-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.6;
  white-space: nowrap;
}

.route-badge.local {
  border-color: rgba(54, 211, 153, 0.36);
  background: var(--ok-soft);
  color: #82efc6;
}

.route-badge.cloud {
  border-color: rgba(142, 168, 255, 0.4);
  background: var(--cloud-soft);
  color: #bccaff;
}

.route-badge em {
  font-style: normal;
  opacity: 0.75;
  font-weight: 500;
}
</style>
