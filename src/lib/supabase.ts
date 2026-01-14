/**
 * 文件名: supabase.ts
 * 功能: Supabase 客户端初始化配置
 * 作者: 章涵硕
 */

import { createClient } from '@supabase/supabase-js'

// 从环境变量获取 Supabase 配置
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string

// 创建 Supabase 客户端实例
export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// 导出类型便于其他模块使用
export type { User, Session } from '@supabase/supabase-js'
