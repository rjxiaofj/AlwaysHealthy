<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { trackingApi } from '@/api'
import type { Trend } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import TrendChart from '@/components/TrendChart.vue'
import { useToastStore } from '@/stores/toast'

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

const form = ref({
  metric_code: 'systolic_bp',
  value: '',
  measured_at: new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16),
  fasting: true,
})

const selected = computed(() => trends.value.find((item) => item.metric_code === active.value) || trends.value[0])
const currentUnit = computed(() => metrics.find((item) => item.code === form.value.metric_code)?.unit || '')

async function load() {
  const codes = metrics.map((item) => item.code)
  trends.value = await trackingApi.trends(codes, days.value)
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
  busy.value = true
  try {
    await trackingApi.addMetric(form.value.metric_code, value, new Date(form.value.measured_at).toISOString(), {
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

    <div class="grid gap-4 xl:grid-cols-[1.4fr_0.6fr]">
      <section class="glass card-pad">
        <div class="mb-3 flex flex-wrap gap-2">
          <button
            v-for="item in trends"
            :key="item.metric_code"
            class="chip"
            :class="selected?.metric_code === item.metric_code ? 'level-low' : ''"
            @click="active = item.metric_code"
          >
            {{ item.label }}
          </button>
        </div>
        <TrendChart
          v-if="selected && selected.points.length"
          :points="selected.points"
          :label="selected.label"
          :unit="selected.unit"
        />
        <EmptyState v-else title="没有该指标的记录" description="在右侧录入一次测量后会生成曲线" />

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
    </div>
  </div>
</template>
