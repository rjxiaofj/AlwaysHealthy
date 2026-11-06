<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { trackingApi } from '@/api'
import type { FeedbackRecord, Trend } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import MultiTrendChart from '@/components/MultiTrendChart.vue'
import TrendChart from '@/components/TrendChart.vue'
import { useToastStore } from '@/stores/toast'
import { localDateTimeInput } from '@/utils/datetime'

const toast = useToastStore()

const metrics = [
  { code: 'systolic_bp', label: '收缩压', unit: 'mmHg' },
  { code: 'diastolic_bp', label: '舒张压', unit: 'mmHg' },
  { code: 'weight_kg', label: '体重', unit: 'kg' },
  { code: 'sleep_hours', label: '睡眠时长', unit: 'h' },
  { code: 'fasting_glucose', label: '空腹血糖', unit: 'mmol/L' },
  { code: 'waist_cm', label: '腰围', unit: 'cm' },
  { code: 'heart_rate', label: '静息心率', unit: 'bpm' },
]

const trends = ref<Trend[]>([])
const active = ref('systolic_bp')
const days = ref(30)
const busy = ref(false)
const compareMode = ref(false)
const compared = ref<string[]>([])

const form = ref({
  metric_code: 'systolic_bp',
  value: '',
  measured_at: localDateTimeInput(),
  fasting: true,
})

const selected = computed(() => trends.value.find((item) => item.metric_code === active.value) || trends.value[0])
const currentUnit = computed(() => metrics.find((item) => item.code === form.value.metric_code)?.unit || '')
const comparedSeries = computed(() =>
  compared.value
    .map((code) => trends.value.find((item) => item.metric_code === code))
    .filter((item): item is Trend => Boolean(item)),
)

function toggleCompare(code: string) {
  const index = compared.value.indexOf(code)
  if (index >= 0) compared.value.splice(index, 1)
  else compared.value.push(code)
}

const feedback = ref({
  mood_status: '',
  fatigue_level: '',
  physical_feeling: '',
  execution_difficulty: '',
})
const feedbackBusy = ref(false)
const feedbacks = ref<FeedbackRecord[]>([])

const moodLabels: Record<string, string> = { good: '平稳', fair: '一般', low: '低落' }
const fatigueLabels: Record<string, string> = { low: '轻', medium: '中', high: '重' }

function feedbackSummary(item: FeedbackRecord) {
  const parts = []
  if (item.mood_status) parts.push(`情绪${moodLabels[item.mood_status] || item.mood_status}`)
  if (item.fatigue_level) parts.push(`疲劳${fatigueLabels[item.fatigue_level] || item.fatigue_level}`)
  if (item.physical_feeling) parts.push(item.physical_feeling)
  if (item.execution_difficulty) parts.push(`执行困难：${item.execution_difficulty}`)
  return parts.join('，')
}

function resetFeedback() {
  feedback.value = { mood_status: '', fatigue_level: '', physical_feeling: '', execution_difficulty: '' }
}

async function submitFeedback() {
  const payload: Record<string, unknown> = {}
  if (feedback.value.mood_status) payload.mood_status = feedback.value.mood_status
  if (feedback.value.fatigue_level) payload.fatigue_level = feedback.value.fatigue_level
  if (feedback.value.physical_feeling.trim()) payload.physical_feeling = feedback.value.physical_feeling.trim()
  if (feedback.value.execution_difficulty.trim()) {
    payload.execution_difficulty = feedback.value.execution_difficulty.trim()
  }
  if (!Object.keys(payload).length) {
    toast.error('至少记录一项')
    return
  }
  feedbackBusy.value = true
  try {
    await trackingApi.feedback(payload)
    toast.success('已记录，感受不会自动当作指标变化')
    resetFeedback()
    feedbacks.value = await trackingApi.feedbackList(days.value > 90 ? days.value : 90)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '记录失败')
  } finally {
    feedbackBusy.value = false
  }
}

