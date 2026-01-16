<!--
  组件名: Settings.vue
  功能: 系统设置页面
  作者: 章涵硕
-->
<script setup lang="ts">
import { useSettingsStore } from '@/stores/settings'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'

const settingsStore = useSettingsStore()
const { 
  autoRefresh, 
  refreshInterval, 
  enableNotification, 
  warningThreshold, 
  dangerThreshold, 
  darkMode 
} = storeToRefs(settingsStore)

// 保存设置
function saveSettings() {
  settingsStore.saveToLocal()
  ElMessage.success('设置已保存！')
}

// 重置默认
function resetSettings() {
  darkMode.value = true
  autoRefresh.value = true
  refreshInterval.value = 30
  enableNotification.value = true
  warningThreshold.value = 80
  dangerThreshold.value = 95
  ElMessage.info('已重置为默认设置')
}
</script>

<template>
  <div class="settings-page">
    <div class="settings-card glass-card">
      <h3 class="section-title">
        <el-icon><Setting /></el-icon>
        系统设置
      </h3>
      
      <el-form label-width="140px" class="settings-form">
        <el-divider content-position="left">数据刷新</el-divider>
        
        <el-form-item label="自动刷新">
          <el-switch v-model="autoRefresh" />
        </el-form-item>
        
        <el-form-item label="刷新间隔(秒)">
          <el-slider v-model="refreshInterval" :min="10" :max="120" :step="10" show-input />
        </el-form-item>
        
        <el-divider content-position="left">预警设置</el-divider>
        
        <el-form-item label="启用通知">
          <el-switch v-model="enableNotification" />
        </el-form-item>
        
        <el-form-item label="警告阈值(%)">
          <el-input-number v-model="warningThreshold" :min="50" :max="100" />
        </el-form-item>
        
        <el-form-item label="危险阈值(%)">
          <el-input-number v-model="dangerThreshold" :min="80" :max="100" />
        </el-form-item>
        
        <el-divider content-position="left">界面设置</el-divider>
        
        <el-form-item label="深色模式">
          <el-switch v-model="darkMode" />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="saveSettings">保存设置</el-button>
          <el-button @click="resetSettings">重置默认</el-button>
        </el-form-item>
      </el-form>
    </div>
    
    <div class="about-card glass-card">
      <h3 class="section-title">
        <el-icon><InfoFilled /></el-icon>
        关于系统
      </h3>
      
      <div class="about-content">
        <div class="about-item">
          <span class="label">系统名称</span>
          <span class="value">智慧水利监测与管理平台</span>
        </div>
        <div class="about-item">
          <span class="label">版本号</span>
          <span class="value">v1.0.0</span>
        </div>
        <div class="about-item">
          <span class="label">开发者</span>
          <span class="value">章涵硕</span>
        </div>
        <div class="about-item">
          <span class="label">所属单位</span>
          <span class="value">河海大学水利水电学院</span>
        </div>
        <div class="about-item">
          <span class="label">技术栈</span>
          <span class="value">Vue 3 + NestJS + Supabase + Cesium</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  height: 100%;
}

.settings-card,
.about-card {
  padding: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 24px;
}

.settings-form {
  max-width: 500px;
}

.about-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.about-item {
  display: flex;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--glass-bg);
  border-radius: var(--radius-md);
}

.about-item .label {
  color: var(--text-secondary);
}

.about-item .value {
  color: var(--text-primary);
  font-weight: 500;
}
</style>
