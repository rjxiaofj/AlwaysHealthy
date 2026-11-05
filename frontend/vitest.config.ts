import { defineConfig, mergeConfig } from 'vitest/config'

import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      // 组件与 store 都用到 window、localStorage，浏览器环境比 jsdom 轻
      environment: 'happy-dom',
      include: ['src/**/*.spec.ts'],
      restoreMocks: true,
    },
  }),
)
