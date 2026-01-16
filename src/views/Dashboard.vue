<!--
  组件名: Dashboard.vue
  功能: 首页监测概览仪表盘
  作者: 章涵硕
  特色: 实时数据卡片 + 状态统计 + 快速入口
-->
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { Statistics, MonitoringPoint } from '@/types'
import { getStatistics, getMonitoringPoints } from '@/api/monitoring'
import * as mlApi from '@/api/ml'

const router = useRouter()

// 统计数据
const statistics = ref<Statistics>({
  totalPoints: 0,
  normalCount: 0,
  warningCount: 0,
  dangerCount: 0,
  latestUpdate: '--'
})

// 实时库水位数据 (模拟，因为没有专门的水位测点接口)
const waterLevel = ref(142.35)

// 快速入口
const quickLinks = ref([
  { title: '引张线监测', count: 0, type: 'tension_wire', icon: 'Connection', color: '#00d4ff', route: '/monitor' },
  { title: '静力水准', count: 0, type: 'hydrostatic_level', icon: 'DataLine', color: '#10b981', route: '/monitor' },
  { title: '倒垂线', count: 0, type: 'plumb_line', icon: 'Aim', color: '#f59e0b', route: '/monitor' },
  { title: '三维模型', count: 1, type: 'model', icon: 'View', color: '#8b5cf6', route: '/bigscreen' }
])

// 最近告警
interface AlarmItem {
  id: string
  point: string
  type: string
  value: number
  status: string
  time: string
}
const recentAlarms = ref<AlarmItem[]>([])

// 定时器
let timer: number | null = null

/**
 * 加载数据
 */
async function loadData() {
  // 并行加载，互不影响
  Promise.allSettled([
    loadStatistics(),
    loadQuickAccessData()
  ])
}

/**
 * 加载统计数据和ML分析
 */
async function loadStatistics() {
  try {
    // 1. 获取统计数据 (基础)
    const stats = await getStatistics()
    
    // 2. [关键修改] 使用ML后端数据覆盖风险统计，确保全站数据统一
    // 2.1 尝试获取 ML 后端测点列表 (允许失败)
    try {
      const mlData = await mlApi.getPoints()
      if (mlData) {
        // console.log('ML Backend Points synced:', mlData.count)
      }
    } catch (e) {
      console.warn('ML Backend Points sync failed (non-critical):', e)
    }

    // 2.2 尝试获取异常检测结果 (覆盖风险统计)
    try {
      const anomalyResult = await mlApi.detectAnomalies()
      if (anomalyResult) {
        console.log('ML Backend Anomalies synced:', anomalyResult)
        
        // 覆盖风险统计
        statistics.value = {
          totalPoints: stats.totalPoints, // 保持数据库总数
          normalCount: stats.totalPoints - anomalyResult.total_anomalies,
          warningCount: anomalyResult.by_severity.medium + anomalyResult.by_severity.low,
          dangerCount: anomalyResult.by_severity.high,
          latestUpdate: new Date().toLocaleString('zh-CN')
        }
        
        // 更新最近告警 (使用ML检测出的真实异常)
        recentAlarms.value = anomalyResult.anomalies
          .slice(0, 5)
          .map((a: any) => ({
            id: a.point_name,
            point: a.point_name,
            type: a.type,
            value: a.current_value,
            status: a.severity === 'high' ? 'danger' : 'warning',
            time: a.measure_time.split(' ')[0]
          }))
      } else {
          statistics.value = stats
      }
    } catch (mlError) {
      console.error('ML Backend Anomaly sync failed:', mlError)
      // 保持使用 stats (数据库静态统计) 作为降级方案
      statistics.value = stats
    }

  } catch (error) {
    console.error('加载Dashboard统计数据失败:', error)
  }
}

/**
 * 加载快速入口数据
 */
async function loadQuickAccessData() {
  try {
    // 3. 获取测点列表用于快速入口计数
    const points = await getMonitoringPoints()
    console.log('Fetched points for Quick Access:', points.length) 
    
    const countByType = (t: string) => points.filter(p => p.type === t).length
    
    quickLinks.value[0].count = countByType('tension_wire')
    quickLinks.value[1].count = countByType('hydrostatic_level')
    quickLinks.value[2].count = countByType('plumb_line')
  } catch (error) {
    console.error('加载快速入口数据失败:', error)
  }
}

/**
 * 跳转到对应页面
 */
function navigateTo(link: any) {
  if (link.route === '/monitor') {
    router.push({ path: link.route, query: { type: link.type } })
  } else {
    router.push(link.route)
  }
}

/**
 * 获取状态标签样式
 */
function getStatusClass(status: string) {
  return `status-tag status-tag--${status}`
}

