<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

import { chatApi } from '@/api'
import { streamMessage, streamResume } from '@/api/stream'
import type { ChatMessage, ConfirmationPayload, Conversation } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
const conversations = ref<Conversation[]>([])
const activeId = ref('')
const messages = ref<ChatMessage[]>([])
const input = ref('')
const sending = ref(false)
const progress = ref('')
const streamingText = ref('')
const confirmation = ref<ConfirmationPayload | null>(null)
const feedback = ref('')
const feedbackOpen = ref(false)
const scroller = ref<HTMLDivElement | null>(null)

const activeTitle = computed(() => conversations.value.find((item) => item.id === activeId.value)?.title || '新的健康对话')
const canSend = computed(() => input.value.trim().length > 0 && !sending.value)

async function scrollToBottom() {
  await nextTick()
  scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: 'smooth' })
}

async function loadConversations() {
  conversations.value = await chatApi.list()
  if (!activeId.value && conversations.value.length) {
    await openConversation(conversations.value[0].id)
  }
}

async function openConversation(id: string) {
  activeId.value = id
  confirmation.value = null
  messages.value = await chatApi.messages(id)
  await scrollToBottom()
}

async function newConversation() {
  const created = await chatApi.create()
  activeId.value = created.id
  messages.value = []
  confirmation.value = null
  await loadConversations()
}

function handleEvent(event: string, data: Record<string, unknown>) {
  if (event === 'node_progress') {
    progress.value = String(data.message || '正在处理')
  } else if (event === 'token') {
    streamingText.value += String(data.content || '')
    scrollToBottom()
  } else if (event === 'confirmation_required') {
    confirmation.value = data as unknown as ConfirmationPayload
    feedbackOpen.value = false
    feedback.value = ''
    scrollToBottom()
  } else if (event === 'run_error') {
    toast.error(String(data.message || '执行失败'))
  }
}

async function refreshMessages() {
  if (!activeId.value) return
  messages.value = await chatApi.messages(activeId.value)
  await loadConversations()
  await scrollToBottom()
}

async function send() {
  if (!canSend.value) return
  if (!activeId.value) await newConversation()
  const content = input.value.trim()
  input.value = ''
  sending.value = true
  progress.value = '正在连接'
  streamingText.value = ''
  messages.value.push({
    id: `local-${Date.now()}`,
    role: 'user',
    content,
    message_type: 'text',
    meta: {},
    created_at: new Date().toISOString(),
  })
  await scrollToBottom()

  try {
    await streamMessage(activeId.value, content, handleEvent)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '发送失败')
  } finally {
    sending.value = false
    progress.value = ''
    streamingText.value = ''
    await refreshMessages()
  }
}

async function resume(decision: 'approve' | 'modify' | 'reject') {
  if (!confirmation.value) return
  const target = confirmation.value
  if (decision === 'modify' && !feedback.value.trim()) {
    feedbackOpen.value = true
    return
  }

  sending.value = true
  progress.value = '正在恢复工作流'
  try {
    await streamResume(
      target.run_id,
      {
        approval_type: target.approval_type,
        decision,
        business_id: target.plan_id,
        version_id: target.plan_version_id,
        feedback: decision === 'modify' ? feedback.value : null,
      },
      handleEvent,
    )
    if (decision === 'approve' || decision === 'reject') confirmation.value = null
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '确认失败')
  } finally {
    sending.value = false
    progress.value = ''
    streamingText.value = ''
    await refreshMessages()
  }
}

function sourcesOf(item: ChatMessage): string[] {
  const sources = item.meta?.sources
  if (!Array.isArray(sources)) return []
  return sources.map((source) => String((source as Record<string, unknown>).title || '')).filter(Boolean)
}

function summaryLines(): string[] {
  const summary = confirmation.value?.summary || {}
  if (confirmation.value?.approval_type === 'profile') {
    const lines = [
      `年龄 ${summary.age ?? '未提供'}`,
      `性别 ${summary.sex === 'male' ? '男' : summary.sex === 'female' ? '女' : '未提供'}`,
      `BMI ${summary.bmi ?? '未计算'}`,
    ]
    if (summary.systolic_bp) lines.push(`血压 ${summary.systolic_bp}/${summary.diastolic_bp} mmHg`)
    const missing = (summary.missing_fields as string[]) || []
    if (missing.length) lines.push(`仍缺少 ${missing.join('、')}`)
    return lines
  }
  return [
    `计划 ${summary.title ?? ''}`,
    `周期 ${summary.duration_days ?? ''} 天，共 ${summary.task_count ?? 0} 项任务`,
    `目标 ${summary.goal ?? ''}`,
  ]
}

onMounted(async () => {
  await loadConversations()
  if (!conversations.value.length) await newConversation()
})
</script>

