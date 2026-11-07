<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

// 管理后台有自己的外壳：侧边栏只有管理菜单，不复用 AppLayout。
// 复用 AppLayout 会让健康首页/智能助手/评估这些用户端入口出现在管理员视野里，
// 而管理员在后台不该看到「待办提醒」和个人健康入口。
const auth = useAuthStore()
const theme = useThemeStore()
const route = useRoute()
const router = useRouter()
const drawer = ref(false)

const menu = [
  { to: '/admin/overview', label: '总览', icon: 'grid' as const },
  { to: '/admin/analytics', label: '数据看板', icon: 'chart' as const },
  { to: '/admin/accounts', label: '账号', icon: 'user' as const },
  { to: '/admin/audit', label: '审计', icon: 'list' as const },
  { to: '/admin/incidents', label: '安全事件', icon: 'shield' as const },
  { to: '/admin/runtime', label: '模型与 Agent', icon: 'pulse' as const },
]

const current = computed(() => route.path)
const pageTitle = computed(() => menu.find((item) => item.to === current.value)?.label ?? '管理后台')

async function logout() {
  await auth.logout()
  router.push('/login')
}

onMounted(() => {
  void auth.ensureUser().catch(() => undefined)
})
</script>

<template>
  <div class="flex min-h-screen w-full gap-5 p-4 lg:p-6">
    <aside
      class="glass hidden w-[228px] shrink-0 flex-col p-4 lg:flex lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)] lg:self-start"
    >
      <div class="flex items-center gap-2 px-2 pb-2 pt-2">
        <div class="h-8 w-8 rounded-full" :style="{ background: 'var(--color-primary)' }" />
        <div>
          <p class="text-[14px] font-semibold leading-tight">AlwaysHealthy</p>
          <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">管理后台</p>
        </div>
      </div>

      <p
        class="mb-3 mt-1 rounded-xl px-2 py-1.5 text-[11px]"
        :style="{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)' }"
      >
        {{ auth.user?.username || '管理员' }}
      </p>

      <nav class="flex flex-1 flex-col gap-1">
        <RouterLink
          v-for="item in menu"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ 'is-active': current === item.to }"
        >
          <AppIcon :name="item.icon" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div
        class="mt-4 flex items-center justify-between border-t px-1 pt-3"
        :style="{ borderColor: 'var(--color-border)' }"
      >
        <button
          class="btn btn-ghost !px-3"
          type="button"
          :aria-label="theme.mode === 'light' ? '切换深色' : '切换浅色'"
          @click="theme.toggle()"
        >
          <AppIcon :name="theme.mode === 'light' ? 'moon' : 'sun'" />
        </button>
        <RouterLink to="/" class="btn btn-ghost !px-3" aria-label="返回前台">
          <AppIcon name="home" />
        </RouterLink>
        <button class="btn btn-ghost !px-3" type="button" aria-label="退出登录" @click="logout">
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
            <p class="text-[13px] font-medium">管理后台 · {{ pageTitle }}</p>
            <p class="text-[11px]" :style="{ color: 'var(--color-text-tertiary)' }">
              管理员不查看任何人的健康档案、评估或计划
            </p>
          </div>
        </div>
        <RouterLink to="/" class="chip">前台首页</RouterLink>
      </header>

      <main class="min-h-0 flex-1">
        <RouterView />
      </main>
    </div>

    <transition name="fade">
      <div v-if="drawer" class="fixed inset-0 z-40 lg:hidden">
        <div class="absolute inset-0 bg-black/20" @click="drawer = false" />
        <div class="glass-strong absolute bottom-3 left-3 top-3 w-[240px] p-4">
          <div class="flex items-center justify-between pb-4">
            <span class="text-[13px] font-semibold">管理菜单</span>
            <button class="btn btn-ghost !px-2" type="button" aria-label="关闭菜单" @click="drawer = false">
              <AppIcon name="close" />
            </button>
          </div>
          <nav class="flex flex-col gap-1">
            <RouterLink
              v-for="item in menu"
              :key="item.to"
              :to="item.to"
              class="nav-item"
              :class="{ 'is-active': current === item.to }"
              @click="drawer = false"
            >
              <AppIcon :name="item.icon" />
              <span>{{ item.label }}</span>
            </RouterLink>
          </nav>
          <RouterLink to="/" class="btn btn-ghost mt-4 w-full" @click="drawer = false">返回前台</RouterLink>
          <button class="btn btn-ghost mt-2 w-full" type="button" @click="theme.toggle()">
            {{ theme.mode === 'light' ? '深色主题' : '浅色主题' }}
          </button>
          <button class="btn btn-ghost mt-2 w-full" type="button" @click="logout">退出登录</button>
        </div>
      </div>
    </transition>
  </div>
</template>
