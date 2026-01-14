<!--
  组件名: Analysis.vue
  功能: 智能分析页面 - AI深度学习预测 + 异常检测
  作者: 章涵硕
  特色: 真实的LSTM/Stacking模型预测，带注意力权重可视化
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, RadarChart, HeatmapChart } from 'echarts/charts'
import { ElMessage, ElCollapseTransition } from 'element-plus'
import { 
  TitleComponent, 
  TooltipComponent, 
  LegendComponent,
  GridComponent,
  RadarComponent,
  MarkLineComponent,
  MarkAreaComponent,
  VisualMapComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import * as mlApi from '@/api/ml'
import { supabase } from '@/lib/supabase'
import { VideoPlay, Coin, Connection, Star, StarFilled, List, Delete, CaretRight, CaretBottom, Monitor, Refresh, CircleCheckFilled, CircleCloseFilled, Loading } from '@element-plus/icons-vue'  // 新增图标
import { SystemDiagnostician, type DiagnosticResult } from '@/utils/diagnostics'

// 注册 ECharts
use([
  CanvasRenderer, LineChart, BarChart, RadarChart, HeatmapChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent,
  RadarComponent, MarkLineComponent, MarkAreaComponent, VisualMapComponent
])

// === 状态变量 ===
const loading = ref(true)
const mlBackendAvailable = ref(false)
const predicting = ref(false)
const predictProgress = ref(0)
const predictionMode = ref('realtime') // 'realtime' | 'database'
const trainLoading = ref(false)

// 自检系统
const showDiagnostics = ref(false)
const diagnosticResults = ref<DiagnosticResult[]>([])
const diagnostician = new SystemDiagnostician((results) => {
  diagnosticResults.value = results
})

function runDiagnostics() {
  showDiagnostics.value = true
  diagnostician.runDiagnostics()
}

// 折叠状态
const showFusionDetails = ref(true)
const showAnomalyDetails = ref(true)



// 测点数据
const allPoints = ref<string[]>([])
const selectedPoint = ref('')
const pointsGrouped = ref<Record<string, string[]>>({})
const selectedType = ref('all')

// 预测参数
const predictSteps = ref(30)

// 时间筛选
const timeFilterType = ref('recent6months') // recent1month, recent3months, recent6months, recent1year, all, custom
const customDateRange = ref<[Date, Date] | null>(null)

// 预测结果
const predictionResult = ref<mlApi.PredictionResult | null>(null)
const isResultSaved = ref(false) // 当前结果是否已保存

// 历史记录
const historyDrawerVisible = ref(false)
const savedPredictions = ref<any[]>([])
const loadingHistory = ref(false)

// 异常检测结果
const anomalyResults = ref<mlApi.AnomalyResult[]>([])
const anomalySummary = ref({ high: 0, medium: 0, low: 0 })

// 雷达图数据
const radarData = ref([5, 5, 5, 5, 5])

// === 初始化加载 ===
async function loadData() {
  loading.value = true
  
  try {
    // 检查ML后端是否可用
    mlBackendAvailable.value = await mlApi.checkMLBackend()
    
    if (mlBackendAvailable.value) {
      // 从ML后端加载数据
      const pointsData = await mlApi.getPoints()
      allPoints.value = pointsData.all_points
      pointsGrouped.value = pointsData.grouped
      
      // 默认选择第一个测点
      if (allPoints.value.length > 0) {
        selectedPoint.value = allPoints.value[0] || ''
      }
      
      // 加载异常检测结果
      await loadAnomalies()
      
    } else {
      // ML后端不可用时使用模拟数据
      allPoints.value = ['EX1-4', 'TC1-5', 'IP3左右岸']
      
      // 使用模拟异常数据
      anomalyResults.value = [
        { point_name: 'EX1-4', type: 'tension_wire', current_value: 3.45, mean: 2.8, std: 0.3, z_score: 2.17, change_rate: 0.15, severity: 'medium', measure_time: '2024-12-20' },
        { point_name: 'TC1-5', type: 'hydrostatic', current_value: 0.96, mean: 0.5, std: 0.2, z_score: 2.3, change_rate: 0.08, severity: 'medium', measure_time: '2024-12-20' }
      ]
    }
    
    // 更新雷达图
    updateRadarData()
    
  } catch (error) {
    console.error('加载分析数据失败:', error)
    ElMessage.error('加载失败，请检查后端服务')
  } finally {
    loading.value = false
  }
}

// 加载异常检测
async function loadAnomalies() {
  try {
    const result = await mlApi.detectAnomalies()
    anomalyResults.value = result.anomalies
    anomalySummary.value = result.by_severity
  } catch (e) {
    console.error('异常检测失败:', e)
  }
}

// 更新雷达图
function updateRadarData() {
  const types = ['tension_wire', 'hydrostatic', 'plumb_line']
  const scores = types.map((type: string) => {
    const typeAnomalies = anomalyResults.value.filter((a: mlApi.AnomalyResult) => a.type === type)
    if (typeAnomalies.length === 0) return 5
    const avgZScore = typeAnomalies.reduce((sum: number, a: mlApi.AnomalyResult) => sum + a.z_score, 0) / typeAnomalies.length
    return Math.max(0, 5 - avgZScore)
  })
  radarData.value = [...scores, 4.8, 4.9]  // 渗流量和温度模拟
}

// === 预测功能 ===
function validateInput() {
  if (!selectedPoint.value) {
    ElMessage.warning('请先选择测点')
    return false
  }
  if (timeFilterType.value === 'custom' && !customDateRange.value) {
    ElMessage.warning('请选择自定义时间范围')
    return false
  }
  return true
}

async function runPrediction() {
  if (!validateInput()) return
  
  // 数据库模式：极速查询
  if (predictionMode.value === 'database') {
    loading.value = true
    try {
      const result = await mlApi.getCachedPrediction(selectedPoint.value)
      
      if (!result) throw new Error('未找到该测点的预计算数据，请先执行“全量训练”')
      
      // 构造完整结果结构
      // 注意：这里简化处理，实际项目应确保getCachedPrediction返回完整PredictionResult结构
      // 或者在此处进行必要的补全
      // 由于API返回结构可能与PredictionResult不完全一致，这里做简单兼容
      predictionResult.value = result as any 
      ElMessage.success(`⚡ 已从数据库秒级加载预测结果 (预测时间: ${new Date(result.predicted_at).toLocaleString()})`)
    } catch (e: any) {
      ElMessage.error(e.message)
    } finally {
      loading.value = false
    }
    return
  }
  
  // 实时模式：深度计算
  predicting.value = true
  predictProgress.value = 0
  
  try {
    // 模拟进度
    const progressInterval = setInterval(() => {
      if (predictProgress.value < 80) {
        predictProgress.value += Math.random() * 15
      }
    }, 200)

    // 1. 获取历史数据（根据时间筛选）
    let recentHistory: { measure_time: string; value: number }[] = []
    try {
      //计算日期范围
      let startDate: string | undefined
      let endDate: string | undefined
      const now = new Date()
      
      if (timeFilterType.value === 'custom' && customDateRange.value) {
        startDate = customDateRange.value[0].toISOString().split('T')[0]
        endDate = customDateRange.value[1].toISOString().split('T')[0]
      } else if (timeFilterType.value !== 'all') {
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
      // 如果是'all'，startDate和endDate都是undefined，查询全部数据
      
      let query = supabase
        .from('monitoring_data')
        .select('measure_time, value')
        .eq('point_name', selectedPoint.value)
        .order('measure_time', { ascending: true })
      
      // 添加日期范围过滤
      if (startDate) query = query.gte('measure_time', startDate)
      if (endDate) query = query.lte('measure_time', endDate)
      
      const { data: dbData } = await query
      
      if (dbData && dbData.length > 0) {
        recentHistory = dbData.map((d: any) => ({
          measure_time: d.measure_time,
          value: d.value
        }))
        console.log(`已获取 ${recentHistory.length} 条历史数据 (${timeFilterType.value})用于预测`)
      }
    } catch (e) {
      console.warn('获取历史数据失败，将使用后端默认数据', e)
    }
    
    // 2. 调用预测API
    const result = await mlApi.predictPoint(selectedPoint.value, predictSteps.value, recentHistory)
    
    clearInterval(progressInterval)
    predictProgress.value = 100
    
    predictionResult.value = result
    
    ElMessage.success(`预测完成！使用模型: LSTM(${(result.weights.lstm * 100).toFixed(0)}%) + Stacking(${(result.weights.stacking * 100).toFixed(0)}%)`)
    
  } catch (error: any) {
    ElMessage.error(`预测失败: ${error.message || error}`)
  } finally {
    predicting.value = false
  }
}

// 触发全量训练
async function triggerBatchTrain() {
  try {
    trainLoading.value = true
    const res = await mlApi.triggerBatchTrainAndStore()
    ElMessage.success(`🚀 ${res.message} (共 ${res.total_points} 个测点)`)
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    trainLoading.value = false
  }
}

// === 结果保存与历史 ===

async function saveCurrentResult() {
  if (!predictionResult.value) return
  
  try {
    loading.value = true
    await mlApi.savePrediction({
      point_name: predictionResult.value.point_name,
      predict_steps: predictSteps.value,
      result_json: predictionResult.value,
      input_range: timeFilterType.value,
      is_favorite: true
    })
    isResultSaved.value = true
    ElMessage.success('已保存到收藏夹')
    loadHistory() // 刷新列表
  } catch (e: any) {
    ElMessage.error(`保存失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  try {
    loadingHistory.value = true
    const list = await mlApi.getPredictionHistory({ is_favorite: true, limit: 50 })
    savedPredictions.value = list
  } catch (e) {
    console.error(e)
  } finally {
    loadingHistory.value = false
  }
}

function openHistory() {
  historyDrawerVisible.value = true
  loadHistory()
}

function viewHistoryItem(item: any) {
  // 加载历史记录到当前视图
  predictionResult.value = item.result_json
  isResultSaved.value = true // 既然是历史记录，肯定是已保存的
  historyDrawerVisible.value = false
  ElMessage.success(`已加载 ${item.point_name} 的历史预测`)
}

async function removeHistoryItem(item: any) {
  try {
    await mlApi.toggleFavorite(item.id, false)
    ElMessage.success('已取消收藏')
    loadHistory()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}





// === 图表配置 ===

// 预测曲线图
const predictionChartOption = computed(() => {
  if (!predictionResult.value) {
    return {
      title: { text: '选择测点并点击预测', textStyle: { color: '#94a3b8' }, left: 'center', top: 'center' }
    }
  }
  
  const r = predictionResult.value
  const historyLen = r.history.length
  
  // X轴：历史日期 + 未来日期
  const dates = [...r.dates]
  for (let i = 1; i <= r.predictions.length; i++) {
    dates.push(`+${i}天`)
  }
  
  // 历史数据系列
  const historyData = [...r.history, ...Array(r.predictions.length).fill(null)]
  
  // 预测数据系列（与历史最后一点连接）
  const predData = [...Array(historyLen - 1).fill(null), r.history[historyLen - 1], ...r.predictions]
  
  // 置信区间
  const upperData = r.confidence_upper.length > 0 
    ? [...Array(historyLen).fill(null), ...r.confidence_upper]
    : []
  const lowerData = r.confidence_lower.length > 0 
    ? [...Array(historyLen).fill(null), ...r.confidence_lower]
    : []
  
  return {
    backgroundColor: 'transparent',
    title: {
      text: `${r.point_name} 深度学习预测 (${r.type})`,
      subtext: `LSTM权重: ${(r.weights.lstm * 100).toFixed(0)}% | Stacking权重: ${(r.weights.stacking * 100).toFixed(0)}%`,
      textStyle: { color: '#f8fafc', fontSize: 16 },
      subtextStyle: { color: '#94a3b8' },
      left: 'center'
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17, 34, 64, 0.95)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: '#f8fafc' }
    },
    toolbox: {
      show: true,
      feature: {
        saveAsImage: { show: true, title: '保存图片', backgroundColor: '#0f172a' },
        dataZoom: { show: true },
        restore: { show: true }
      },
      iconStyle: { borderColor: '#94a3b8' },
      right: 20
    },
    legend: {
      data: ['历史数据', 'AI预测', '置信上界', '置信下界'],
      bottom: 0,
      textStyle: { color: '#94a3b8' }
    },
    grid: { top: 80, left: 60, right: 30, bottom: 60 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
      axisLabel: { color: '#94a3b8', rotate: 45 }
    },
    yAxis: {
      type: 'value',
      name: '监测值',
      nameTextStyle: { color: '#94a3b8' },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
      axisLabel: { color: '#94a3b8' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
    },
    series: [
      {
        name: '历史数据',
        type: 'line',
        data: historyData,
        lineStyle: { color: '#00d4ff', width: 2 },
        itemStyle: { color: '#00d4ff' },
        symbol: 'circle',
        symbolSize: 4
      },
      {
        name: 'AI预测',
        type: 'line',
        data: predData,
        lineStyle: { color: '#f59e0b', width: 3, type: 'dashed' },
        itemStyle: { color: '#f59e0b' },
        symbol: 'diamond',
        symbolSize: 8
      },
      {
        name: '置信上界',
        type: 'line',
        data: upperData,
        lineStyle: { opacity: 0 },
        areaStyle: { color: 'rgba(245, 158, 11, 0.15)' },
        symbol: 'none',
        stack: 'confidence'
      },
      {
        name: '置信下界',
        type: 'line',
        data: lowerData,
        lineStyle: { color: 'rgba(245, 158, 11, 0.3)', type: 'dotted' },
        symbol: 'none'
      }
    ]
  }
})

// 注意力权重图
const attentionChartOption = computed(() => {
  if (!predictionResult.value?.attention_weights) {
    return { title: { text: '注意力权重', textStyle: { color: '#94a3b8' }, left: 'center' } }
  }
  
  const weights = predictionResult.value.attention_weights
  
  return {
    backgroundColor: 'transparent',
    title: {
      text: '时序注意力权重',
      textStyle: { color: '#f8fafc', fontSize: 14 },
      left: 'center'
    },
    tooltip: { trigger: 'axis' },
    toolbox: {
      show: true,
      feature: { saveAsImage: { show: true, title: '保存', backgroundColor: '#0f172a' } },
      iconStyle: { borderColor: '#94a3b8' },
      right: 0
    },
    grid: { top: 50, left: 40, right: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: weights.map((_: number, i: number) => `T-${weights.length - i}`),
      axisLabel: { color: '#94a3b8' }
    },
    yAxis: {
      type: 'value',
      show: false
    },
    series: [{
      type: 'bar',
      data: weights,
      itemStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: '#00d4ff' },
            { offset: 1, color: '#0066ff' }
          ]
        }
      },
      barWidth: '60%'
    }]
  }
})

// 雷达图
const radarChartOption = computed(() => ({
  backgroundColor: 'transparent',
  title: {
    text: '综合健康评估',
    textStyle: { color: '#f8fafc', fontSize: 14 },
    left: 'center'
  },
  tooltip: {},
  radar: {
    indicator: [
      { name: '引张线', max: 5 },
      { name: '静力水准', max: 5 },
      { name: '倒垂线', max: 5 },
      { name: '渗流量', max: 5 },
      { name: '温度', max: 5 }
    ],
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisName: { color: '#94a3b8' }
  },
  series: [{
    type: 'radar',
    data: [{
      value: radarData.value,
      name: '健康得分',
      areaStyle: { color: 'rgba(0, 212, 255, 0.3)' },
      lineStyle: { color: '#00d4ff', width: 2 },
      itemStyle: { color: '#00d4ff' }
    }]
  }]
}))

// === 辅助方法 ===
function getSeverityClass(severity: string) {
  const map: Record<string, string> = {
    low: 'status-tag--success',
    medium: 'status-tag--warning',
    high: 'status-tag--danger'
  }
  return `status-tag ${map[severity]}`
}

function getSeverityText(severity: string) {
  const map: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险'
  }
  return map[severity] || severity
}

function getTypeLabel(type: string) {
  const map: Record<string, string> = {
    tension_wire: '引张线',
    hydrostatic: '静力水准',
    plumb_line: '倒垂线'
  }
  return map[type] || type
}

// 过滤后的测点列表
const filteredPoints = computed(() => {
  if (selectedType.value === 'all') return allPoints.value
  return pointsGrouped.value[selectedType.value] || []
})

// 处理类型变化
function handleTypeChange() {
  if (filteredPoints.value.length > 0 && !filteredPoints.value.includes(selectedPoint.value)) {
    selectedPoint.value = filteredPoints.value[0] || ''
  }
}

// 处理自定义日期变化
function handleCustomDateChange(value: [Date, Date] | null) {
  if (value) {
    timeFilterType.value = 'custom'
  }
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="analysis-page">
    <!-- 顶部：AI预测控制面板 -->
    <div class="control-panel glass-card">
      <div class="panel-header">
        <div class="panel-title">
          <el-icon :size="24" color="var(--accent)"><MagicStick /></el-icon>
          <div>
            <h2>AI 深度学习预测</h2>
            <p v-if="mlBackendAvailable" class="status-ok">
              <el-icon><CircleCheck /></el-icon> ML后端已连接
            </p>
            <p v-else class="status-warn">
              <el-icon><Warning /></el-icon> ML后端未连接，使用模拟数据
            </p>
          </div>
        </div>
        
        <div class="tech-tags">
          <span class="tech-tag">BiLSTM + Attention</span>
          <span class="tech-tag">Stacking集成</span>
          <span class="tech-tag">动态权重融合</span>
        </div>
        
        <div class="header-actions">
           <el-button @click="runDiagnostics" type="primary" plain size="small" style="margin-right: 8px;">
             <el-icon style="margin-right: 4px;"><Monitor /></el-icon>系统自检
           </el-button>
           <el-button @click="openHistory" circle>
             <el-icon><List /></el-icon>
           </el-button>
        </div>
      </div>

      
      <!-- 控制区域 -->
      <div class="controls-grid">
        <!-- 基础配置区 -->
        <div class="control-group">
          <div class="control-item">
            <label>监测类型</label>
            <el-select v-model="selectedType" @change="handleTypeChange" style="width: 140px">
              <el-option label="全部类型" value="all" />
              <el-option label="引张线" value="tension_wire" />
              <el-option label="静力水准" value="hydrostatic" />
              <el-option label="倒垂线" value="plumb_line" />
            </el-select>
          </div>
          
          <div class="control-item flex-grow">
            <label>选择测点</label>
            <el-select v-model="selectedPoint" filterable placeholder="输入或选择测点" style="width: 100%" :disabled="loading">
              <el-option 
                v-for="point in filteredPoints" 
                :key="point" 
                :label="point" 
                :value="point" 
              />
            </el-select>
          </div>
        </div>
        
        <!-- 高级参数区 -->
        <div class="control-group">
          <div class="control-item">
            <label>预测视野 ({{ predictSteps }}天)</label>
            <el-slider 
              v-model="predictSteps" 
              :min="7" 
              :max="90" 
              :step="7"
              :show-tooltip="false"
              style="width: 180px"
            />
          </div>
          
          <div class="control-item">
            <label>算力模式</label>
            <el-radio-group v-model="predictionMode" size="default">
              <el-radio-button label="realtime">实时算力</el-radio-button>
              <el-radio-button label="database">数据库</el-radio-button>
            </el-radio-group>
          </div>

          <div class="action-buttons">
            <el-button 
              v-if="predictionMode === 'database'"
              type="success"
              plain
              :loading="trainLoading"
              @click="triggerBatchTrain"
            >
              🚀 全量训练
            </el-button>
            
            <el-button 
              type="primary" 
              class="predict-btn"
              size="large"
              :loading="predicting || loading"
              :disabled="!selectedPoint || (loading && predictionMode === 'database')"
              @click="runPrediction"
            >
              <el-icon v-if="!predicting"><Position /></el-icon>
              {{ predicting ? `计算中 ${predictProgress.toFixed(0)}%` : '启动预测' }}
            </el-button>
          </div>
          
          <!-- 保存按钮 (仅当有结果时显示) -->
          <div class="save-actions" v-if="predictionResult">
             <el-button 
               :type="isResultSaved ? 'warning' : 'default'" 
               :icon="isResultSaved ? StarFilled : Star"
               circle
               @click="saveCurrentResult"
               :disabled="isResultSaved"
               title="收藏当前结果"
             />
          </div>
        </div>
      </div>
      
      <!-- 进度条 -->
      <el-progress 
        v-if="predicting" 
        :percentage="predictProgress" 
        :stroke-width="4"
        :show-text="false"
        style="margin-top: 12px"
      />
    </div>
    
    <!-- 时间筛选栏 -->
    <div v-if="selectedPoint" class="time-filter-section glass-card">
      <div class="filter-row">
        <div class="filter-group">
          <span class="filter-label">📅 历史数据范围：</span>
          <el-radio-group v-model="timeFilterType" size="small">
            <el-radio-button value="recent1month">近1月</el-radio-button>
            <el-radio-button value="recent3months">近3月</el-radio-button>
            <el-radio-button value="recent6months">近6月</el-radio-button>
            <el-radio-button value="recent1year">近1年</el-radio-button>
            <el-radio-button value="all">全部</el-radio-button>
          </el-radio-group>
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
        
        <div class="filter-hint">
          <el-icon><InfoFilled /></el-icon>
          选择时间范围后，点击"启动预测"加载对应数据
        </div>
      </div>
    </div>
    
    <!-- 预测前的空状态 -->
    <div v-if="!predictionResult" class="empty-state glass-card">
      <el-empty description="请选择测点并点击“启动预测”" :image-size="160">
        <template #image>
          <el-icon :size="80" color="var(--accent-glow)"><DataAnalysis /></el-icon>
        </template>
      </el-empty>
    </div>

    <!-- 中部：图表区域 -->
    <div v-if="predictionResult" class="charts-grid">
      <!-- 预测曲线 -->
      <div class="chart-card glass-card main-chart">
        <v-chart :option="predictionChartOption" autoresize style="height: 320px;" />
      </div>
      
      <!-- 右侧小图表 -->
      <div class="side-charts">
        <!-- 注意力权重 -->
        <div class="chart-card glass-card">
          <v-chart :option="attentionChartOption" autoresize style="height: 150px;" />
        </div>
        
        <!-- 雷达图 -->
        <div class="chart-card glass-card">
          <v-chart :option="radarChartOption" autoresize style="height: 180px;" />
        </div>
      </div>
    </div>
    
    <!-- 融合详情卡片 -->
    <div v-if="predictionResult?.fusion_details" class="fusion-details glass-card">
      <div class="section-header clickable" @click="showFusionDetails = !showFusionDetails">
        <h3 class="section-title">
          <el-icon :class="{ 'rotate-icon': showFusionDetails }"><CaretRight /></el-icon>
          <el-icon><Operation /></el-icon>
          三层动态权重融合详情
        </h3>
      </div>
      
      <el-collapse-transition>
        <div v-show="showFusionDetails" class="fusion-grid">
          <!-- 全局权重 -->
          <div class="fusion-card">
            <div class="fusion-label">🌍 全局权重</div>
            <div class="fusion-values">
              <div class="weight-item">
                <span>LSTM</span>
                <el-progress 
                  :percentage="(predictionResult.fusion_details.global_weights?.lstm || 0.45) * 100"
                  :stroke-width="12"
                  :color="'#00d4ff'"
                />
              </div>
              <div class="weight-item">
                <span>Stacking</span>
                <el-progress 
                  :percentage="(predictionResult.fusion_details.global_weights?.stacking || 0.55) * 100"
                  :stroke-width="12"
                  :color="'#f59e0b'"
                />
              </div>
            </div>
          </div>
          
          <!-- 局部权重 -->
          <div class="fusion-card">
            <div class="fusion-label">📍 局部权重 (趋势一致性)</div>
            <div class="fusion-values">
              <div class="weight-item">
                <span>LSTM</span>
                <el-progress 
                  :percentage="(predictionResult.fusion_details.local_weights?.lstm || 0.5) * 100"
                  :stroke-width="12"
                  :color="'#00d4ff'"
                />
              </div>
              <div class="weight-item">
                <span>Stacking</span>
                <el-progress 
                  :percentage="(predictionResult.fusion_details.local_weights?.stacking || 0.5) * 100"
                  :stroke-width="12"
                  :color="'#f59e0b'"
                />
              </div>
            </div>
          </div>
          
          <!-- 置信度权重 -->
          <div class="fusion-card">
            <div class="fusion-label">🎯 置信度权重</div>
            <div class="fusion-values">
              <div class="weight-item">
                <span>LSTM</span>
                <el-progress 
                  :percentage="(predictionResult.fusion_details.confidence_weights?.lstm || 0.5) * 100"
                  :stroke-width="12"
                  :color="'#00d4ff'"
                />
              </div>
              <div class="weight-item">
                <span>Stacking</span>
                <el-progress 
                  :percentage="(predictionResult.fusion_details.confidence_weights?.stacking || 0.5) * 100"
                  :stroke-width="12"
                  :color="'#f59e0b'"
                />
              </div>
            </div>
          </div>
          
          <!-- 统计信息 -->
          <div class="fusion-card stats">
            <div class="stat-item">
              <div class="stat-value">{{ ((predictionResult.fusion_details.model_consistency || 0) * 100).toFixed(1) }}%</div>
              <div class="stat-label">模型一致性</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ (predictionResult.fusion_details.uncertainty_std || 0).toFixed(4) }}</div>
              <div class="stat-label">不确定性σ</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ ((predictionResult.weights?.lstm || 0) * 100).toFixed(0) }}% : {{ ((predictionResult.weights?.stacking || 0) * 100).toFixed(0) }}%</div>
              <div class="stat-label">最终权重</div>
            </div>
          </div>
        </div>
      </el-collapse-transition>
    </div>
    
    <!-- 底部：异常检测结果表 (始终显示) -->
    <div class="anomaly-section glass-card" style="margin-top: auto;">
      <div class="section-header clickable" @click="showAnomalyDetails = !showAnomalyDetails">
        <h3 class="section-title">
          <el-icon :class="{ 'rotate-icon': showAnomalyDetails }"><CaretRight /></el-icon>
          <el-icon><Warning /></el-icon>
          AI异常检测结果
        </h3>
        <div class="anomaly-summary">
          <span class="summary-item high">高风险: {{ anomalySummary.high }}</span>
          <span class="summary-item medium">中风险: {{ anomalySummary.medium }}</span>
          <span class="summary-item low">低风险: {{ anomalySummary.low }}</span>
        </div>
      </div>
      
      <el-collapse-transition>
        <div v-show="showAnomalyDetails">
          <el-table 
            v-if="anomalyResults.length > 0"
            :data="anomalyResults.slice(0, 10)" 
            style="width: 100%; background: transparent;" 
            :header-cell-style="{ background: 'transparent', color: '#94a3b8' }"
            :cell-style="{ background: 'transparent', color: '#f8fafc' }"
          >
            <el-table-column prop="point_name" label="测点" width="100" />
            <el-table-column prop="type" label="类型" width="100">
              <template #default="{ row }">
                {{ getTypeLabel(row.type) }}
              </template>
            </el-table-column>
            <el-table-column prop="current_value" label="当前值" width="100">
              <template #default="{ row }">
                <span style="font-weight: 600;">{{ row.current_value.toFixed(3) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="异常评分" width="100">
              <template #default="{ row }">
                <span :style="{ color: row.z_score > 2 ? 'var(--danger)' : 'var(--warning)' }">
                  {{ row.z_score.toFixed(2) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="severity" label="风险等级" width="100">
              <template #default="{ row }">
                <span :class="getSeverityClass(row.severity)">
                  {{ getSeverityText(row.severity) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="measure_time" label="检测时间" />
          </el-table>
          
          <div v-else class="empty-text">
            暂无异常检测结果
          </div>
        </div>
      </el-collapse-transition>
    </div>

  
  <!-- 历史记录抽屉 -->
  <el-drawer v-model="historyDrawerVisible" title="预测收藏夹" size="30%">
    <div v-loading="loadingHistory" class="history-list">
      <div v-if="savedPredictions.length === 0" class="empty-history">
        暂无收藏记录
      </div>
      
      <div 
        v-for="item in savedPredictions" 
        :key="item.id" 
        class="history-item"
        @click="viewHistoryItem(item)"
      >
        <div class="history-header">
          <span class="point-name">{{ item.point_name }}</span>
          <span class="history-time">{{ new Date(item.created_at).toLocaleString() }}</span>
        </div>
        <div class="history-meta">
          <span>{{ item.predict_steps }}步预测</span>
          <el-button 
            type="danger" 
            link 
            :icon="Delete" 
            @click.stop="removeHistoryItem(item)"
          />
        </div>
      </div>
    </div>
  </el-drawer>

  <!-- 自检报告弹窗 -->
  <el-dialog
    v-model="showDiagnostics"
    title="系统功能自检报告"
    width="500px"
    center
    append-to-body
  >
    <div class="diagnostic-list">
      <div 
        v-for="item in diagnosticResults" 
        :key="item.id" 
        class="diagnostic-item"
      >
        <div class="diag-icon">
          <el-icon v-if="item.status === 'pending'" class="is-pending"><MoreFilled /></el-icon>
          <el-icon v-else-if="item.status === 'running'" class="is-loading"><Loading /></el-icon>
          <el-icon v-else-if="item.status === 'success'" color="var(--success)"><CircleCheckFilled /></el-icon>
          <el-icon v-else color="var(--danger)"><CircleCloseFilled /></el-icon>
        </div>
        <div class="diag-content">
          <div class="diag-name">{{ item.name }}</div>
          <div v-if="item.message" class="diag-msg" :class="item.status">{{ item.message }}</div>
        </div>
        <div class="diag-status">
          <el-tag v-if="item.status === 'pending'" type="info" size="small">等待中</el-tag>
          <el-tag v-else-if="item.status === 'running'" type="primary" size="small">检测中</el-tag>
          <el-tag v-else-if="item.status === 'success'" type="success" size="small">通过</el-tag>
          <el-tag v-else type="danger" size="small">失败</el-tag>
        </div>
      </div>
    </div>
    <template #footer>
      <span class="dialog-footer">
        <el-button type="primary" @click="showDiagnostics = false">关闭</el-button>
      </span>
    </template>
  </el-dialog>
  </div>
</template>

<style scoped>
.analysis-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  /* height: 100%;  <-- Removed to let Layout handle scrolling */
  /* overflow-y: auto; <-- Removed to avoid nested scrollbars */
  padding-bottom: 24px;
}



/* 控制面板 */
.control-panel {
  padding: 24px;
  position: sticky; /* 改为粘性定位 */
  top: 0;
  z-index: 100; /* 极高层级 */
  background: var(--primary); /* 增加背景不透明度防止透视 */
  border-bottom: 2px solid var(--border-accent);
  overflow: visible;
  flex-shrink: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

/* 布局逻辑 */
.controls-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.control-group {
  display: flex;
  align-items: flex-end;
  gap: 24px;
  flex-wrap: wrap;
}

.control-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.history-item:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--accent);
}

.history-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.point-name {
  font-weight: bold;
  color: var(--accent);
}

.history-time {
  font-size: 12px;
  color: #94a3b8;
}

.history-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #cbd5e1;
}

.save-actions {
  display: flex;
  align-items: center;
  margin-left: 10px;
}


.control-item label {
  font-size: 13px;
  color: var(--text-secondary);
}

.flex-grow {
  flex: 1;
  min-width: 200px;
}

.action-buttons {
  margin-left: auto;
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.predict-btn {
  min-width: 160px;
  font-weight: 600;
  letter-spacing: 1px;
}


/* 空状态 */
.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px dashed var(--border-accent);
}

/* 图表区域 */
.charts-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  margin-top: 10px; /* 强制间距 */
  z-index: 1;
  position: relative;
}

.main-chart {
  padding: 16px;
}

.side-charts {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chart-card {
  padding: 12px;
}

/* 异常检测区域 */
.anomaly-section {
  padding: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
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

.anomaly-summary {
  display: flex;
  gap: 16px;
}

.summary-item {
  font-size: 13px;
  font-weight: 500;
}

.summary-item.high { color: var(--danger); }
.summary-item.medium { color: var(--warning); }
.summary-item.low { color: var(--success); }

/* 状态标签 */
.status-tag {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.status-tag--success {
  background: rgba(34, 197, 94, 0.15);
  color: var(--success);
}

.status-tag--warning {
  background: rgba(245, 158, 11, 0.15);
  color: var(--warning);
}

.status-tag--danger {
  background: rgba(239, 68, 68, 0.15);
  color: var(--danger);
}

/* 融合详情样式 */
.fusion-details {
  padding: 20px;
  margin-top: 16px;
}

.fusion-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.fusion-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 16px;
}

.fusion-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
  font-weight: 500;
}

.fusion-values {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.weight-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.weight-item span {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 60px;
}

.weight-item .el-progress {
  flex: 1;
}

.fusion-card.stats {
  display: flex;
  justify-content: space-around;
  align-items: center;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 4px;
}

.stat-label {
  font-size: 11px;
  color: var(--text-secondary);
}

@media (max-width: 1200px) {
  .fusion-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* === 高级视觉效果 === */

/* 卡片悬停发光效果 */
.glass-card {
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.glass-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  border-color: rgba(255, 255, 255, 0.15);
}

.glass-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.05),
    transparent
  );
  transition: 0.5s;
  pointer-events: none; /* 防止遮挡点击事件 */
  z-index: 0;
}

.glass-card:hover::before {
  left: 100%;
}

/* 确保内容在遮罩层之上 */
.glass-card > * {
  position: relative;
  z-index: 1;
}

/* 统计数字科技感字体 */
.stat-value, .summary-item {
  font-feature-settings: "tnum";
  font-variant-numeric: tabular-nums;
}

/* 进度条动画 */
.el-progress-bar__inner {
  transition: width 1s ease-in-out !important;
  position: relative;
  overflow: hidden;
}

.el-progress-bar__inner::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  right: 0;
  background-image: linear-gradient(
    -45deg,
    rgba(255, 255, 255, 0.15) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255, 255, 255, 0.15) 50%,
    rgba(255, 255, 255, 0.15) 75%,
    transparent 75%,
    transparent
  );
  background-size: 20px 20px;
  animation: progress-stripes 2s linear infinite;
}

@keyframes progress-stripes {
  0% { background-position: 0 0; }
  100% { background-position: 20px 20px; }
}

/* 页面进入动画 */
.analysis-page > div {
  animation: fade-in-up 0.6s ease-out forwards;
  opacity: 0;
}

.analysis-page > div:nth-child(1) { animation-delay: 0.1s; }
.analysis-page > div:nth-child(2) { animation-delay: 0.2s; }
.analysis-page > div:nth-child(3) { animation-delay: 0.3s; }
.analysis-page > div:nth-child(4) { animation-delay: 0.4s; }

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 时间筛选栏样式 */
.time-filter-section {
  padding: 16px 24px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-label {
  font-size: 14px;
  color: #94a3b8;
  white-space: nowrap;
  font-weight: 500;
}

.filter-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-size: 13px;
  color: #64748b;
  font-style: italic;
}

/* 折叠交互样式 */
.clickable {
  cursor: pointer;
  user-select: none;
  transition: opacity 0.2s;
}

.clickable:hover {
  opacity: 0.8;
}

.rotate-icon {
  transform: rotate(90deg);
  transition: transform 0.3s;
}

.empty-text {
  text-align: center;
  padding: 20px;
  color: var(--text-secondary);
  font-size: 14px;
}

/* 诊断弹窗样式 */
.diagnostic-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.diagnostic-item {
  display: flex;
  align-items: center;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  gap: 12px;
}

.diag-icon {
  display: flex;
  align-items: center;
  font-size: 20px;
}

.diag-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.diag-name {
  font-weight: 500;
  color: var(--text-primary);
}

.diag-msg {
  font-size: 12px;
  color: var(--text-secondary);
}

.diag-msg.success { color: var(--success); }
.diag-msg.failure { color: var(--danger); }
</style>
