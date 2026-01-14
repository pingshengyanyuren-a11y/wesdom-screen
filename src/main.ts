/**
 * 文件名: main.ts
 * 功能: Vue 应用入口文件
 * 作者: 章涵硕
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Element Plus
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

// 路由
import router from './router'

// 样式
import './styles/water-theme.css'

// 根组件
import App from './App.vue'

// 认证状态
import { useAuthStore } from './stores/auth'

// 创建应用实例
const app = createApp(App)

// 使用插件
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { size: 'default' })

// 注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
}

// 初始化认证状态后挂载应用
const authStore = useAuthStore()
authStore.initialize().then(() => {
    app.mount('#app')
})
