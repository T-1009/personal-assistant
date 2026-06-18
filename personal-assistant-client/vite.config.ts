/// <reference types="vitest" />
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig(({ mode }) => {
  // 加载当前环境的环境变量，包括 .env.local 等
  const env = loadEnv(mode, process.cwd(), '')
  
  // 判断代理目标环境，默认为 dev
  const targetEnv = env.PROXY_TARGET || 'dev'
  
  // 生产环境与本地环境的配置区分
  const isProdTarget = targetEnv === 'prod'
  const targetUrl = isProdTarget 
    ? 'https://defaultgw-ha3wenzqga.cn-southwest-2.huaweicloud-agentarts.com' 
    : 'http://localhost:8080'

  return {
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './src/test/setup.ts',
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    plugins: [react(), tailwindcss()],
    build: {
      outDir: 'dist',
      sourcemap: false,
    },
    server: {
      proxy: {
        '/invocations/playground': {
          target: targetUrl,
          changeOrigin: true,
          ws: true,
          rewrite: (path) => isProdTarget 
            ? path.replace(/^\/invocations\/playground/, '/runtimes/personal-assistant/invocations/playground') 
            : path,
        },
        '/invocations': {
          target: targetUrl,
          changeOrigin: true,
          rewrite: (path) => isProdTarget 
            ? path.replace(/^\/invocations/, '/runtimes/personal-assistant/invocations') 
            : path,
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              proxyReq.setHeader('X-HW-AgentGateway-User-Id', 'dev-user');
            });
          },
        },
      },
    },
  }
})