<template>
  <div class="grid h-[calc(100vh-136px)] gap-4 md:grid-cols-[230px_1fr]">
    <aside class="glass hidden flex-col p-3 md:flex">
      <button class="btn btn-primary mb-3 w-full" @click="newConversation">新建对话</button>
      <div class="scroll-thin flex-1 overflow-y-auto">
        <button
          v-for="item in conversations"
          :key="item.id"
          class="mb-1 w-full rounded-[14px] px-3 py-2 text-left text-[12px]"
          :style="{
            background: item.id === activeId ? 'rgba(23,25,29,0.06)' : 'transparent',
            color: item.id === activeId ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
          }"
          @click="openConversation(item.id)"
        >
          <p class="truncate font-medium">{{ item.title }}</p>
          <p class="truncate text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            {{ item.last_message || '暂无消息' }}
          </p>
        </button>
      </div>
    </aside>

    <section class="glass-strong flex min-h-0 flex-col">
      <header class="flex items-center justify-between border-b px-5 py-3" :style="{ borderColor: 'var(--color-border)' }">
        <div>
          <p class="text-[13px] font-medium">{{ activeTitle }}</p>
          <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
            紧急症状会被优先识别，普通建议不会覆盖紧急提示
          </p>
        </div>
        <span v-if="progress" class="chip level-unknown">{{ progress }}</span>
      </header>

      <div ref="scroller" class="scroll-thin flex-1 space-y-4 overflow-y-auto px-5 py-5">
        <EmptyState
          v-if="!messages.length && !streamingText"
          title="描述你的基本情况"
          description="例如：我今年 39 岁，男，身高 175，体重 88 公斤，血压 150/95，每周运动 1 天"
        />

        <div v-for="item in messages" :key="item.id" class="flex" :class="item.role === 'user' ? 'justify-end' : 'justify-start'">
          <div
            class="max-w-[76%] whitespace-pre-wrap rounded-[18px] px-4 py-3 text-[13px] leading-relaxed"
            :style="
              item.role === 'user'
                ? { background: 'var(--color-primary)', color: 'var(--color-bg)' }
                : {
                    background: 'var(--color-surface-glass)',
                    border: `1px solid ${item.message_type === 'emergency' ? 'rgba(217,67,67,0.45)' : 'var(--color-border)'}`,
                  }
            "
          >
            {{ item.content }}
            <div v-if="sourcesOf(item).length" class="mt-2 border-t pt-2 text-[11px]" :style="{ borderColor: 'var(--color-border)', color: 'var(--color-text-tertiary)' }">
              依据：{{ sourcesOf(item).join('、') }}
            </div>
          </div>
        </div>

        <div v-if="streamingText" class="flex justify-start">
          <div class="max-w-[76%] whitespace-pre-wrap rounded-[18px] px-4 py-3 text-[13px] leading-relaxed" :style="{ background: 'var(--color-surface-glass)', border: '1px solid var(--color-border)' }">
            {{ streamingText }}
          </div>
        </div>

        <div v-if="confirmation" class="glass-strong p-4">
          <p class="text-[13px] font-medium">{{ confirmation.message }}</p>
          <ul class="mt-2 flex flex-col gap-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
            <li v-for="line in summaryLines()" :key="line">{{ line }}</li>
          </ul>

          <textarea
            v-if="feedbackOpen"
            v-model="feedback"
            class="field mt-3 h-20 resize-none"
            placeholder="说明需要调整的地方"
          />

          <div class="mt-3 flex flex-wrap gap-2">
            <button class="btn btn-primary" :disabled="sending" @click="resume('approve')">
              {{ confirmation.approval_type === 'profile' ? '信息正确，继续' : '确认启用计划' }}
            </button>
            <button class="btn btn-ghost" :disabled="sending" @click="feedbackOpen ? resume('modify') : (feedbackOpen = true)">
              {{ confirmation.approval_type === 'profile' ? '需要补充' : '要求修改' }}
            </button>
            <button class="btn btn-danger" :disabled="sending" @click="resume('reject')">放弃</button>
          </div>
        </div>
      </div>

      <footer class="border-t px-4 py-3" :style="{ borderColor: 'var(--color-border)' }">
        <div class="flex items-end gap-2">
          <textarea
            v-model="input"
            rows="1"
            class="field max-h-[120px] resize-none"
            placeholder="输入健康描述或问题，Enter 发送，Shift + Enter 换行"
            :disabled="sending"
            @keydown.enter.exact.prevent="send"
          />
          <button class="btn btn-primary" :disabled="!canSend" @click="send">
            {{ sending ? '处理中' : '发送' }}
          </button>
        </div>
      </footer>
    </section>
  </div>
</template>
