/**
 * 文件名: auth.ts
 * 功能: 用户认证状态管理 (Pinia Store)
 * 作者: 章涵硕
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { supabase, type User, type Session } from '@/lib/supabase'

export const useAuthStore = defineStore('auth', () => {
    // 状态
    const user = ref<User | null>(null)
    const session = ref<Session | null>(null)
    const loading = ref(false)
    const error = ref<string | null>(null)

    // 计算属性
    const isAuthenticated = computed(() => !!session.value)
    const userEmail = computed(() => user.value?.email || '')

    /**
     * 初始化认证状态 - 检查现有会话
     */
    async function initialize() {
        loading.value = true
        try {
            const { data } = await supabase.auth.getSession()
            session.value = data.session
            user.value = data.session?.user ?? null

            // 监听认证状态变化
            supabase.auth.onAuthStateChange((_event, newSession) => {
                session.value = newSession
                user.value = newSession?.user ?? null
            })
        } catch (e) {
            error.value = (e as Error).message
        } finally {
            loading.value = false
        }
    }

    /**
     * 邮箱密码登录
     */
    async function signInWithEmail(email: string, password: string) {
        loading.value = true
        error.value = null
        try {
            const { data, error: signInError } = await supabase.auth.signInWithPassword({
                email,
                password
            })

            if (signInError) throw signInError

            session.value = data.session
            user.value = data.user
            return { success: true }
        } catch (e) {
            error.value = (e as Error).message
            return { success: false, error: error.value }
        } finally {
            loading.value = false
        }
    }

    /**
     * 邮箱密码注册
     */
    async function signUpWithEmail(email: string, password: string) {
        loading.value = true
        error.value = null
        try {
            const { data, error: signUpError } = await supabase.auth.signUp({
                email,
                password
            })

            if (signUpError) throw signUpError

            return { success: true, data }
        } catch (e) {
            error.value = (e as Error).message
            return { success: false, error: error.value }
        } finally {
            loading.value = false
        }
    }

    /**
     * 退出登录
     */
    async function signOut() {
        loading.value = true
        try {
            await supabase.auth.signOut()
            session.value = null
            user.value = null
        } catch (e) {
            error.value = (e as Error).message
        } finally {
            loading.value = false
        }
    }

    return {
        // 状态
        user,
        session,
        loading,
        error,
        // 计算属性
        isAuthenticated,
        userEmail,
        // 方法
        initialize,
        signInWithEmail,
        signUpWithEmail,
        signOut
    }
})
