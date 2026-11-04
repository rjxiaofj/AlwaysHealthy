import { defineStore } from 'pinia'
import { ref } from 'vue'

const KEY = 'ah_theme'

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<'light' | 'dark'>((localStorage.getItem(KEY) as 'light' | 'dark') || 'light')

  function apply() {
    document.documentElement.dataset.theme = mode.value
  }

  function toggle() {
    mode.value = mode.value === 'light' ? 'dark' : 'light'
    localStorage.setItem(KEY, mode.value)
    apply()
  }

  return { mode, apply, toggle }
})
