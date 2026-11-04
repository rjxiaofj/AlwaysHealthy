<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { reportApi } from '@/api'
import { tokens } from '@/api/client'
import type { ReportDetail } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import RiskBadge from '@/components/RiskBadge.vue'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const toast = useToastStore()
const report = ref<ReportDetail | null>(null)
const loading = ref(true)

async function download() {
  if (!report.value) return
  try {
    const response = await fetch(reportApi.exportUrl(report.value.id), {
      headers: { Authorization: `Bearer ${tokens.access}` },
    })
    if (!response.ok) throw new Error('导出失败')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${report.value.title}.md`
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '导出失败')
  }
}

onMounted(async () => {
  try {
    report.value = await reportApi.detail(String(route.params.id))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="flex flex-col gap-4">
    <section class="glass card-pad">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <RouterLink to="/profile" class="text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">返回个人中心</RouterLink>
          <h1 class="mt-2 text-[20px] font-semibold">{{ report?.title || '报告' }}</h1>
          <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">
            {{ report ? new Date(report.created_at).toLocaleString('zh-CN') : '' }}
          </p>
        </div>
        <div class="flex items-center gap-2">
          <RiskBadge v-if="report?.content.overall_level" :level="report.content.overall_level" />
          <button class="btn btn-ghost" @click="download">导出 Markdown</button>
        </div>
      </div>
    </section>

    <section v-if="loading" class="glass card-pad text-[12px]">加载中</section>
    <section v-else-if="!report" class="glass card-pad">
      <EmptyState title="报告不存在" description="可能已被删除或不属于当前账号" />
    </section>
    <template v-else>
      <p class="px-1 text-[11px] leading-relaxed" :style="{ color: 'var(--color-text-tertiary)' }">
        {{ report.content.disclaimer }}
      </p>
      <section v-for="section in report.content.sections" :key="section.heading" class="glass card-pad">
        <h2 class="mb-2 text-[14px] font-semibold">{{ section.heading }}</h2>
        <p v-for="line in section.paragraphs" :key="line" class="text-[13px] leading-relaxed">{{ line }}</p>
        <ul v-if="section.items.length" class="mt-2 flex flex-col gap-1">
          <li v-for="item in section.items" :key="item" class="text-[13px]" :style="{ color: 'var(--color-text-secondary)' }">
            {{ item }}
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>
