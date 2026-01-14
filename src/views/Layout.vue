<!--
  组件名: Layout.vue
  功能: 主布局组件 - 侧边栏 + 顶栏 + 内容区
  作者: 章涵硕
-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessageBox } from 'element-plus'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 侧边栏折叠状态
const isCollapsed = ref(false)

// 当前激活的菜单
const activeMenu = computed(() => route.path)

// 菜单项
const menuItems = [
  { path: '/dashboard', title: '监测概览', icon: 'Monitor' },
  { path: '/monitor', title: '数据监测', icon: 'DataLine' },
  { path: '/model3d', title: '三维模型', icon: 'View' },
  { path: '/analysis', title: '智能分析', icon: 'TrendCharts' },
  { path: '/settings', title: '系统设置', icon: 'Setting' }
]

// 当前时间
const currentTime = ref(new Date().toLocaleString('zh-CN'))
setInterval(() => {
  currentTime.value = new Date().toLocaleString('zh-CN')
}, 1000)

/**
 * 处理退出登录
 */
async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await authStore.signOut()
    router.push('/login')
  } catch {
    // 用户取消
  }
}
</script>

<template>
  <div class="layout">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ collapsed: isCollapsed }">
      <!-- Logo -->
      <div class="logo">
        <el-icon :size="32" color="var(--accent)">
          <Monitor />
        </el-icon>
        <span v-if="!isCollapsed" class="logo-text">智慧水利</span>
      </div>
      
      <!-- 菜单 -->
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        router
        class="sidebar-menu"
      >
        <el-menu-item 
          v-for="item in menuItems" 
          :key="item.path"
          :index="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
      
      <!-- 折叠按钮 -->
      <div class="collapse-btn" @click="isCollapsed = !isCollapsed">
        <el-icon>
          <component :is="isCollapsed ? 'Expand' : 'Fold'" />
        </el-icon>
      </div>
    </aside>
    
    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 顶栏 -->
      <header class="header glass-card">
        <div class="header-left">
          <h2 class="page-title">{{ route.meta.title }}</h2>
        </div>
        
        <div class="header-right">
          <!-- 时间显示 -->
          <div class="time-display">
            <el-icon><Clock /></el-icon>
            <span>{{ currentTime }}</span>
          </div>
          
          <!-- 用户信息 -->
          <el-dropdown trigger="click">
            <div class="user-info">
              <el-avatar :size="36" class="avatar">
                {{ authStore.userEmail.charAt(0).toUpperCase() }}
              </el-avatar>
              <span class="username">{{ authStore.userEmail }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>
                  <el-icon><User /></el-icon>个人中心
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      
      <!-- 内容区 -->
      <div class="content-wrapper">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>

  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  background: var(--primary-dark);
}

/* 侧边栏 */
.sidebar {
  width: 240px;
  background: var(--primary);
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  transition: width var(--transition-normal);
}

.sidebar.collapsed {
  width: 64px;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border-bottom: 1px solid var(--border);
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.sidebar-menu {
  flex: 1;
  padding: 12px 0;
  border: none !important;
}

.sidebar-menu .el-menu-item {
  height: 48px;
  margin: 4px 8px;
  border-radius: var(--radius-md);
}

.collapse-btn {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  border-top: 1px solid var(--border);
  transition: all var(--transition-fast);
}

.collapse-btn:hover {
  color: var(--accent);
  background: var(--glass-bg-hover);
}

/* 主内容区 */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 顶栏 */
.header {
  height: 64px;
  margin: 12px 12px 0;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--glass-bg);
  border-radius: var(--radius-lg);
}

.header-left {
  display: flex;
  align-items: center;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.time-display {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 14px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.user-info:hover {
  background: var(--glass-bg-hover);
}

.avatar {
  background: var(--accent-gradient);
  color: var(--primary-dark);
  font-weight: 600;
}

.username {
  color: var(--text-primary);
  font-size: 14px;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 内容区 */
.content-wrapper {
  flex: 1;
  padding: 12px;
  overflow: auto;
}

/* 页面切换动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
