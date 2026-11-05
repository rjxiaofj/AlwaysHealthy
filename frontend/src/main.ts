import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { setSessionExpiredHandler } from './api/client'
import router from './router'
import { useThemeStore } from './stores/theme'
import { useToastStore } from './stores/toast'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)

const theme = useThemeStore()
theme.apply()

// 登录态过期时 api 层会叫一声，这里把人送回登录页；顺带记住原来停在哪，登录后回跳
setSessionExpiredHandler(() => {
  const current = router.currentRoute.value
  useToastStore().error('登录已过期，请重新登录')
  if (current.name !== 'login') {
    router.push({ name: 'login', query: { redirect: current.fullPath } })
  }
})

app.mount('#app')
