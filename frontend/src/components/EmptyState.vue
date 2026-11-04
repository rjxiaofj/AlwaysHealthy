<script setup lang="ts">
defineProps<{ title: string; description?: string; action?: string }>()
const emit = defineEmits<{ action: [] }>()
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-3 py-12 text-center">
    <div class="h-10 w-10 rounded-full border border-dashed" :style="{ borderColor: 'var(--color-border)' }" />
    <p class="text-[13px]" :style="{ color: 'var(--color-text-secondary)' }">{{ title }}</p>
    <p v-if="description" class="max-w-[380px] text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">
      {{ description }}
    </p>
    <button v-if="action" class="btn btn-ghost mt-1" @click="emit('action')">{{ action }}</button>
  </div>
</template>
