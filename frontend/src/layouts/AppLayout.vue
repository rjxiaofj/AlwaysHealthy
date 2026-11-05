<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import { useAuthStore } from '@/stores/auth'
import { useReminderStore } from '@/stores/reminders'
import { useThemeStore } from '@/stores/theme'

const auth = useAuthStore()
const theme = useThemeStore()
const reminders = useReminderStore()
const router = useRouter()
const drawer = ref(false)

const nav = [
  { to: '/', label: '健康首页', icon: 'home' as const },
  { to: '/chat', label: '智能助手', icon: 'chat' as const },
  { to: '/assessment', label: '健康评估', icon: 'pulse' as const },
  { to: '/plans', label: '健康管理', icon: 'calendar' as const },
  { to: '/trends', label: '指标趋势', icon: 'chart' as const },
  { to: '/profile', label: '个人中心', icon: 'user' as const },
]

async function logout() {
  await auth.logout()
  router.push('/login')
}

onMounted(async () => {
  await auth.ensureUser()
  reminders.load().catch(() => undefined)
})
</script>

<template>
  <div class="flex min-h-screen w-full gap-5 p-4 lg:p-6">
    <aside class="glass hidden w-[236px] shrink-0 flex-col p-4 lg:flex">
      <div class="flex items-center gap-2 px-2 pb-6 pt-2">
        <div class="h-8 w-8 rounded-full" :style="{ background: 'var(--color-primary)' }" />
        <div>
          <p class="text-[14px] font-semibold leading-tight">AlwaysHealthy</p>
          <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">健康评估与管理</p>
        </div>
      </div>

      <nav class="flex flex-1 flex-col gap-1">
        <RouterLink v-for="item in nav" :key="item.to" :to="item.to" class="nav-item">
          <AppIcon :name="item.icon" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="mt-4 flex items-center justify-between border-t px-2 pt-4" :style="{ borderColor: 'var(--color-border)' }">
        <button class="btn btn-ghost !px-3" @click="theme.toggle()" :aria-label="theme.mode === 'light' ? '切换深色' : '切换浅色'">
          <AppIcon :name="theme.mode === 'light' ? 'moon' : 'sun'" />
        </button>
        <button class="btn btn-ghost !px-3" aria-label="退出登录" @click="logout">
          <AppIcon name="logout" />
        </button>
      </div>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col gap-4">
      <header class="glass flex items-center justify-between px-4 py-3 lg:px-5">
        <div class="flex items-center gap-3">
          <button class="btn btn-ghost !px-2 lg:hidden" aria-label="打开菜单" @click="drawer = true">
            <AppIcon name="menu" />
          </button>
          <div>
            <p class="text-[13px] font-medium">{{ auth.user?.username || '健康用户' }}</p>
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              数据仅用于健康管理参考，不构成诊断
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <RouterLink to="/reminders" class="chip">
            待办提醒
            <span v-if="reminders.unread" class="ml-1 font-semibold" :style="{ color: 'var(--color-danger)' }">{{ reminders.unread }}</span>
          </RouterLink>
        </div>
      </header>

      <main class="min-h-0 flex-1">
        <RouterView />
      </main>
    </div>

    <transition name="fade">
      <div v-if="drawer" class="fixed inset-0 z-40 lg:hidden">
        <div class="absolute inset-0 bg-black/20" @click="drawer = false" />
        <div class="glass-strong absolute left-3 top-3 bottom-3 w-[240px] p-4">
          <div class="flex items-center justify-between pb-4">
            <span class="text-[13px] font-semibold">导航</span>
            <button class="btn btn-ghost !px-2" aria-label="关闭菜单" @click="drawer = false">
              <AppIcon name="close" />
            </button>
          </div>
          <nav class="flex flex-col gap-1">
            <RouterLink
              v-for="item in nav"
              :key="item.to"
              :to="item.to"
              class="nav-item"
              @click="drawer = false"
            >
              <AppIcon :name="item.icon" />
              <span>{{ item.label }}</span>
            </RouterLink>
          </nav>
          <button class="btn btn-ghost mt-4 w-full" @click="theme.toggle()">
            {{ theme.mode === 'light' ? '深色主题' : '浅色主题' }}
          </button>
          <button class="btn btn-ghost mt-2 w-full" @click="logout">退出登录</button>
        </div>
      </div>
    </transition>
  </div>
</template>
