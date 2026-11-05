<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { safeRedirect } from '@/utils/redirect'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const error = ref('')

async function submit() {
  error.value = ''
  if (username.value.length < 3 || password.value.length < 8) {
    error.value = '用户名至少 3 位，密码至少 8 位'
    return
  }
  try {
    if (mode.value === 'login') await auth.login(username.value, password.value)
    else await auth.register(username.value, password.value)
    router.push(safeRedirect(route.query.redirect))
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

      <section class="glass-strong p-6 lg:p-8">
        <h2 class="text-[18px] font-semibold">{{ mode === 'login' ? '登录' : '注册' }}</h2>
        <p class="mt-1 text-[12px]" :style="{ color: 'var(--color-text-secondary)' }">
          {{ mode === 'login' ? '使用账号继续你的健康档案' : '新账号会自动创建一份健康档案' }}
        </p>

        <form class="mt-6 flex flex-col gap-4" @submit.prevent="submit">
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
              autocomplete="current-password"
              placeholder="至少 8 位"
            />
          </div>
          <p v-if="error" class="text-[12px]" :style="{ color: 'var(--color-danger)' }">{{ error }}</p>
          <button class="btn btn-primary w-full" type="submit" :disabled="auth.pending">
            {{ auth.pending ? '处理中' : mode === 'login' ? '登录' : '注册并进入' }}
          </button>
        </form>

        <button class="mt-4 w-full text-center text-[12px]" :style="{ color: 'var(--color-text-secondary)' }" @click="mode = mode === 'login' ? 'register' : 'login'">
          {{ mode === 'login' ? '没有账号，去注册' : '已有账号，去登录' }}
        </button>
      </section>
    </div>
  </div>
</template>
