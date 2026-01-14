<!--
  组件名: Monitor.vue
  功能: 数据监测页面 - 测点列表 + 历史数据图表 + 新增测值
  作者: 章涵硕
-->
<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { 
  TitleComponent, 
  TooltipComponent, 
  LegendComponent,
  GridComponent 
} from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import type { MonitoringPoint, MonitoringValue } from '@/types'
import { getMonitoringPoints, getMonitoringValues, addMonitoringValue } from '@/api/monitoring'
import * as mlApi from '@/api/ml'

// 注册 ECharts 组件
use([CanvasRenderer, LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const route = useRoute()

// 测点类型选项
const pointTypes = [
  { value: 'all', label: '全部类型' },
  { value: 'tension_wire', label: '引张线' },
  { value: 'hydrostatic_level', label: '静力水准' },
  { value: 'plumb_line', label: '倒垂线' }
]

// 筛选条件
const filterType = ref('all')
const searchKeyword = ref('')

// 时间筛选
const timeFilterType = ref('recent6months') // recent1week, recent1month, recent3months, recent6months, recent1year, all, custom
const customDateRange = ref<[Date, Date] | null>(null)
const selectedYear = ref<number | null>(null)

// 测点数据
const points = ref<MonitoringPoint[]>([])
const loading = ref(false)

// 选中的测点
const selectedPoint = ref<MonitoringPoint | null>(null)

// 历史数据
const historyData = ref<MonitoringValue[]>([])
const chartLoading = ref(false)

// 新增测值表单
const addValueDialogVisible = ref(false)
const newValueForm = ref({
  pointId: '',
  value: 0,
  measuredAt: new Date() // 修改为Date对象
})

// 筛选后的测点
const filteredPoints = computed(() => {
  return points.value.filter(p => {
    const matchType = filterType.value === 'all' || p.type === filterType.value
    const matchSearch = !searchKeyword.value || 
      p.name.toLowerCase().includes(searchKeyword.value.toLowerCase()) ||
      p.section.includes(searchKeyword.value)
    return matchType && matchSearch
  })
})

// 数据统计信息
const dataStats = computed(() => {
  if (historyData.value.length === 0) return null
  
  const dates = historyData.value.map((d: MonitoringValue) => new Date(d.measuredAt).getTime())
  const totalPoints = historyData.value.length
  
  return {
    startDate: new Date(Math.min(...dates)).toLocaleDateString('zh-CN'),
    endDate: new Date(Math.max(...dates)).toLocaleDateString('zh-CN'),
    totalPoints,
    avgInterval: dates.length > 1 
      ? ((Math.max(...dates) - Math.min(...dates)) / (dates.length - 1) / (1000 * 60 * 60 * 24)).toFixed(1)
      : '0'
  }
})

// 可选年份列表（2011-2024）
const availableYears = computed(() => {
  const years: number[] = []
  for (let year = 2011; year <= 2024; year++) {
    years.push(year)
  }
  return years.reverse() // 最新年份在前
})

// ECharts 图表配置
const chartOption = computed(() => ({
  backgroundColor: 'transparent',
  title: {
    text: selectedPoint.value ? `${selectedPoint.value.name} 历史趋势` : '请选择测点',
    textStyle: { color: '#f8fafc', fontSize: 14 },
    left: 'center'
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(17, 34, 64, 0.9)',
    borderColor: 'rgba(0, 212, 255, 0.3)',
    textStyle: { color: '#f8fafc' },
    formatter: function(params: any) {
      const item = params[0]
      if (!item) return ''
      return `${item.name}<br/>${item.marker}${item.seriesName}: <b>${item.value} mm</b>`
    }
  },
  // 添加工具栏实现打印/导出功能
  toolbox: {
    show: true,
    feature: {
      saveAsImage: { 
        show: true, 
        title: '保存为图片',
        name: selectedPoint.value ? `测点_${selectedPoint.value.name}_趋势图` : '趋势图',
        backgroundColor: '#0f172a'
      },
      dataView: { show: true, title: '数据视图', lang: ['数据视图', '关闭', '刷新'] }
    },
    iconStyle: { borderColor: '#94a3b8' },
    right: 20
  },
  grid: {
    top: 60,
    left: 60,
    right: 40,
    bottom: 40
  },
  xAxis: {
    type: 'category',
    data: historyData.value.map(d => new Date(d.measuredAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })),
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
    axisLabel: { color: '#94a3b8', fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    name: '位移 (mm)',
    nameTextStyle: { color: '#94a3b8' },
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
    axisLabel: { color: '#94a3b8' },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  series: [{
    name: '测值',
    type: 'line',
    smooth: true,
    data: historyData.value.map(d => d.value),
    lineStyle: { color: '#00d4ff', width: 2 },
    areaStyle: {
      color: {
        type: 'linear',
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(0, 212, 255, 0.3)' },
          { offset: 1, color: 'rgba(0, 212, 255, 0)' }
        ]
      }
    },
    itemStyle: { color: '#00d4ff' },
    markPoint: {
      data: [
        { type: 'max', name: '最大值' },
        { type: 'min', name: '最小值' }
      ]
    }
  }]
}))

/**
 * 加载所有测点
 */
async function loadPoints() {
  loading.value = true
  try {
    points.value = await getMonitoringPoints()
    
    // [关键修改] 使用 ML 后端数据进行二次覆盖，确保状态一致
    try {
      const anomalyResult = await mlApi.detectAnomalies()
      if (anomalyResult && anomalyResult.anomalies) {
        // 创建异常映射表
        const anomalyMap = new Map()
        anomalyResult.anomalies.forEach((a: any) => {
          const status = a.severity === 'high' ? 'danger' : 'warning'
          anomalyMap.set(a.point_name, status)
        })
        
        // 更新所有测点的状态
        points.value.forEach((p: any) => {
          if (anomalyMap.has(p.name)) {
            p.status = anomalyMap.get(p.name)
          } else {
            p.status = 'normal'
          }
        })
        console.log(`Monitor列表已同步 ML 异常状态`)
      }
    } catch (mlError) {
      console.warn('ML Backend status sync failed:', mlError)
    }
    
    // 如果有 type 参数，设置筛选
    if (route.query.type) {
      filterType.value = String(route.query.type)
    }
    
    // 默认选中第一个或特定测点
    if (points.value.length > 0 && !selectedPoint.value) {
      // 优先选中筛选结果中的第一个
      const target = filteredPoints.value[0] || points.value[0]
      if (target) {
        selectPoint(target)
      }
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('加载测点数据失败')
  } finally {
    loading.value = false
  }
}

/**
 * 选择测点查看详情
 */
async function selectPoint(point: MonitoringPoint) {
  selectedPoint.value = point
  // 重置时间筛选为默认
  timeFilterType.value = 'recent6months'
  selectedYear.value = null
  await loadHistoryWithFilter()
}

/**
 * 处理自定义日期变化
 */
function handleCustomDateChange(value: [Date, Date] | null) {
  if (value) {
    timeFilterType.value = 'custom'
    selectedYear.value = null
    loadHistoryWithFilter()
  }
}

/**
 * 根据筛选条件加载历史数据
 */
async function loadHistoryWithFilter() {
  if (!selectedPoint.value) return
  
  chartLoading.value = true
  try {
    let startDate: string | undefined
    let endDate: string | undefined
    const now = new Date()
    
    // 根据筛选类型计算日期范围
    if (selectedYear.value) {
      // 按年份筛选
      startDate = `${selectedYear.value}-01-01`
      endDate = `${selectedYear.value}-12-31`
    } else if (timeFilterType.value === 'custom' && customDateRange.value) {
      // 自定义日期区间
      startDate = customDateRange.value[0].toISOString().split('T')[0]
      endDate = customDateRange.value[1].toISOString().split('T')[0]
    } else if (timeFilterType.value === 'all') {
      // 全部数据，不设置日期范围
      startDate = undefined
      endDate = undefined
      console.log('⚠️ 加载全部数据，数据量可能较大')
    } else if (timeFilterType.value !== 'all') {
      // 按快捷时间范围筛选
      endDate = now.toISOString().split('T')[0]
      const start = new Date(now)
      
      switch (timeFilterType.value) {
        case 'recent1month':
          start.setMonth(start.getMonth() - 1)
          break
        case 'recent3months':
          start.setMonth(start.getMonth() - 3)
          break
        case 'recent6months':
          start.setMonth(start.getMonth() - 6)
          break
        case 'recent1year':
          start.setFullYear(start.getFullYear() - 1)
          break
      }
      
      startDate = start.toISOString().split('T')[0]
    }
    
    // 获取历史数据（带时间范围）
    historyData.value = await getMonitoringValues(selectedPoint.value.id, startDate, endDate)
  } catch (error) {
    console.error(error)
    ElMessage.error('加载历史数据失败')
  } finally {
    chartLoading.value = false
  }
}

/**
 * 获取状态样式
 */
function getStatusType(status: string) {
  const map: Record<string, string> = {
    normal: 'success',
    warning: 'warning', 
    danger: 'danger'
  }
  return map[status] || 'info'
}

function getStatusText(status: string) {
  const map: Record<string, string> = {
    normal: '正常',
    warning: '警告',
    danger: '危险'
  }
  return map[status] || status
}

/**
 * 打开新增测值对话框
 */
function openAddValueDialog(point: MonitoringPoint) {
  newValueForm.value.pointId = point.id
  newValueForm.value.value = point.latestValue || 0
  addValueDialogVisible.value = true
}

/**
 * 导出为CSV
 */
function exportToCSV() {
  if (historyData.value.length === 0) {
    ElMessage.warning('暂无数据可导出')
    return
  }
  
  const csvContent = [
    ['测量时间', '测量值(mm)', '测点编号'],
    ...historyData.value.map((d: MonitoringValue) => [
      new Date(d.measuredAt).toLocaleString(),
      d.value,
      selectedPoint.value?.name || ''
    ])
  ].map(row => row.join(',')).join('\n')
  
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `${selectedPoint.value?.name}_历史数据_${new Date().toLocaleDateString()}.csv`
  link.click()
  
  ElMessage.success('CSV导出成功！')
}

/**
 * 导出图表为PNG图片
 */
async function printChart() {
  if (!selectedPoint.value) {
    ElMessage.warning('请先选择测点')
    return
  }
  
  try {
    // 获取图表容器
    const chartContainer = document.querySelector('.chart-container')
    if (!chartContainer) {
      ElMessage.error('未找到图表')
      return
    }
    
    // 使用html2canvas库导出为图片
    const html2canvas = (await import('html2canvas')).default
    const canvas = await html2canvas(chartContainer as HTMLElement, {
      backgroundColor: '#0f172a',
      scale: 2 // 提高清晰度
    })
    
    // 转换为blob并下载
    canvas.toBlob((blob) => {
      if (blob) {
        const link = document.createElement('a')
        link.href = URL.createObjectURL(blob)
        link.download = `${selectedPoint.value?.name}_趋势图_${new Date().toLocaleDateString()}.png`
        link.click()
        ElMessage.success('图表导出成功！')
      }
    })
  } catch (e) {
    console.error('导出失败:', e)
    ElMessage.error('导出失败，请检查浏览器兼容性')
  }
}

/**
 * 提交新测值
 */
async function submitNewValue() {
  try {
    const { pointId, value, measuredAt } = newValueForm.value
    
    // 确保measuredAt是Date对象，然后转换为ISO字符串
    const measuredAtISO = measuredAt instanceof Date 
      ? measuredAt.toISOString() 
      : new Date(measuredAt).toISOString()
    
    await addMonitoringValue(pointId, value, measuredAtISO)
    
    ElMessage.success(`测点 ${pointId} 新增测值成功！`)
    addValueDialogVisible.value = false
    
    // 刷新当前选中的测点数据
    if (selectedPoint.value && selectedPoint.value.id === pointId) {
      await selectPoint(selectedPoint.value)
    }
    // 刷新测点列表（更新最新值）
    await loadPoints()
    
  } catch (error) {
    console.error(error)
    ElMessage.error('提交失败')
  }
}

onMounted(() => {
  loadPoints()
})
</script>

<template>
  <div class="monitor-page">
    <!-- 左侧：测点列表 (比例增大) -->
    <div class="point-list glass-card">
      <div class="list-header">
        <h3 class="section-title">
          <el-icon><List /></el-icon>
          测点列表
          <span class="point-count">共 {{ points.length }} 个测点</span>
        </h3>
        
        <!-- 筛选器 -->
        <div class="filters">
          <el-select v-model="filterType" size="small" style="width: 120px;">
            <el-option 
              v-for="t in pointTypes" 
              :key="t.value" 
              :label="t.label" 
              :value="t.value" 
            />
          </el-select>
          <el-input 
            v-model="searchKeyword" 
            placeholder="搜索测点..." 
            size="small"
            prefix-icon="Search"
            style="width: 150px;"
          />
        </div>
      </div>
      
      <!-- 测点表格 -->
      <el-table 
        :data="filteredPoints" 
        style="width: 100%"
        :row-class-name="({row}) => row.id === selectedPoint?.id ? 'selected-row' : ''"
        @row-click="selectPoint"
        max-height="calc(100vh - 200px)"
      >
        <el-table-column prop="name" label="编号" width="90" />
        <el-table-column prop="typeName" label="类型" width="90" />
        <el-table-column prop="section" label="坝段" width="90" />
        <el-table-column prop="latestValue" label="最新值(mm)">
          <template #default="{ row }">
            <span class="value-highlight">{{ row.latestValue?.toFixed(4) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="60">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="openAddValueDialog(row)">
              <el-icon><Plus /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    
    <!-- 右侧：详情面板 (图表 + 历史列表) -->
    <div class="detail-panel">
      <!-- 测点详情 -->
      <div class="detail-panel glass-card">
        <!-- 时间筛选器 -->
        <div v-if="selectedPoint" class="time-filter-bar">
          <div class="filter-group">
            <span class="filter-label">时间范围：</span>
            <el-radio-group v-model="timeFilterType" size="small" @change="loadHistoryWithFilter">
              <el-radio-button value="recent1month">近1月</el-radio-button>
              <el-radio-button value="recent3months">近3月</el-radio-button>
              <el-radio-button value="recent6months">近6月</el-radio-button>
              <el-radio-button value="recent1year">近1年</el-radio-button>
              <el-radio-button value="all">全部</el-radio-button>
            </el-radio-group>
          </div>
          <div class="filter-group">
            <span class="filter-label">选择年份：</span>
            <el-select v-model="selectedYear" size="small" clearable placeholder="全部年份" @change="loadHistoryWithFilter" style="width: 120px">
              <el-option v-for="year in availableYears" :key="year" :label="`${year}年`" :value="year" />
            </el-select>
          </div>
          <div class="filter-group">
            <span class="filter-label">自定义区间：</span>
            <el-date-picker
              v-model="customDateRange"
              type="daterange"
              range-separator="-"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              style="width: 240px"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              @change="handleCustomDateChange"
            />
          </div>
          <div class="filter-group" style="margin-left: auto">
            <el-button-group size="small">
              <el-button type="primary" @click="exportToCSV">
                <el-icon><Download /></el-icon>
                导出CSV
              </el-button>
              <el-button type="primary" @click="printChart">
                <el-icon><Printer /></el-icon>
                打印
              </el-button>
            </el-button-group>
          </div>
        </div>
        
        <!-- 数据统计栏 -->
        <div v-if="selectedPoint && dataStats" class="data-stats-bar">
          <div class="stat-item">
            <span class="stat-label">📅 数据范围:</span>
            <span class="stat-value">{{ dataStats.startDate }} ~ {{ dataStats.endDate }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">📊 总数据点:</span>
            <span class="stat-value">{{ dataStats.totalPoints }} 条</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">⏱️ 平均间隔:</span>
            <span class="stat-value">{{ dataStats.avgInterval }} 天</span>
          </div>
        </div>
        
        <el-tabs type="border-card" class="monitor-tabs">
          <el-tab-pane>
            <template #label>
              <span class="tab-label"><el-icon><TrendCharts /></el-icon> 趋势分析</span>
            </template>
            <div class="chart-container">
              <v-chart :option="chartOption" autoresize style="height: 400px;" />
            </div>
          </el-tab-pane>
          
          <el-tab-pane>
            <template #label>
              <span class="tab-label"><el-icon><Tickets /></el-icon> 历史数据</span>
            </template>
            <div class="history-table-container">
              <el-table :data="historyData" max-height="400px" style="width: 100%" size="small">
                <el-table-column label="测量时间" width="180">
                  <template #default="{ row }">
                    {{ new Date(row.measuredAt).toLocaleString() }}
                  </template>
                </el-table-column>
                <el-table-column prop="value" label="测量值(mm)">
                  <template #default="{ row }">
                    {{ row.value.toFixed(4) }}
                  </template>
                </el-table-column>
                <el-table-column label="单位" width="60" align="center">
                  <template #default>mm</template>
                </el-table-column>
              </el-table>
            </div>
          </el-tab-pane>
          
          <el-tab-pane v-if="selectedPoint">
            <template #label>
              <span class="tab-label"><el-icon><InfoFilled /></el-icon> 测点详情</span>
            </template>
            <div class="info-grid">
              <div class="info-item">
                <span class="label">仪器编号</span>
                <span class="value">{{ selectedPoint.name }}</span>
              </div>
              <div class="info-item">
                <span class="label">监测类型</span>
                <span class="value">{{ selectedPoint.typeName }}</span>
              </div>
              <div class="info-item">
                <span class="label">平面位置</span>
                <span class="value">{{ selectedPoint.location }}</span>
              </div>
              <div class="info-item">
                <span class="label">高程(m)</span>
                <span class="value">{{ selectedPoint.elevation }}</span>
              </div>
              <div class="info-item">
                <span class="label">所在坝段</span>
                <span class="value">{{ selectedPoint.section }}</span>
              </div>
              <div class="info-item">
                <span class="label">埋设时间</span>
                <span class="value">{{ selectedPoint.installDate }}</span>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
    
    <!-- 新增测值对话框 -->
    <el-dialog 
      v-model="addValueDialogVisible" 
      title="新增测值"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form :model="newValueForm" label-width="80px">
        <el-form-item label="测量值">
          <el-input-number v-model="newValueForm.value" :precision="4" :step="0.01" />
          <span style="margin-left: 8px; color: var(--text-secondary);">mm</span>
        </el-form-item>
        <el-form-item label="测量时间">
          <el-date-picker 
            v-model="newValueForm.measuredAt" 
            type="datetime"
            placeholder="选择时间"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addValueDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitNewValue">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.monitor-page {
  display: grid;
  grid-template-columns: 2fr 3fr; /* 增大左侧比例 */
  gap: 16px;
  height: 100%;
}

.point-list {
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.filters {
  display: flex;
  gap: 8px;
}

.detail-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.detail-card {
  padding: 0;
  overflow: hidden;
  height: 100%;
}

:deep(.monitor-tabs) {
  height: 100%;
  background: transparent !important;
  border: none !important;
}

:deep(.el-tabs__content) {
  padding: 20px;
  background: rgba(13, 33, 55, 0.5) !important;
}

:deep(.el-tabs--border-card > .el-tabs__header) {
  background-color: rgba(30, 41, 59, 0.8) !important;
  border-bottom: 1px solid rgba(0, 212, 255, 0.2) !important;
}

:deep(.el-tabs--border-card > .el-tabs__header .el-tabs__item.is-active) {
  background-color: rgba(13, 33, 55, 0.5) !important;
  color: #00d4ff !important;
  border-right-color: rgba(0, 212, 255, 0.2) !important;
  border-left-color: rgba(0, 212, 255, 0.2) !important;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 6px;
}

.value-highlight {
  color: #00d4ff;
  font-weight: 600;
  font-family: 'Courier New', monospace;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item .label {
  font-size: 12px;
  color: var(--text-secondary);
}

.info-item .value {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  border-bottom: 1px dashed rgba(255,255,255,0.1);
  padding-bottom: 4px;
}

/* 选中行样式 - 增强视觉效果 */
:deep(.selected-row) {
  background: linear-gradient(90deg, rgba(0, 212, 255, 0.25), rgba(0, 212, 255, 0.1)) !important;
  border-left: 3px solid #00d4ff !important;
  box-shadow: 0 0 8px rgba(0, 212, 255, 0.3) !important;
  position: relative;
}

:deep(.selected-row td) {
  font-weight: 600 !important;
}

.point-count {
  margin-left: 12px;
  font-size: 13px;
  color: #00d4ff;
  font-weight: normal;
  padding: 2px 12px;
  background: rgba(0, 212, 255, 0.15);
  border-radius: 12px;
}

/* 时间筛选栏 */
.time-filter-bar {
  display: flex;
  gap: 20px;
  padding: 16px 20px;
  background: rgba(30, 41, 59, 0.5);
  border-bottom: 1px solid rgba(0, 212, 255, 0.2);
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 13px;
  color: #94a3b8;
  white-space: nowrap;
}

:deep(.el-table) {
  background: transparent !important;
}

:deep(.el-table tr) {
  background: transparent !important;
  color: #cbd5e1;
}

:deep(.el-table th.el-table__cell) {
  background: rgba(30, 41, 59, 0.5) !important;
  color: #94a3b8;
}

:deep(.el-table--enable-row-hover .el-table__body tr:hover > td.el-table__cell) {
  background-color: rgba(0, 212, 255, 0.1) !important;
}

/* 数据统计栏 */
.data-stats-bar {
  display: flex;
  gap: 24px;
  padding: 12px 20px;
  background: rgba(0, 212, 255, 0.05);
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.stat-label {
  color: #94a3b8;
}

.stat-value {
  color: #00d4ff;
  font-weight: 600;
  font-family: 'Courier New', monospace;
}

/* 修复弹窗输入框文字在暗色主题下看不清的问题 */
:deep(.el-dialog) {
  --el-text-color-regular: #606266;
  --el-text-color-primary: #303133;
}

:deep(.el-dialog .el-input__inner) {
  color: #333333 !important;
  font-weight: 500;
}

:deep(.el-dialog .el-form-item__label) {
  color: #606266 !important;
}
</style>
