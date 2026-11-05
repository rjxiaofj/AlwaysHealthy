<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { consentApi, profileApi, reportApi } from '@/api'
import { tokens } from '@/api/client'
import type { ConsentRecord, EmergencyEvent, ExtractedDocument, FileItem, Profile, ReportSummary } from '@/api/types'
import { useToastStore } from '@/stores/toast'
import { buildProfilePatch, formFromProfile } from '@/views/profileLogic'

const toast = useToastStore()
const profile = ref<Profile | null>(null)
const reports = ref<ReportSummary[]>([])
const files = ref<FileItem[]>([])
const consents = ref<ConsentRecord[]>([])
const emergencies = ref<EmergencyEvent[]>([])
const busy = ref(false)
const uploading = ref(false)
const downloading = ref('')
const extracted = ref<ExtractedDocument | null>(null)
const extracting = ref('')
const selectedCodes = ref<string[]>([])
const applying = ref(false)

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
  const [data, reportList, fileList, consentList, emergencyList] = await Promise.all([
    profileApi.get(),
    reportApi.list(),
    profileApi.files(),
    consentApi.list(),
    profileApi.emergencyEvents().catch(() => []),
  ])
  profile.value = data
  reports.value = reportList
  files.value = fileList
  consents.value = consentList
  emergencies.value = emergencyList
  form.value = formFromProfile(data)
}

async function save() {
  busy.value = true
  try {
    profile.value = await profileApi.patch(buildProfilePatch(form.value))
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
    const hint =
      result.parse_status === 'parsed'
        ? '文件已上传并完成识别'
        : result.parse_status === 'unsupported'
          ? '文件已保存，这份资料没有可读取的文字层'
          : '文件已保存，解析失败'
    toast.success(hint)
    files.value = await profileApi.files()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '上传失败')
  } finally {
    uploading.value = false
    input.value = ''
  }
}

async function openExtracted(item: FileItem) {
  if (extracted.value?.id === item.id) {
    extracted.value = null
    selectedCodes.value = []
    return
  }
  extracting.value = item.id
  try {
    const detail = await profileApi.extracted(item.id)
    extracted.value = detail
    selectedCodes.value = detail.fields.map((field) => field.metric_code)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '读取识别结果失败')
  } finally {
    extracting.value = ''
  }
}

function toggleCode(code: string) {
  const index = selectedCodes.value.indexOf(code)
  if (index >= 0) selectedCodes.value.splice(index, 1)
  else selectedCodes.value.push(code)
}

async function applyExtracted() {
  if (!extracted.value || selectedCodes.value.length === 0) return
  applying.value = true
  try {
    const result = await profileApi.applyExtracted(extracted.value.id, selectedCodes.value)
    toast.success(result.applied > 0 ? `已写入 ${result.applied} 项指标` : '这些指标已经写入过，未重复记录')
    extracted.value = null
    selectedCodes.value = []
    await load()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '写入失败')
  } finally {
    applying.value = false
  }
}

function sizeText(size: number) {
  return size > 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)} MB` : `${Math.round(size / 1024)} KB`
}

const PARSE_LABELS: Record<string, string> = {
  parsed: '已识别',
  unsupported: '无法识别',
  failed: '解析失败',
  pending: '待解析',
}

function parseText(status: string) {
  return PARSE_LABELS[status] ?? status
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

        <section v-if="emergencies.length" class="glass card-pad">
          <div class="flex items-center justify-between">
            <h2 class="text-[14px] font-semibold">紧急提示记录</h2>
            <span class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">共 {{ emergencies.length }} 次</span>
          </div>
          <ul class="mt-2 flex flex-col gap-2">
            <li
              v-for="item in emergencies"
              :key="item.id"
              class="rounded-[14px] border px-3 py-2"
              :style="{ borderColor: 'var(--color-border)' }"
            >
              <p class="text-[12px]">{{ item.trigger_reason || '触发了紧急提示' }}</p>
              <p class="mt-1 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
                {{ new Date(item.triggered_at).toLocaleString('zh-CN') }} · {{ item.urgency }} · 当时已提示优先就医
              </p>
            </li>
          </ul>
          <p class="mt-2 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            这里只记录对话中触发过的紧急提示，不代表诊断结论，也不改变当时的处置建议
          </p>
        </section>

        <section class="glass card-pad">
          <h2 class="mb-2 text-[14px] font-semibold">体检资料</h2>
          <input class="field" type="file" accept=".pdf,.jpg,.jpeg,.png" :disabled="uploading" @change="upload" />
          <p class="mt-2 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            支持 PDF、JPG、PNG，单个不超过 10MB。PDF 会尝试读取文字层并列出识别到的指标，图片与扫描件只保存原件。识别结果需要你逐项确认后才会写入指标记录。
          </p>
          <ul class="mt-2 flex flex-col gap-2">
            <li v-for="item in files" :key="item.id" class="flex flex-col gap-1">
              <div class="flex items-center justify-between gap-2 text-[12px]">
                <span class="truncate">{{ item.original_filename }}</span>
                <span class="flex shrink-0 items-center gap-2">
                  <span :style="{ color: 'var(--color-text-tertiary)' }">{{ sizeText(item.file_size) }} · {{ parseText(item.parse_status) }}</span>
                  <button
                    v-if="item.parse_status === 'parsed'"
                    class="btn btn-ghost !px-2 !py-1 text-[11px]"
                    :disabled="extracting === item.id"
                    @click="openExtracted(item)"
                  >
                    {{ extracted?.id === item.id ? '收起' : extracting === item.id ? '读取中' : '识别结果' }}
                  </button>
                  <button class="btn btn-ghost !px-2 !py-1 text-[11px]" :disabled="downloading === item.id" @click="downloadFile(item)">
                    {{ downloading === item.id ? '下载中' : '下载' }}
                  </button>
                </span>
              </div>
              <div
                v-if="extracted?.id === item.id"
                class="rounded-[14px] border px-3 py-2"
                :style="{ borderColor: 'var(--color-border)' }"
              >
                <p v-if="!extracted.fields.length" class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
                  {{ extracted.parse_message }}
                </p>
                <template v-else>
                  <ul class="flex flex-col gap-1">
                    <li v-for="field in extracted.fields" :key="field.metric_code" class="flex items-center gap-2 text-[12px]">
                      <input
                        :id="`pick-${item.id}-${field.metric_code}`"
                        type="checkbox"
                        :checked="selectedCodes.includes(field.metric_code)"
                        @change="toggleCode(field.metric_code)"
                      />
                      <label :for="`pick-${item.id}-${field.metric_code}`" class="flex flex-1 cursor-pointer items-center gap-1">
                        <span>{{ field.label }}</span>
                        <span class="font-medium">{{ field.value }}</span>
                        <span :style="{ color: 'var(--color-text-tertiary)' }">{{ field.unit }}</span>
                      </label>
                      <span class="shrink-0 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">{{ field.raw }}</span>
                    </li>
                  </ul>
                  <div class="mt-2 flex items-center justify-between gap-2">
                    <span class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">{{ extracted.parse_message }}</span>
                    <button
                      class="btn btn-primary shrink-0 !px-3 !py-1 text-[11px]"
                      :disabled="applying || selectedCodes.length === 0"
                      @click="applyExtracted"
                    >
                      {{ applying ? '写入中' : `写入 ${selectedCodes.length} 项` }}
                    </button>
                  </div>
                </template>
              </div>
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
      <p>外部模型只接收当前任务所需的健康描述，不发送账号、令牌与完整报告原件。模型不可用时改用本地规则文案，评估结论不依赖模型是否可用。</p>
    </section>
  </div>
</template>
