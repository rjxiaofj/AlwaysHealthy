<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import type { AccountRole } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { safeRedirect } from '@/utils/redirect'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

type Mode = 'login' | 'register'

const tabs: { value: AccountRole; label: string }[] = [
  { value: 'user', label: '用户登录' },
  { value: 'admin', label: '管理员登录' },
]

const tab = ref<AccountRole>('user')
const mode = ref<Mode>('login')
const username = ref('')
const password = ref('')
const adminCode = ref('')
const error = ref('')

const isAdminTab = computed(() => tab.value === 'admin')
const heading = computed(() => {
  if (mode.value === 'register') return isAdminTab.value ? '注册管理员账号' : '注册新账号'
  return isAdminTab.value ? '管理员登录' : '登录'
})
const subheading = computed(() => {
  if (mode.value === 'register') {
    return isAdminTab.value ? '需要管理员邀请码，注册后进入管理后台' : '新账号会自动创建一份健康档案'
  }
  return isAdminTab.value ? '管理部门账号，查看服务状态与安全事件' : '使用账号继续你的健康档案'
})
const submitLabel = computed(() => {
  if (auth.pending) return '处理中'
  if (mode.value === 'register') return isAdminTab.value ? '注册管理员并进入后台' : '注册并进入'
  return isAdminTab.value ? '进入管理后台' : '登录'
})
const switchLabel = computed(() => {
  if (mode.value === 'register') return '已有账号，去登录'
  return isAdminTab.value ? '没有管理员账号？管理员注册' : '没有账号，去注册'
})
// 两种身份都常驻这一行：用 v-if 增删节点会让卡片变高，外层垂直居中会把整页上下推
const footerNote = computed(() =>
  isAdminTab.value
    ? '管理入口只管账号与平台安全，不查看任何人的健康档案。'
    : '健康数据仅本人可见，管理员也不查看任何人的健康档案。',
)

function switchTab(next: AccountRole) {
  if (tab.value === next) return
  tab.value = next
  // 换身份就回到登录态，别把上一个身份的注册表单和错误提示带过去；
  // 用户名保留，方便同名账号在两个通道之间试
  mode.value = 'login'
  error.value = ''
  password.value = ''
  adminCode.value = ''
}

function toggleMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
  adminCode.value = ''
}

async function submit() {
  error.value = ''
  if (username.value.length < 3 || password.value.length < 8) {
    error.value = '用户名至少 3 位，密码至少 8 位'
    return
  }
  if (mode.value === 'register' && isAdminTab.value && !adminCode.value.trim()) {
    error.value = '请填写管理员邀请码'
    return
  }
  try {
    if (mode.value === 'login') {
      await auth.login(username.value, password.value, tab.value)
    } else {
      await auth.register(
        username.value,
        password.value,
        tab.value,
        isAdminTab.value ? adminCode.value.trim() : undefined,
      )
    }
    // 按选中的通道决定去向：管理员从「用户登录」进来仍是看前台，
    // 侧边栏的管理入口由 /users/me 的 role 决定，两件事分开
    router.push(tab.value === 'admin' ? '/admin' : safeRedirect(route.query.redirect))
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '网络异常，请稍后重试'
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center p-6">
    <div class="grid w-full max-w-[960px] gap-6 lg:grid-cols-[1.1fr_0.9fr]">
      <section class="hidden flex-col justify-between p-4 lg:flex">
        <div>
          <div class="mb-8 flex items-center gap-3">
            <div class="h-9 w-9 rounded-full" :style="{ background: 'var(--color-primary)' }" />
            <span class="text-[15px] font-semibold">AlwaysHealthy</span>
          </div>
          <h1 class="text-[32px] font-semibold leading-tight">
            把健康评估<br />变成可以执行的日常
          </h1>
          <p class="mt-4 max-w-[420px] text-[13px] leading-relaxed" :style="{ color: 'var(--color-text-secondary)' }">
            多智能体协作完成信息采集、风险评估、干预建议与计划跟踪。所有结论标注依据与版本，数据缺失时明确说明，不用默认值填补。
          </p>
        </div>
        <div class="mt-10 grid gap-3 text-[12px]" :style="{ color: 'var(--color-text-tertiary)' }">
          <p>评估结果仅供健康管理参考，不构成疾病诊断或治疗方案。</p>
          <p>出现胸痛、呼吸困难等紧急症状时，请直接呼叫急救。</p>
        </div>
      </section>

      <section
        class="glass-strong flex h-[664px] max-h-[calc(100vh-3rem)] flex-col overflow-y-auto p-6 lg:p-8"
        data-testid="login-card"
      >
        <div class="segment" role="tablist" aria-label="登录身份">
          <button
            v-for="item in tabs"
            :key="item.value"
            class="segment-item"
            :class="{ 'is-active': tab === item.value }"
            type="button"
            role="tab"
            :aria-selected="tab === item.value"
            @click="switchTab(item.value)"
          >
            {{ item.label }}
          </button>
        </div>

        <h2 class="mt-6 min-h-[26px] text-[18px] font-semibold">{{ heading }}</h2>
        <p class="mt-1 min-h-[36px] text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">{{ subheading }}</p>

        <form class="mt-6 flex flex-1 flex-col gap-4" @submit.prevent="submit">
          <div>
            <label class="label" for="username">用户名</label>
            <input id="username" v-model="username" class="field" autocomplete="username" placeholder="字母数字下划线" />
          </div>
          <div>
            <label class="label" for="password">密码</label>
            <input
              id="password"
              v-model="password"
              class="field"
              type="password"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              placeholder="至少 8 位"
            />
          </div>
          <div v-if="mode === 'register' && isAdminTab">
            <label class="label" for="admin-code">管理员邀请码</label>
            <input
              id="admin-code"
              v-model="adminCode"
              class="field"
              type="password"
              autocomplete="off"
              placeholder="由部署方配置"
            />
            <p class="mt-1.5 text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              邀请码由部署方配置，未配置时不开放管理员注册。
            </p>
          </div>
          <!-- 错误行常驻占位：出现/清空时不改变卡片高度，也不把提交按钮往下顶 -->
          <p
            class="min-h-[18px] text-[12px]"
            :style="{ color: 'var(--color-danger)' }"
            role="alert"
            data-testid="login-error"
          >
            {{ error }}
          </p>
          <button class="btn btn-primary mt-auto w-full" type="submit" :disabled="auth.pending" data-testid="login-submit">
            {{ submitLabel }}
          </button>
        </form>

        <button
          class="mt-4 w-full text-center text-[12px]"
          :style="{ color: 'var(--color-text-secondary)' }"
          type="button"
          @click="toggleMode"
        >
          {{ switchLabel }}
        </button>
        <p
          class="mt-2 min-h-[34px] text-center text-[11px]"
          :style="{ color: 'var(--color-text-tertiary)' }"
          data-testid="login-footer-note"
        >
          {{ footerNote }}
        </p>
      </section>
    </div>
  </div>
</template>
