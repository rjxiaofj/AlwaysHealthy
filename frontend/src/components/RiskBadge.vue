<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ level: string; text?: string }>()

const mapping: Record<string, { cls: string; label: string }> = {
  低: { cls: 'level-low', label: '低风险' },
  中: { cls: 'level-mid', label: '需要关注' },
  高: { cls: 'level-high', label: '高风险' },
  信息不足: { cls: 'level-unknown', label: '信息不足' },
}

const style = computed(() => mapping[props.level] || mapping['信息不足'])
</script>

<template>
  <span class="chip" :class="style.cls">{{ text || style.label }}</span>
</template>
