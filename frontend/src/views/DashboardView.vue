<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'

import { assessmentApi, planApi, trackingApi } from '@/api'
import type { Assessment, Plan, Task, Trend } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import RiskBadge from '@/components/RiskBadge.vue'
// echarts 这一个包 466 kB，比其余所有页面加起来还大。静态引入的话新用户一进首页
// 就要下它，哪怕一条指标都没有、只显示「还没有指标记录」。改成按需加载：
// 模板里本来就是 v-if 有数据才渲染，没数据时这个 chunk 根本不会被请求
const TrendChart = defineAsyncComponent(() => import('@/components/TrendChart.vue'))
import { useAuthStore } from '@/stores/auth'
import { useReminderStore } from '@/stores/reminders'
import { useToastStore } from '@/stores/toast'
import { useToday } from '@/utils/today'

const auth = useAuthStore()
const toast = useToastStore()
const reminderStore = useReminderStore()
const loading = ref(true)
const checking = ref('')
const assessment = ref<Assessment | null>(null)
const plan = ref<Plan | null>(null)
const trends = ref<Trend[]>([])
const activeMetric = ref('')

const dimensionNames: Record<string, string> = {
  cardiovascular: '心血管',
  metabolic: '代谢',
  sleep: '睡眠与疲劳',
  mental: '心理',
  lifestyle: '生活方式',
}

const emptyDimensions = computed(() => !assessment.value || assessment.value.dimensions.length === 0)
const selectedTrend = computed(() => trends.value.find((item) => item.metric_code === activeMetric.value) || trends.value[0])
const unreadThree = computed(() => reminderStore.items.filter((item) => !item.read_at).slice(0, 3))
const today = useToday()
const todayTasks = computed(() => {
  if (!plan.value) return []
  return plan.value.tasks.filter((task) => task.scheduled_date === today.value)
})

async function load() {
  loading.value = true
  try {
    const [latest, plans, trendList] = await Promise.all([
      assessmentApi.latest(),
      planApi.list(),
      trackingApi.trends(['systolic_bp', 'weight_kg', 'sleep_hours'], 30).catch(() => []),
      reminderStore.load().catch(() => undefined),
    ])
    assessment.value = latest
    trends.value = trendList
    activeMetric.value = trendList.length ? trendList[0].metric_code : ''
    const active = plans.find((item) => item.status === 'active') || plans[0]
    plan.value = active ? await planApi.detail(active.id) : null
  } catch (error) {
    // 首屏几路请求里只要有没兜住的，整个 load 就会挂在这里。
    // 不提示的话页面只剩几个空状态，看着像「我什么都没有」，其实是没读出来
    toast.error(error instanceof Error ? error.message : '读取首页数据失败')
  } finally {
    loading.value = false
  }
}

async function markRead(id: string) {
  try {
    await reminderStore.read(id)
  } catch {
    /* 标记失败不挡住页面，下次进入还会重新拉取 */
  }
}