onMounted(() => {
  loadData()
  
  // 每30秒刷新一次数据
  timer = window.setInterval(() => {
    loadData()
    // 模拟水位变化
    waterLevel.value = 142 + Math.random() * 0.5
  }, 30000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="dashboard">
    <!-- 顶部统计卡片 -->
    <div class="stats-row">
      <!-- 测点总览 -->
      <div class="stat-card glass-card animate-fade-in-up">
        <div class="stat-icon" style="background: rgba(0, 212, 255, 0.15);">
          <el-icon :size="28" color="var(--accent)"><Monitor /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-label">测点总数</span>
          <span class="stat-value">{{ statistics.totalPoints }}</span>
        </div>
      </div>
      
      <!-- 正常测点 -->
      <div class="stat-card glass-card animate-fade-in-up" style="animation-delay: 0.1s;">
        <div class="stat-icon" style="background: rgba(16, 185, 129, 0.15);">
          <el-icon :size="28" color="var(--success)"><CircleCheckFilled /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-label">正常</span>
          <span class="stat-value" style="color: var(--success);">{{ statistics.normalCount }}</span>
        </div>
      </div>
      
      <!-- 警告测点 -->
      <div class="stat-card glass-card animate-fade-in-up" style="animation-delay: 0.2s;">
        <div class="stat-icon" style="background: rgba(245, 158, 11, 0.15);">
          <el-icon :size="28" color="var(--warning)"><WarningFilled /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-label">警告</span>
          <span class="stat-value" style="color: var(--warning);">{{ statistics.warningCount }}</span>
        </div>
      </div>
      
      <!-- 危险测点 -->
      <div class="stat-card glass-card animate-fade-in-up" style="animation-delay: 0.3s;">
        <div class="stat-icon" style="background: rgba(239, 68, 68, 0.15);">
          <el-icon :size="28" color="var(--danger)"><CircleCloseFilled /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-label">危险</span>
          <span class="stat-value" style="color: var(--danger);">{{ statistics.dangerCount }}</span>
        </div>
      </div>
      
      <!-- 库水位 -->
      <div class="stat-card glass-card animate-fade-in-up animate-glow" style="animation-delay: 0.4s;">
        <div class="stat-icon" style="background: rgba(59, 130, 246, 0.15);">
          <el-icon :size="28" color="var(--info)"><Odometer /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-label">库水位</span>
          <span class="stat-value" style="color: var(--info);">{{ waterLevel.toFixed(2) }}m</span>
        </div>
      </div>
    </div>
    
    <!-- 中间内容区 -->
    <div class="content-row">
      <!-- 快速入口 -->
      <div class="quick-links glass-card">
        <h3 class="section-title">
          <el-icon><Grid /></el-icon>
          快速入口
        </h3>
        <div class="link-grid">
          <div 
            v-for="link in quickLinks" 
            :key="link.title" 
            class="link-item"
            :style="{ '--link-color': link.color }"
            @click="navigateTo(link)"
          >
            <div class="link-icon">
              <el-icon :size="32"><component :is="link.icon" /></el-icon>
            </div>
            <div class="link-info">
              <span class="link-title">{{ link.title }}</span>
              <span class="link-count">{{ link.count }} 个测点</span>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 最近告警 -->
      <div class="recent-alarms glass-card">
        <h3 class="section-title">
          <el-icon><Bell /></el-icon>
          最近告警
        </h3>
        <div class="alarm-list">
          <div v-for="alarm in recentAlarms" :key="alarm.id" class="alarm-item">
            <div class="alarm-left">
              <span class="alarm-point">{{ alarm.point }}</span>
              <span class="alarm-type">{{ alarm.type }}</span>
            </div>
            <div class="alarm-center">
              <span class="alarm-value">{{ alarm.value }} mm</span>
              <span :class="getStatusClass(alarm.status)">
                {{ alarm.status === 'warning' ? '警告' : '危险' }}
              </span>
            </div>
            <div class="alarm-time">{{ alarm.time }}</div>
          </div>
          <div v-if="recentAlarms.length === 0" class="no-alarm">
            <el-empty description="系统运行正常，无告警信息" :image-size="60" />
          </div>
        </div>
      </div>
    </div>
    
    <!-- 底部信息 -->
    <div class="footer-info glass-card">
      <div class="info-item">
        <el-icon><Clock /></el-icon>
        <span>最近更新：{{ statistics.latestUpdate }}</span>
      </div>
      <div class="info-item">
        <el-icon><Connection /></el-icon>
        <span>系统状态：<span style="color: var(--success);">在线</span></span>
      </div>
      <div class="info-item">
        <el-icon><DataAnalysis /></el-icon>
        <span>数据来源：Supabase 实时数据库</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}

/* 统计卡片行 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

/* 内容行 */
.content-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

/* 快速入口 */
.quick-links {
  padding: 24px;
}

.link-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.link-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: var(--glass-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.link-item:hover {
  border-color: var(--link-color);
  background: rgba(255, 255, 255, 0.08);
  transform: translateY(-2px);
}

.link-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--link-color) 15%, transparent);
  color: var(--link-color);
}

.link-info {
  display: flex;
  flex-direction: column;
}

.link-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.link-count {
  font-size: 13px;
  color: var(--text-secondary);
}

/* 最近告警 */
.recent-alarms {
  padding: 24px;
}

.alarm-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alarm-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: var(--glass-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.alarm-item:hover {
  border-color: var(--border-accent);
}

.alarm-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.alarm-point {
  font-weight: 600;
  color: var(--text-primary);
}

.alarm-type {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 2px 8px;
  background: var(--glass-bg);
  border-radius: 4px;
}

.alarm-center {
  display: flex;
  align-items: center;
  gap: 12px;
}

.alarm-value {
  font-weight: 500;
  color: var(--text-primary);
}

.alarm-time {
  font-size: 13px;
  color: var(--text-muted);
}

/* 底部信息 */
.footer-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 40px;
  padding: 16px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

/* 响应式 */
@media (max-width: 1200px) {
  .stats-row {
    grid-template-columns: repeat(3, 1fr);
  }
  
  .content-row {
    grid-template-columns: 1fr;
  }
}
</style>
