<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { consentApi, profileApi, reportApi } from '@/api'
import { tokens } from '@/api/client'
import type { ConsentRecord, FileItem, Profile, ReportSummary } from '@/api/types'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
const profile = ref<Profile | null>(null)
const reports = ref<ReportSummary[]>([])
const files = ref<FileItem[]>([])
const consents = ref<ConsentRecord[]>([])
const busy = ref(false)
const uploading = ref(false)
const downloading = ref('')

const consentOptions = [
  { type: 'health_data', label: '健康数据处理', desc: '保存并使用健康档案与指标记录生成评估' },
  { type: 'ai_analysis', label: 'AI 辅助分析', desc: '把必要的健康描述发送给模型生成建议，不发送账号与令牌' },
]

const form = ref({
  birth_date: '',
  sex: '',
  height_cm: '',
  weight_kg: '',
  waist_cm: '',
  occupation: '',
  sleep_hours: '',
  exercise_days: '',
  sedentary_hours: '',
  smoking_status: '',
  drinking_frequency: '',
})

const history = ref({ history_type: 'personal', condition_code: 'hypertension', description: '' })

const conditions = [
  { code: 'hypertension', label: '高血压' },
  { code: 'diabetes', label: '糖尿病' },
  { code: 'dyslipidemia', label: '血脂异常' },
  { code: 'chd', label: '冠心病' },
  { code: 'stroke', label: '脑卒中' },
  { code: 'cvd', label: '心血管疾病' },
]

async function load() {
  const [data, reportList, fileList, consentList] = await Promise.all([
    profileApi.get(),
    reportApi.list(),
    profileApi.files(),
    consentApi.list(),
  ])
  profile.value = data
  reports.value = reportList
  files.value = fileList
  consents.value = consentList
  const lifestyle = data.lifestyle || {}
  form.value = {
    birth_date: data.birth_date || '',
    sex: data.sex || '',
    height_cm: data.height_cm ? String(data.height_cm) : '',
    weight_kg: data.weight_kg ? String(data.weight_kg) : '',
    waist_cm: data.waist_cm ? String(data.waist_cm) : '',
    occupation: data.occupation || '',
    sleep_hours: lifestyle.sleep_hours ? String(lifestyle.sleep_hours) : '',
    exercise_days: lifestyle.exercise_days !== undefined && lifestyle.exercise_days !== null ? String(lifestyle.exercise_days) : '',
    sedentary_hours: lifestyle.sedentary_hours ? String(lifestyle.sedentary_hours) : '',
    smoking_status: (lifestyle.smoking_status as string) || '',
    drinking_frequency: (lifestyle.drinking_frequency as string) || '',
  }
}

async function save() {
  busy.value = true
  try {
    const num = (value: string) => (value.trim() === '' ? null : Number(value))
    const lifestyle: Record<string, unknown> = {}
    if (form.value.sleep_hours) lifestyle.sleep_hours = Number(form.value.sleep_hours)
    if (form.value.exercise_days) lifestyle.exercise_days = Number(form.value.exercise_days)
    if (form.value.sedentary_hours) lifestyle.sedentary_hours = Number(form.value.sedentary_hours)
    if (form.value.smoking_status) lifestyle.smoking_status = form.value.smoking_status
    if (form.value.drinking_frequency) lifestyle.drinking_frequency = form.value.drinking_frequency

    profile.value = await profileApi.patch({
      birth_date: form.value.birth_date || null,
      sex: form.value.sex || null,
      height_cm: num(form.value.height_cm),
      weight_kg: num(form.value.weight_kg),
      waist_cm: num(form.value.waist_cm),
      occupation: form.value.occupation || null,
      lifestyle,
    })
    toast.success('档案已更新')
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    busy.value = false
  }
}

async function addHistory() {
  try {
    await profileApi.addHistory({
      history_type: history.value.history_type,
      condition_code: history.value.condition_code,
      description: history.value.description || undefined,
    })
    history.value.description = ''
    toast.success('已记录')
    await load()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '记录失败')
  }
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const result = await profileApi.upload(file)
    toast.success(result.parse_status === 'pending' ? '文件已保存，解析尚未启用' : '文件已上传')
    files.value = await profileApi.files()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '上传失败')
  } finally {
    uploading.value = false
    input.value = ''
  }
}