async function checkin(task: Task) {
  checking.value = task.id
  try {
    await planApi.checkin(task.id, 'completed')
    toast.success('已记一次完成')
    await load()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '打卡失败')
  } finally {
    checking.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="flex flex-col gap-4">
    <section class="glass card-pad">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p class="text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">健康概览</p>
          <h1 class="mt-1 text-[24px] font-semibold leading-tight">
            {{ auth.user?.username || '你好' }}，今天先完成能记录的部分
          </h1>
          <p class="mt-2 max-w-[520px] text-[12px] leading-relaxed" :style="{ color: 'var(--color-text-secondary)' }">
            平台只展示已有数据得出的结论。没有测量记录的指标不会用默认值替代，需要补充时会明确标注。
          </p>
        </div>
        <div v-if="assessment" class="flex flex-col items-end gap-2">
          <span class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">最近一次评估</span>
          <RiskBadge :level="assessment.overall_level" />
          <span class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            {{ new Date(assessment.created_at).toLocaleString('zh-CN') }}
          </span>
        </div>
        <div v-else class="flex flex-col items-end gap-2">
          <span class="chip level-unknown">尚未评估</span>
          <RouterLink to="/chat" class="btn btn-primary">开始评估</RouterLink>
        </div>
      </div>
    </section>

    <div class="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
      <section class="glass card-pad">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-[14px] font-semibold">五维风险提示</h2>
          <RouterLink to="/assessment" class="text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">查看依据</RouterLink>
        </div>
        <EmptyState v-if="emptyDimensions" title="还没有评估结果" description="通过智能助手描述基本情况后生成五维评估" action="去评估" @action="$router.push('/chat')" />
        <div v-else class="grid gap-3 sm:grid-cols-2">
          <div
            v-for="item in assessment?.dimensions"
            :key="item.dimension"
            class="rounded-[18px] border p-4"
            :style="{ borderColor: 'var(--color-border)' }"
          >
            <div class="flex items-center justify-between">
              <span class="text-[13px] font-medium">{{ dimensionNames[item.dimension] || item.dimension }}</span>
              <RiskBadge :level="item.level" />
            </div>
            <p class="mt-2 line-clamp-2 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
              {{ item.risk_factors[0]?.message || item.explanation || '当前数据未触发重点关注规则' }}
            </p>
            <p v-if="item.missing_data.length" class="mt-1 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              缺少：{{ item.missing_data.join('、') }}
            </p>
          </div>
        </div>
      </section>

      <div class="flex flex-col gap-4">
        <section class="glass card-pad">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-[14px] font-semibold">今日任务</h2>
            <RouterLink to="/plans" class="text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">计划</RouterLink>
          </div>
          <EmptyState v-if="!todayTasks.length" title="今天没有待办任务" description="计划生效后每日任务会出现在这里" />
          <ul v-else class="flex flex-col gap-2">
            <li
              v-for="task in todayTasks"
              :key="task.id"
              class="flex items-start justify-between gap-3 rounded-[14px] border px-3 py-2"
              :style="{ borderColor: 'var(--color-border)' }"
            >
              <div class="min-w-0">
                <p class="truncate text-[12px] font-medium">{{ task.title }}</p>
                <p class="truncate text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">{{ task.completion_criteria }}</p>
              </div>
              <div class="flex shrink-0 items-center gap-2">
                <span class="chip" :class="task.checkin_status === 'completed' ? 'level-low' : 'level-unknown'">
                  {{ task.checkin_status === 'completed' ? '已完成' : '待完成' }}
                </span>
                <button
                  v-if="plan?.status === 'active' && task.checkin_status !== 'completed'"
                  class="btn btn-primary !px-3 !py-1 text-[11px]"
                  :disabled="checking === task.id"
                  @click="checkin(task)"
                >
                  完成
                </button>
              </div>
            </li>
          </ul>
        </section>

        <section class="glass card-pad">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-[14px] font-semibold">未读提醒</h2>
            <div class="flex items-center gap-2">
              <span v-if="unreadThree.length" class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
                {{ reminderStore.unread }} 条
              </span>
              <RouterLink to="/reminders" class="text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">全部</RouterLink>
            </div>
          </div>
          <EmptyState v-if="!unreadThree.length" title="没有未读提醒" />
          <ul v-else class="flex flex-col gap-2">
            <li v-for="item in unreadThree" :key="item.id" class="flex items-start justify-between gap-2">
              <div class="min-w-0 text-[12px]">
                <p class="font-medium">{{ item.title }}</p>
                <p :style="{ color: 'var(--color-text-secondary)' }">{{ item.content }}</p>
              </div>
              <button class="btn btn-ghost shrink-0 !px-2 !py-1 text-[11px]" @click="markRead(item.id)">已读</button>
            </li>
          </ul>
        </section>
      </div>
    </div>

    <section class="glass card-pad">
      <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 class="text-[14px] font-semibold">指标趋势</h2>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="item in trends"
            :key="item.metric_code"
            class="chip"
            :class="selectedTrend?.metric_code === item.metric_code ? 'level-low' : ''"
            @click="activeMetric = item.metric_code"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
      <!-- 外层留出 260px：图表按需加载的那一瞬间组件还没挂上，没有这层会看到布局塌一下 -->
      <div v-if="selectedTrend && selectedTrend.points.length" class="min-h-[260px]">
        <TrendChart
          :points="selectedTrend.points"
          :label="selectedTrend.label"
          :unit="selectedTrend.unit"
        />
      </div>
      <EmptyState v-else title="还没有指标记录" description="在指标趋势页录入血压、体重或睡眠时长后生成曲线" action="录入指标" @action="$router.push('/trends')" />
    </section>
  </div>
</template>
