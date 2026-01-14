/**
 * 文件名: index.ts
 * 功能: Vue Router 路由配置
 * 作者: 章涵硕
 */

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { supabase } from '@/lib/supabase'

// 路由配置
const routes: RouteRecordRaw[] = [
    {
        path: '/login',
        name: 'Login',
        component: () => import('@/views/Login.vue'),
        meta: { requiresAuth: false, title: '登录' }
    },
    {
        path: '/',
        name: 'Layout',
        component: () => import('@/views/Layout.vue'),
        meta: { requiresAuth: true },
        redirect: '/dashboard',
        children: [
            {
                path: 'dashboard',
                name: 'Dashboard',
                component: () => import('@/views/Dashboard.vue'),
                meta: { title: '监测概览', icon: 'Monitor' }
            },
            {
                path: 'monitor',
                name: 'Monitor',
                component: () => import('@/views/Monitor.vue'),
                meta: { title: '数据监测', icon: 'DataLine' }
            },
            {
                path: 'model3d',
                name: 'Model3D',
                redirect: '/bigscreen',  // 统一跳转到大屏页面
                meta: { title: '三维模型', icon: 'View' }
            },
            {
                path: 'analysis',
                name: 'Analysis',
                component: () => import('@/views/Analysis.vue'),
                meta: { title: '智能分析', icon: 'TrendCharts' }
            },
            {
                path: 'settings',
                name: 'Settings',
                component: () => import('@/views/Settings.vue'),
                meta: { title: '系统设置', icon: 'Setting' }
            }
        ]
    },
    {
        path: '/bigscreen',
        name: 'BigScreen',
        component: () => import('@/views/BigScreen.vue'),
        meta: { requiresAuth: false, title: '可视化大屏' }
    },
    {
        path: '/:pathMatch(.*)*',
        redirect: '/dashboard'
    }
]

// 创建路由实例
const router = createRouter({
    history: createWebHistory(),
    routes
})

// 路由守卫 - 登录验证
router.beforeEach(async (to, _from, next) => {
    // 更新页面标题
    document.title = `${to.meta.title || '智慧水利监测平台'} - 河海大学`

    // 检查是否需要登录
    if (to.meta.requiresAuth !== false) {
        const { data: { session } } = await supabase.auth.getSession()

        if (!session) {
            // 未登录，跳转到登录页
            next({ name: 'Login', query: { redirect: to.fullPath } })
            return
        }
    }

    next()
})

export default router
