<script setup lang="ts">
withDefaults(
  defineProps<{
    name: 'home' | 'chat' | 'chart' | 'calendar' | 'pulse' | 'user' | 'sun' | 'moon' | 'menu' | 'logout' | 'plus' | 'close'
    size?: number
  }>(),
  { size: 18 },
)

const paths: Record<string, string> = {
  home: 'M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z',
  chat: 'M4 5h16v11H9l-5 4z',
  chart: 'M4 19V5m0 14h16M8 15l3-4 3 2 4-6',
  calendar: 'M5 7h14v13H5zM5 11h14M9 4v4M15 4v4',
  pulse: 'M3 12h4l2-5 3 10 2-5h6',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-4 3.6-6 8-6s8 2 8 6',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19',
  moon: 'M20 14A8 8 0 0 1 10 4a8 8 0 1 0 10 10z',
  menu: 'M4 7h16M4 12h16M4 17h16',
  logout: 'M14 5h5v14h-5M10 12H3m0 0 3-3m-3 3 3 3',
  plus: 'M12 5v14M5 12h14',
  close: 'M6 6l12 12M18 6 6 18',
}
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name]" />
  </svg>
</template>
