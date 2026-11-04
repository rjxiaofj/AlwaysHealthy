<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { assessmentApi } from '@/api'
import type { Assessment, AssessmentSummary } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import RiskBadge from '@/components/RiskBadge.vue'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
const current = ref<Assessment | null>(null)
const history = ref<AssessmentSummary[]>([])
const loading = ref(true)
const running = ref(false)

const dimensionNames: Record<string, string> = {
  cardiovascular: '心血管健康',
  metabolic: '代谢健康',
  sleep: '睡眠与疲劳',
  mental: '心理健康',
  lifestyle: '生活方式',
}

const levelHint = computed(() => {
  if (!current.value) return ''
  if (current.value.urgency === '需尽快就医') return '本次评估存在需要尽快就医的提示，请优先处理报告中标注的维度'
  return '风险等级是平台内部提示分层，不是疾病诊断分级'
})

async function load() {
  loading.value = true
  try {
    const [latest, list] = await Promise.all([assessmentApi.latest(), assessmentApi.list(1, 10)])
    current.value = latest
    history.value = list.items
  } finally {
    loading.value = false
  }
}

async function runAssessment() {
  running.value = true
  try {
    current.value = await assessmentApi.create()
    toast.success('评估已生成')
    await load()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '评估失败')
  } finally {
    running.value = false
  }
}

async function openHistory(id: string) {
  current.value = await assessmentApi.detail(id)
}

onMounted(load)
</script>

<template>
  <div class="flex flex-col gap-4">
    <section class="glass card-pad">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 class="text-[20px] font-semibold">健康评估</h1>
          <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">{{ levelHint }}</p>
        </div>
        <div class="flex items-center gap-2">
          <span v-if="current" class="chip">规则版本 {{ current.rule_engine_version }}</span>
          <button class="btn btn-primary" :disabled="running" @click="runAssessment">
            {{ running ? '评估中' : '用当前档案评估' }}
          </button>
        </div>
      </div>
    </section>

    <div v-if="loading" class="glass card-pad text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">加载中</div>

    <template v-else-if="current">
      <section class="glass card-pad">
        <div class="flex flex-wrap items-center gap-4">
          <div>
            <p class="text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">总体风险提示</p>
            <div class="mt-1 flex items-center gap-2">
              <RiskBadge :level="current.overall_level" />
              <span v-if="current.urgency !== '非紧急'" class="chip level-mid">{{ current.urgency }}</span>
            </div>
          </div>
          <div class="h-10 w-px" :style="{ background: 'var(--color-border)' }" />
          <div>
            <p class="text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">评估时间</p>
            <p class="text-[13px]">{{ new Date(current.created_at).toLocaleString('zh-CN') }}</p>
          </div>
          <div>
            <p class="text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">知识库版本</p>
            <p class="text-[13px]">{{ current.knowledge_version }}</p>
          </div>
        </div>
      </section>

      <section class="grid gap-4 lg:grid-cols-2">
        <article v-for="item in current.dimensions" :key="item.dimension" class="glass card-pad">
          <div class="flex items-center justify-between">
            <h2 class="text-[14px] font-semibold">{{ dimensionNames[item.dimension] || item.dimension }}</h2>
            <RiskBadge :level="item.level" />
          </div>

          <p v-if="item.explanation" class="mt-2 text-[12px] leading-relaxed" :style="{ color: 'var(--color-text-secondary)' }">
            {{ item.explanation }}
          </p>

          <div v-if="item.risk_factors.length" class="mt-3">
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">命中依据</p>
            <ul class="mt-1 flex flex-col gap-1">
              <li v-for="factor in item.risk_factors" :key="factor.rule_id" class="text-[12px]">
                {{ factor.message }}
                <span v-if="factor.value !== null && factor.value !== undefined" :style="{ color: 'var(--color-text-tertiary)' }">
                  （{{ factor.value }}{{ factor.unit }}）
                </span>
              </li>
            </ul>
          </div>

          <div v-if="item.missing_data.length" class="mt-3">
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">缺失数据</p>
            <p class="text-[12px]">{{ item.missing_data.join('、') }}</p>
          </div>

          <div v-if="item.limitations.length" class="mt-2">
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">评估局限</p>
            <ul class="mt-1 flex flex-col gap-1">
              <li v-for="line in item.limitations" :key="line" class="text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
                {{ line }}
              </li>
            </ul>
          </div>

          <div v-if="item.evidence_sources.length" class="mt-3 border-t pt-2" :style="{ borderColor: 'var(--color-border)' }">
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">医学依据</p>
            <p v-for="source in item.evidence_sources" :key="source.source_id" class="text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
              {{ source.title }}<span v-if="source.version">（{{ source.version }}）</span>
              <span v-if="source.page" :style="{ color: 'var(--color-text-tertiary)' }"> 第 {{ source.page }} 页</span>
            </p>
          </div>
        </article>
      </section>

      <section v-if="current.recommendations.length" class="glass card-pad">
        <h2 class="mb-3 text-[14px] font-semibold">个性化建议</h2>
        <div class="grid gap-3 md:grid-cols-2">
          <div v-for="item in current.recommendations" :key="item.id" class="rounded-[18px] border p-4" :style="{ borderColor: 'var(--color-border)' }">
            <div class="flex items-center justify-between">
              <span class="text-[13px] font-medium">{{ item.title }}</span>
              <span class="chip">{{ item.category }}</span>
            </div>
            <ul class="mt-2 flex flex-col gap-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
              <li v-for="action in item.action_items" :key="action">{{ action }}</li>
            </ul>
            <p v-if="item.requires_professional_consultation" class="mt-2 text-[11px]" :style="{ color: 'var(--color-warning)' }">
              该维度建议尽快由专业人员评估
            </p>
          </div>
        </div>
      </section>

      <section class="glass card-pad">
        <h2 class="mb-3 text-[14px] font-semibold">历史评估</h2>
        <ul class="flex flex-col gap-2">
          <li
            v-for="item in history"
            :key="item.id"
            class="flex cursor-pointer items-center justify-between rounded-[14px] border px-3 py-2"
            :style="{ borderColor: 'var(--color-border)' }"
            @click="openHistory(item.id)"
          >
            <span class="text-[12px]">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</span>
            <span class="flex items-center gap-2">
              <RiskBadge :level="item.overall_level" />
              <span class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">档案 v{{ item.profile_version }}</span>
            </span>
          </li>
        </ul>
      </section>
    </template>

    <section v-else class="glass card-pad">
      <EmptyState
        title="还没有可用的评估"
        description="先在智能助手里完成一次信息采集，或补齐档案后点击右上角评估"
        action="去智能助手"
        @action="$router.push('/chat')"
      />
    </section>
  </div>
</template>
