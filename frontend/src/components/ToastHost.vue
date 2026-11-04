<script setup lang="ts">
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
</script>

<template>
  <div class="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
    <transition-group name="fade">
      <div
        v-for="item in toast.items"
        :key="item.id"
        class="glass-strong px-4 py-3 text-[13px] max-w-[320px]"
        :style="{
          color:
            item.tone === 'error'
              ? 'var(--color-danger)'
              : item.tone === 'success'
                ? 'var(--color-success)'
                : 'var(--color-text-primary)',
        }"
      >
        {{ item.text }}
      </div>
    </transition-group>
  </div>
</template>