async function load() {
  const codes = metrics.map((item) => item.code)
  try {
    const [trendList, feedbackList] = await Promise.all([
      trackingApi.trends(codes, days.value),
      trackingApi.feedbackList(days.value).catch(() => []),
    ])
    trends.value = trendList
    feedbacks.value = feedbackList
  } catch (error) {
    // 曲线读不出来时要说明白，不能只留一块「还没有指标记录」的空状态
    toast.error(error instanceof Error ? error.message : '读取指标失败')
    return
  }
  if (!trends.value.find((item) => item.metric_code === active.value) && trends.value.length) {
    active.value = trends.value[0].metric_code
  }
}

async function submit() {
  const value = Number(form.value.value)
  if (!value || Number.isNaN(value)) {
    toast.error('填写有效数值')
    return
  }
  // 时间框被清空时 new Date('') 是 Invalid Date，直接 toISOString 会抛 RangeError，
  // 用户会在提示里看到「Invalid time value」这种英文
  const measuredAt = new Date(form.value.measured_at)
  if (!form.value.measured_at || Number.isNaN(measuredAt.getTime())) {
    toast.error('选择测量时间')
    return
  }
  busy.value = true
  try {
    await trackingApi.addMetric(form.value.metric_code, value, measuredAt.toISOString(), {
      fasting: form.value.metric_code === 'fasting_glucose' ? form.value.fasting : undefined,
    })
    toast.success('已记录')
    form.value.value = ''
    await load()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '记录失败')
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="flex flex-col gap-4">
    <section class="glass card-pad">
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 class="text-[20px] font-semibold">指标趋势</h1>
          <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
            只做描述性统计，单次变化不能说明病情变化
          </p>
        </div>
        <div class="flex items-end gap-2">
          <div>
            <label class="label" for="days">观察范围</label>
            <select id="days" v-model.number="days" class="field w-[110px]" @change="load">
              <option :value="7">7 天</option>
              <option :value="30">30 天</option>
              <option :value="90">90 天</option>
            </select>
          </div>
        </div>
      </div>
    </section>

    <!-- items-start：不加的话左栏卡片会被右栏（录入表单加感受列表）撑到同样高，
         图表下面空出一大块，看着像没渲染完 -->
    <div class="grid items-start gap-4 xl:grid-cols-[1.4fr_0.6fr]">
      <section class="glass card-pad">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div class="flex flex-wrap gap-2">
            <button
              v-for="item in trends"
              :key="item.metric_code"
              class="chip"
              :class="
                compareMode
                  ? compared.includes(item.metric_code)
                    ? 'level-low'
                    : ''
                  : selected?.metric_code === item.metric_code
                    ? 'level-low'
                    : ''
              "
              @click="compareMode ? toggleCompare(item.metric_code) : (active = item.metric_code)"
            >
              {{ item.label }}
            </button>
          </div>
          <button class="chip" :class="compareMode ? 'level-low' : ''" @click="compareMode = !compareMode">
            {{ compareMode ? '对比中' : '对比' }}
          </button>
        </div>

        <div v-if="compareMode">
          <MultiTrendChart
            v-if="comparedSeries.length > 1"
            :series="comparedSeries.map((item) => ({ key: item.metric_code, label: item.label, unit: item.unit, points: item.points }))"
          />
          <EmptyState
            v-else
            title="选择至少两个指标"
            description="点上面的指标标签勾选两个以上，就能在同一张图上对比它们的趋势"
          />
          <p v-if="comparedSeries.length > 1" class="mt-2 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            横轴按测量日期对齐，同一天的测量落在同一条竖线上；没测的日期不补点。纵轴按所有选中指标的全局范围统一缩放，量纲不同的指标对比高低只作参考。
          </p>
        </div>
        <template v-else>
          <div v-if="selected && selected.points.length">
            <TrendChart :points="selected.points" :label="selected.label" :unit="selected.unit" />
          </div>
          <EmptyState v-else title="没有该指标的记录" description="在右侧录入一次测量后会生成曲线" />
        </template>

        <div v-if="selected" class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">最新</p>
            <p class="text-[16px] font-semibold">{{ selected.latest ?? '-' }} <span class="text-[11px] font-normal">{{ selected.unit }}</span></p>
          </div>
          <div>
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">平均</p>
            <p class="text-[16px] font-semibold">{{ selected.average ?? '-' }}</p>
          </div>
          <div>
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">范围</p>
            <p class="text-[14px]">{{ selected.minimum ?? '-' }} 至 {{ selected.maximum ?? '-' }}</p>
          </div>
          <div>
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">首末变化</p>
            <p class="text-[14px]" :style="{ color: selected.change && selected.change > 0 ? 'var(--color-danger)' : 'var(--color-success)' }">
              {{ selected.change === null ? '样本不足' : `${selected.change > 0 ? '+' : ''}${selected.change}` }}
            </p>
          </div>
        </div>
      </section>

      <div class="flex flex-col gap-4">
        <section class="glass card-pad">
          <h2 class="text-[14px] font-semibold">录入指标</h2>
          <div class="mt-3 flex flex-col gap-3">
            <div>
              <label class="label" for="metric">指标</label>
              <select id="metric" v-model="form.metric_code" class="field">
                <option v-for="item in metrics" :key="item.code" :value="item.code">{{ item.label }}（{{ item.unit }}）</option>
              </select>
            </div>
            <div>
              <label class="label" for="value">数值 {{ currentUnit }}</label>
              <input id="value" v-model="form.value" class="field" inputmode="decimal" placeholder="例如 126" />
            </div>
            <div>
              <label class="label" for="time">测量时间</label>
              <input id="time" v-model="form.measured_at" class="field" type="datetime-local" />
            </div>
            <label v-if="form.metric_code === 'fasting_glucose'" class="flex items-center gap-2 text-[12px]">
              <input v-model="form.fasting" type="checkbox" />
              空腹八小时以上
            </label>
            <button class="btn btn-primary" :disabled="busy" @click="submit">{{ busy ? '保存中' : '记录' }}</button>
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              血压建议静坐五分钟后测量，体重建议晨起空腹同一台秤。单位与测量条件会一起保存。
            </p>
          </div>
        </section>

        <section class="glass card-pad">
          <h2 class="text-[14px] font-semibold">身体感受</h2>
          <p class="mt-1 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            记录主观感受，不参与风险分级
          </p>
          <div class="mt-3 flex flex-col gap-3">
            <div>
              <label class="label" for="mood">情绪状态</label>
              <select id="mood" v-model="feedback.mood_status" class="field">
                <option value="">未填写</option>
                <option value="good">平稳</option>
                <option value="fair">一般</option>
                <option value="low">低落</option>
              </select>
            </div>
            <div>
              <label class="label" for="fatigue">疲劳程度</label>
              <select id="fatigue" v-model="feedback.fatigue_level" class="field">
                <option value="">未填写</option>
                <option value="low">轻</option>
                <option value="medium">中</option>
                <option value="high">重</option>
              </select>
            </div>
            <div>
              <label class="label" for="feeling">身体感受</label>
              <textarea
                id="feeling"
                v-model="feedback.physical_feeling"
                class="field h-16 resize-none"
                placeholder="例如 下午容易犯困，走两层楼有点喘"
              />
            </div>
            <div>
              <label class="label" for="difficulty">执行困难</label>
              <input id="difficulty" v-model="feedback.execution_difficulty" class="field" placeholder="例如 加班太晚没时间运动" />
            </div>
            <button class="btn btn-ghost" :disabled="feedbackBusy" @click="submitFeedback">
              {{ feedbackBusy ? '保存中' : '记录感受' }}
            </button>
          </div>
        </section>
      </div>
    </div>

    <section class="glass card-pad">
      <div class="flex items-center justify-between">
        <h2 class="text-[14px] font-semibold">最近的身体感受</h2>
        <span class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">{{ feedbacks.length }} 条</span>
      </div>
      <EmptyState
        v-if="!feedbacks.length"
        title="还没有记录"
        description="在上面的表单里写下主观感受，之后可以在这里回看"
      />
      <ul v-else class="mt-3 flex flex-col gap-2">
        <li
          v-for="item in feedbacks"
          :key="item.id"
          class="rounded-[14px] border px-3 py-2"
          :style="{ borderColor: 'var(--color-border)' }"
        >
          <p class="text-[12px]">{{ feedbackSummary(item) }}</p>
          <p class="mt-1 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            {{ new Date(item.recorded_at).toLocaleString('zh-CN') }}
          </p>
        </li>
      </ul>
      <p class="mt-2 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
        感受只作描述，不换算成指标，也不参与风险分级
      </p>
    </section>
  </div>
</template>
