import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ToastItem {
  id: number
  text: string
  tone: 'info' | 'success' | 'error'
}

let seed = 0

export const useToastStore = defineStore('toast', () => {
  const items = ref<ToastItem[]>([])

  function push(text: string, tone: ToastItem['tone'] = 'info') {
    const id = ++seed
    items.value.push({ id, text, tone })
    window.setTimeout(() => {
      items.value = items.value.filter((item) => item.id !== id)
    }, 3200)
  }

  function error(text: string) {
    push(text, 'error')
  }

  function success(text: string) {
    push(text, 'success')
  }

  return { items, push, error, success }
})
