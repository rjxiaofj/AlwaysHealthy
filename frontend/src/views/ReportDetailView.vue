<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { knowledgeApi, reportApi } from '@/api'
import { tokens } from '@/api/client'
import type { KnowledgeSource, ReportDetail } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import RiskBadge from '@/components/RiskBadge.vue'
import { useToastStore } from '@/stores/toast'
import { downloadBlob } from '@/utils/download'

const route = useRoute()
const toast = useToastStore()
const report = ref<ReportDetail | null>(null)
const sources = ref<KnowledgeSource[]>([])
const loading = ref(true)

async function download() {
  if (!report.value) return
  try {
    const response = await fetch(reportApi.exportUrl(report.value.id), {
      headers: { Authorization: `Bearer ${tokens.access}` },
    })
    if (!response.ok) throw new Error('导出失败')
    const blob = await response.blob()
    downloadBlob(blob, `${report.value.title}.md`)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '导出失败')
  }
}

async function printPdf() {
  if (!report.value) return
  // 先同步开窗拿引用：浏览器只在用户手势的同步调用栈里放行 window.open，
  // 放到 fetch 之后（异步回调里）会被弹窗拦截器挡住
  const win = window.open('', '_blank')
  if (!win) {
    toast.error('浏览器拦截了新窗口，请允许弹出窗口后重试')
    return
  }
  try {
    // print 端点需要登录态，先 fetch 拿到打印友好的 HTML 再写进新窗口
    const response = await fetch(reportApi.printUrl(report.value.id), {
      headers: { Authorization: `Bearer ${tokens.access}` },
    })
    if (!response.ok) throw new Error('导出失败')
    const html = await response.text()
    win.document.write(html)
    win.document.close()
    // document.write 是同步的，close 时文档已就绪；再监听 load 收不到事件。
    // 写完直接触发打印即可，等 300ms 让样式先应用
    setTimeout(() => win.print(), 300)
  } catch (error) {
    win.close()
    toast.error(error instanceof Error ? error.message : '导出失败')
  }
}

onMounted(async () => {
  try {
    report.value = await reportApi.detail(String(route.params.id))
  } finally {
    loading.value = false
  }
  sources.value = await knowledgeApi.sources().catch(() => [])
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
          <button class="btn btn-primary" @click="printPdf">导出 PDF</button>
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

      <details v-if="sources.length" class="glass card-pad">
        <summary class="cursor-pointer text-[14px] font-semibold">资料来源台账 {{ sources.length }} 份</summary>
        <ul class="mt-2 flex flex-col gap-2">
          <li v-for="item in sources" :key="item.source_id" class="rounded-[14px] border px-3 py-2" :style="{ borderColor: 'var(--color-border)' }">
            <p class="text-[12px]">{{ item.title }}</p>
            <p class="mt-1 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              {{ item.issuing_org }} · 版本 {{ item.version || '未标注' }} · {{ item.publish_date || '发布日期未标注' }} · 适用 {{ item.applicable_population }}
            </p>
          </li>
        </ul>
        <p class="mt-2 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
          报告里的医学依据按标题与版本取自这些资料，摘要随代码库一起发布，正式引用请核对出版方原文
        </p>
      </details>
    </template>
  </div>
</template>