function sizeText(size: number) {
  return size > 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)} MB` : `${Math.round(size / 1024)} KB`
}

async function downloadFile(item: FileItem) {
  downloading.value = item.id
  try {
    // 下载接口要鉴权，不能直接用 a 标签跳转
    const response = await fetch(`/api/v1/files/${item.id}/download`, {
      headers: { Authorization: `Bearer ${tokens.access}` },
    })
    if (!response.ok) throw new Error('下载失败')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = item.original_filename
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '下载失败')
  } finally {
    downloading.value = ''
  }
}

async function setConsent(type: string, granted: boolean) {
  try {
    await consentApi.set(type, granted)
    consents.value = await consentApi.list()
    toast.success(granted ? '已授权' : '已撤回授权')
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '操作失败')
  }
}

function consentStatus(type: string) {
  const latest = consents.value.find((item) => item.consent_type === type)
  return latest ? latest.consent_status : 'none'
}

onMounted(load)
</script>

<template>
  <div class="flex flex-col gap-4">
    <section class="glass card-pad">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 class="text-[20px] font-semibold">个人中心</h1>
          <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
            档案版本 v{{ profile?.profile_version ?? '-' }}，任何字段修改都会递增版本，历史评估保留当时的快照
          </p>
        </div>
        <div class="flex items-center gap-2">
          <span v-if="profile?.bmi" class="chip">BMI {{ profile.bmi }}</span>
          <span v-if="profile?.age" class="chip">{{ profile.age }} 岁</span>
        </div>
      </div>
    </section>

    <div class="grid gap-4 xl:grid-cols-2">
      <section class="glass card-pad">
        <h2 class="mb-3 text-[14px] font-semibold">基础信息</h2>
        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="label" for="birth">出生日期</label>
            <input id="birth" v-model="form.birth_date" class="field" type="date" />
          </div>
          <div>
            <label class="label" for="sex">性别</label>
            <select id="sex" v-model="form.sex" class="field">
              <option value="">未填写</option>
              <option value="male">男</option>
              <option value="female">女</option>
            </select>
          </div>
          <div>
            <label class="label" for="height">身高 cm</label>
            <input id="height" v-model="form.height_cm" class="field" inputmode="decimal" />
          </div>
          <div>
            <label class="label" for="weight">体重 kg</label>
            <input id="weight" v-model="form.weight_kg" class="field" inputmode="decimal" />
          </div>
          <div>
            <label class="label" for="waist">腰围 cm</label>
            <input id="waist" v-model="form.waist_cm" class="field" inputmode="decimal" />
          </div>
          <div>
            <label class="label" for="job">职业</label>
            <input id="job" v-model="form.occupation" class="field" />
          </div>
        </div>

        <h2 class="mb-3 mt-5 text-[14px] font-semibold">生活方式</h2>
        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="label" for="sleep">平均睡眠时长 h</label>
            <input id="sleep" v-model="form.sleep_hours" class="field" inputmode="decimal" />
          </div>
          <div>
            <label class="label" for="exercise">每周运动天数</label>
            <input id="exercise" v-model="form.exercise_days" class="field" inputmode="numeric" />
          </div>
          <div>
            <label class="label" for="sedentary">每日久坐时长 h</label>
            <input id="sedentary" v-model="form.sedentary_hours" class="field" inputmode="decimal" />
          </div>
          <div>
            <label class="label" for="smoke">吸烟情况</label>
            <select id="smoke" v-model="form.smoking_status" class="field">
              <option value="">未填写</option>
              <option value="never">从不</option>
              <option value="former">已戒</option>
              <option value="current">当前吸烟</option>
            </select>
          </div>
          <div>
            <label class="label" for="drink">饮酒频率</label>
            <select id="drink" v-model="form.drinking_frequency" class="field">
              <option value="">未填写</option>
              <option value="never">不饮酒</option>
              <option value="occasional">偶尔</option>
              <option value="daily">每日</option>
            </select>
          </div>
        </div>

        <button class="btn btn-primary mt-4" :disabled="busy" @click="save">{{ busy ? '保存中' : '保存档案' }}</button>
      </section>

      <div class="flex flex-col gap-4">
        <section class="glass card-pad">
          <h2 class="mb-3 text-[14px] font-semibold">既往史与家族史</h2>
          <div class="grid gap-2 sm:grid-cols-[110px_1fr]">
            <select v-model="history.history_type" class="field">
              <option value="personal">本人</option>
              <option value="family">家族</option>
            </select>
            <select v-model="history.condition_code" class="field">
              <option v-for="item in conditions" :key="item.code" :value="item.code">{{ item.label }}</option>
            </select>
          </div>
          <input v-model="history.description" class="field mt-2" placeholder="补充说明，可留空" />
          <button class="btn btn-ghost mt-2" @click="addHistory">添加记录</button>

          <ul class="mt-3 flex flex-col gap-1">
            <li v-for="item in profile?.medical_histories || []" :key="item.id" class="text-[12px]">
              {{ item.history_type === 'family' ? '家族' : '本人' }} ·
              {{ conditions.find((c) => c.code === item.condition_code)?.label || item.condition_code }}
              <span v-if="item.description" :style="{ color: 'var(--color-text-tertiary)' }"> · {{ item.description }}</span>
            </li>
          </ul>
        </section>

        <section class="glass card-pad">
          <div class="flex items-center justify-between">
            <h2 class="text-[14px] font-semibold">历史报告</h2>
            <span class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">共 {{ reports.length }} 份</span>
          </div>
          <ul class="mt-2 flex flex-col gap-1">
            <li v-for="item in reports" :key="item.id">
              <RouterLink :to="`/reports/${item.id}`" class="flex items-center justify-between text-[12px]">
                <span>{{ item.title }}</span>
                <span :style="{ color: 'var(--color-text-tertiary)' }">{{ new Date(item.created_at).toLocaleDateString('zh-CN') }}</span>
              </RouterLink>
            </li>
          </ul>
          <p v-if="!reports.length" class="mt-2 text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">暂无报告</p>
        </section>

        <section class="glass card-pad">
          <h2 class="mb-2 text-[14px] font-semibold">体检资料</h2>
          <input class="field" type="file" accept=".pdf,.jpg,.jpeg,.png" :disabled="uploading" @change="upload" />
          <p class="mt-2 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            支持 PDF、JPG、PNG，单个不超过 10MB。当前版本只保存文件，文字识别与字段提取尚未开放，上传结果不会被自动写入档案。
          </p>
          <ul class="mt-2 flex flex-col gap-1">
            <li v-for="item in files" :key="item.id" class="flex items-center justify-between gap-2 text-[12px]">
              <span class="truncate">{{ item.original_filename }}</span>
              <span class="flex shrink-0 items-center gap-2">
                <span :style="{ color: 'var(--color-text-tertiary)' }">{{ sizeText(item.file_size) }} · {{ item.parse_status }}</span>
                <button class="btn btn-ghost !px-2 !py-1 text-[11px]" :disabled="downloading === item.id" @click="downloadFile(item)">
                  {{ downloading === item.id ? '下载中' : '下载' }}
                </button>
              </span>
            </li>
          </ul>
        </section>
        <section class="glass card-pad">
          <h2 class="mb-2 text-[14px] font-semibold">隐私与授权</h2>
          <ul class="flex flex-col gap-2">
            <li
              v-for="item in consentOptions"
              :key="item.type"
              class="flex items-start justify-between gap-3 rounded-[14px] border px-3 py-2"
              :style="{ borderColor: 'var(--color-border)' }"
            >
              <div class="min-w-0">
                <p class="text-[12px] font-medium">
                  {{ item.label }}
                  <span class="chip ml-1" :class="consentStatus(item.type) === 'granted' ? 'level-low' : 'level-unknown'">
                    {{ consentStatus(item.type) === 'granted' ? '已授权' : consentStatus(item.type) === 'revoked' ? '已撤回' : '未授权' }}
                  </span>
                </p>
                <p class="mt-1 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">{{ item.desc }}</p>
              </div>
              <button
                class="btn btn-ghost shrink-0 !px-2 !py-1 text-[11px]"
                @click="setConsent(item.type, consentStatus(item.type) !== 'granted')"
              >
                {{ consentStatus(item.type) === 'granted' ? '撤回' : '授权' }}
              </button>
            </li>
          </ul>
          <p class="mt-2 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            授权与撤回都会留记录，撤回不影响历史报告的查阅
          </p>
        </section>
      </div>
    </div>

    <section class="glass card-pad text-[11px] leading-relaxed" :style="{ color: 'var(--color-text-tertiary)' }">
      <p>数据用途：仅用于本平台的健康评估与管理，评估结果不构成诊断、处方或治疗建议。</p>
      <p>外部模型只接收当前任务所需的健康描述，不发送账号、令牌与完整报告原件。演示环境使用模拟数据。</p>
    </section>
  </div>
</template>
