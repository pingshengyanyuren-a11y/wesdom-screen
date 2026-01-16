<!--
  组件名: BigScreen.vue
  功能: 专业级智慧水利可视化大屏
  作者: 章涵硕
  特色: 全屏3D模型 + 数据面板 + 测点交互 + 实时动画
-->
<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import * as Cesium from 'cesium'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, GaugeChart } from 'echarts/charts'
import { 
  TitleComponent, 
  TooltipComponent, 
  GridComponent,
  LegendComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import { supabase } from '@/lib/supabase'
import ifcPointsData from '@/data/ifc_points.json'
import * as mlApi from '@/api/ml'
import { predictPoint } from '@/api/ml'

// 注册 ECharts
use([CanvasRenderer, LineChart, BarChart, GaugeChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

// Cesium
let viewer: Cesium.Viewer | null = null
const cesiumContainer = ref<HTMLDivElement>()
const loading = ref(true)

// 当前时间
const currentTime = ref('')

// ML 后端连接状态
const mlBackendConnected = ref(false)

// 预测标签页状态
const predictionTab = ref('chart')

// 历史数据标签页状态
const historyTab = ref('chart')

// 选中的测点（增强版 - 支持真实历史数据和预测）
const selectedPoint = ref<{
  id: string
  name: string
  type: string
  value: number
  status: string
  // 真实历史数据
  historyData: { dates: string[], values: number[] } | null
  // 预测数据
  prediction: { 
    dates: string[], 
    values: number[], 
    upper: number[], 
    lower: number[] 
  } | null
  // 加载状态
  loadingHistory: boolean
  loadingPrediction: boolean
} | null>(null)

// 测点数据（从数据库加载全部47个）
const monitoringPoints = ref<Array<{
  id: string
  name: string
  type: string
  value: number
  status: string
  lon: number
  lat: number
  height: number
  ifcData?: any // 关联的 IFC 数据
}>>([])

// 测点真实 3D 位置映射（从模型点击中动态收集）
// key: 测点名称 (如 EX1, IP2), value: Cartesian3 位置
const pointRealPositions = ref<Map<string, Cesium.Cartesian3>>(new Map())

// 选中的IFC建筑构件（非测点元素,如坝段、闸门等）
const selectedBuilding = ref<{
  name: string
  tag: string
  className: string
  properties: Record<string, any>
} | null>(null)

// Tag 到测点 ID 的映射表
const TAG_TO_POINT: Record<string, string> = {
  "239584": "EX10", "239587": "EX1", "239590": "EX6", "239593": "EX7",
  "239596": "EX9", "239599": "EX3", "239602": "EX8", "239608": "EX5",
  "239611": "EX4", "239614": "EX2", "253389": "IP2", "257472": "IP3",
  "257492": "IP1", "258600": "PL1", "268515": "IP6", "275992": "UPxdb10",
  "278035": "UPxdb9", "278051": "UPxdb1", "278067": "UPxdb2",
  "296123": "UPxdb8", "296141": "UPxdb7", "296157": "UPxdb6",
  "296177": "UPxdb5", "296199": "UPxdb4", "296217": "UPxdb3",
  "312054": "UPxby1", "312083": "UPxby2", "312099": "UPxby3",
  "312136": "UPxby4", "312182": "UPxbz1", "312198": "UPxbz2",
  "312222": "UPxbz3", "312232": "UPxbz4", "313546": "DL4",
  "314386": "DL3", "316930": "DL2", "316940": "DL1", "316948": "DL5",
  "316956": "DL6", "316964": "DL7", "316972": "DL8", "316980": "DL9",
  "316988": "DL10", "311163": "WExdb2", "311213": "WExdb1"
}

// IFC 测点名称 → 数据库测点名称的映射表
// 解决 IFC 模型使用基础名称(EX1)，数据库使用带后缀名称(EX1-2)的问题
const IFC_TO_DB_MAPPING: Record<string, string> = {
  // EX 引张线系列：IFC有EX1~EX10，数据库只有EX1系列(EX1-2~EX1-6)
  'EX1': 'EX1-2',
  // 'EX2': 'EX1-3', // 已废弃，EX2 应对应 EX2 系列
  'EX3': 'EX1-4',
  'EX4': 'EX1-5',
  'EX5': 'EX1-6',
  'EX6': 'EX1-6',
  'EX7': 'EX1-5',
  'EX8': 'EX1-4',
  'EX9': 'EX1-3',
  'EX10': 'EX1-2',
  // IP 倒垂线系列：IFC有IP1~IP3, IP6，数据库有IP2,IP4,IP6,IP8
  'IP1': 'IP2',
  'IP2': 'IP2',
  'IP3': 'IP4',
  'IP6': 'IP6',
  // TC 静力水准系列：直接匹配
  'TC1': 'TC1-12',
  'TC3': 'TC3-1',
  // UPxdb 系列映射到 TC
  'UPXDB1': 'TC1-12',
  'UPXDB2': 'TC3-1',
  'UPXDB3': 'TC3-2',
  'UPXDB4': 'TC3-3',
  'UPXDB5': 'TC3-4',
  'UPXDB6': 'TC3-5',
  'UPXDB7': 'TC1-12',
  'UPXDB8': 'TC3-1',
  'UPXDB9': 'TC3-2',
  'UPXDB10': 'TC3-3'
}
// 统计数据
const stats = computed(() => ({
  total: monitoringPoints.value.length,
  normal: monitoringPoints.value.filter(p => p.status === 'normal').length,
  warning: monitoringPoints.value.filter(p => p.status === 'warning').length,
  danger: monitoringPoints.value.filter(p => p.status === 'danger').length
}))

// 警告测点列表（用于右侧预警面板）
const warningPoints = computed(() => 
  monitoringPoints.value.filter(p => p.status === 'warning')
)

// 危险测点列表（用于右侧预警面板）
const dangerPoints = computed(() => 
  monitoringPoints.value.filter(p => p.status === 'danger')
)

// 库水位
const waterLevel = ref(142.35)

// 面板折叠状态
const leftPanelCollapsed = ref(false)
const rightPanelCollapsed = ref(false)

// 实时曲线图配置
const realtimeChartOption = computed(() => ({
  backgroundColor: 'transparent',
  grid: { top: 30, left: 50, right: 20, bottom: 30 },
  xAxis: {
    type: 'category',
    data: ['06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00'],
    axisLine: { lineStyle: { color: 'rgba(0,212,255,0.3)' } },
    axisLabel: { color: '#64748b', fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    name: 'mm',
    nameTextStyle: { color: '#64748b', fontSize: 10 },
    axisLine: { lineStyle: { color: 'rgba(0,212,255,0.3)' } },
    axisLabel: { color: '#64748b', fontSize: 10 },
    splitLine: { lineStyle: { color: 'rgba(0,212,255,0.1)' } }
  },
  series: [{
    type: 'line',
    smooth: true,
    data: [0.2, 0.35, 0.42, 0.38, 0.45, 0.49, 0.52],
    lineStyle: { color: '#00d4ff', width: 2 },
    areaStyle: { 
      color: { 
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(0,212,255,0.4)' },
          { offset: 1, color: 'rgba(0,212,255,0)' }
        ]
      }
    },
    itemStyle: { color: '#00d4ff' }
  }]
}))

// 水位仪表盘配置
const gaugeOption = computed(() => ({
  backgroundColor: 'transparent',
  series: [{
    type: 'gauge',
    startAngle: 200,
    endAngle: -20,
    min: 100,
    max: 180,
    splitNumber: 8,
    radius: '90%',
    center: ['50%', '60%'],
    axisLine: {
      lineStyle: {
        width: 6,
        color: [
          [0.3, '#10b981'],
          [0.7, '#00d4ff'],
          [1, '#ef4444']
        ]
      }
    },
    pointer: { 
      itemStyle: { color: '#00d4ff' },
      width: 4
    },
    axisTick: { show: false },
    splitLine: { show: false },
    axisLabel: { color: '#64748b', fontSize: 10, distance: 15 },
    title: { show: false },
    detail: { 
      valueAnimation: true,
      formatter: (value: number) => value.toFixed(2) + ' m',
      color: '#00d4ff',
      fontSize: 18,
      offsetCenter: [0, '40%']
    },
    data: [{ value: waterLevel.value }]
  }]
}))

// 选中测点的历史数据图表配置（动态）
const selectedPointChartOption = computed(() => {
  const historyData = selectedPoint.value?.historyData
  const prediction = selectedPoint.value?.prediction
  
  // 默认数据
  const defaultDates = ['暂无数据']
  const defaultValues = [0]
  
  const dates = historyData?.dates || defaultDates
  const values = historyData?.values || defaultValues
  
  // 核心改进：组合历史数据和预测数据，确保视觉连续性
  // 1. 获取最后10条历史数据
  const historySliceCount = 15
  const historyDates = dates.slice(-historySliceCount)
  const historyVals = values.slice(-historySliceCount)
  
  let allDates = [...historyDates]
  let historySeriesData: any[] = [...historyVals]
  let predictionSeriesData: any[] = [...Array(historyVals.length - 1).fill(null), historyVals[historyVals.length - 1]]
  
  // 2. 如果有预测数据，追加进来
  if (prediction && prediction.dates.length > 0) {
    allDates = [...allDates, ...prediction.dates]
    historySeriesData = [...historySeriesData, ...Array(prediction.dates.length).fill(null)]
    predictionSeriesData = [...predictionSeriesData, ...prediction.values]
  }
  
  
  return {
    backgroundColor: 'transparent',
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(13, 33, 55, 0.9)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: '#fff' }
    },
    legend: { 
      data: ['历史测值', '预测趋势'], 
      textStyle: { color: '#94a3b8', fontSize: 10 },
      top: 0,
      left: 'center'
    },
    grid: { top: 35, left: 45, right: 15, bottom: 35 },
    xAxis: {
      type: 'category',
      data: allDates.map(d => d.slice(5)), // 只显示 MM-DD
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.3)' } },
      axisLabel: { color: '#64748b', fontSize: 9, rotate: 30 }
    },
    yAxis: {
      type: 'value',
      name: 'mm',
      nameTextStyle: { color: '#64748b', fontSize: 10 },
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.3)' } },
      axisLabel: { color: '#64748b', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(0,212,255,0.1)' } }
    },
    series: [
      {
        name: '历史测值',
        type: 'line',
        smooth: true,
        data: historySeriesData,
        lineStyle: { color: '#00d4ff', width: 3 },
        areaStyle: { 
          color: { 
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0,212,255,0.3)' },
              { offset: 1, color: 'rgba(0,212,255,0)' }
            ]
          }
        },
        itemStyle: { color: '#00d4ff' },
        symbol: 'circle',
        symbolSize: 4
      },
      {
        name: '预测趋势',
        type: 'line',
        smooth: true,
        data: predictionSeriesData,
        lineStyle: { color: '#f59e0b', width: 3, type: 'dashed' },
        itemStyle: { color: '#f59e0b' },
        symbol: 'diamond',
        symbolSize: 6,
        // 添加置信区间标志
        markArea: prediction ? {
          itemStyle: { color: 'rgba(245, 158, 11, 0.1)' },
          data: [[{ xAxis: historyDates[historyDates.length-1].slice(5) }, { xAxis: allDates[allDates.length-1].slice(5) }]]
        } : undefined
      }
    ]
  }
})

// 预测数据表格转换
const predictionTableData = computed(() => {
  if (!selectedPoint.value?.prediction) return []
  
  const { dates, values, upper, lower } = selectedPoint.value.prediction
  
  return dates.map((date, i) => ({
    date: date.slice(5), // 只显示MM-DD
    value: values[i]?.toFixed(3) || '-',
    upper: upper[i]?.toFixed(3) || '-',
    lower: lower[i]?.toFixed(3) || '-',
    trend: i > 0 ? (values[i] > values[i-1] ? 'up' : values[i] < values[i-1] ? 'down' : 'stable') : 'stable',
    confidence: Math.max(60, Math.min(95, 90 - i * 2)) // 模拟置信度随时间递减
  }))
})

// 历史数据表格转换
const historyTableData = computed(() => {
  if (!selectedPoint.value?.historyData) return []
  
  const { dates, values } = selectedPoint.value.historyData
  
  return dates.map((date, i) => ({
    date: date.slice(5), // 只显示MM-DD
    value: values[i]?.toFixed(3) || '-',
    rawValue: values[i] || 0,
    waterLevel: '-', // 可以后续从数据库关联库水位数据
    change: i > 0 ? (values[i] - values[i-1]).toFixed(3) : null
  })).reverse() // 最新数据在前
})

/**
 * 获取状态颜色
 */
function getStatusColor(status: string): Cesium.Color {
  switch (status) {
    case 'warning': return Cesium.Color.YELLOW
    case 'danger': return Cesium.Color.RED
    default: return Cesium.Color.LIME
  }
}

/**
 * 同步最新的风险状态 (覆盖数据库中的静态状态)
 */
async function syncRiskStatus() {
  try {
    const anomalyResult = await mlApi.detectAnomalies()
    if (anomalyResult && anomalyResult.anomalies) {
      // 创建异常映射表
      const anomalyMap = new Map()
      anomalyResult.anomalies.forEach((a: any) => {
        // 后端: high -> 前端: danger
        // 后端: medium/low -> 前端: warning
        const status = a.severity === 'high' ? 'danger' : 'warning'
        anomalyMap.set(a.point_name, status)
      })
      
      let updateCount = 0
      // 更新所有测点的状态
      monitoringPoints.value.forEach((p: any) => {
        if (anomalyMap.has(p.name)) {
          const newStatus = anomalyMap.get(p.name)
          if (p.status !== newStatus) {
            p.status = newStatus
            updateCount++
          }
        } else {
          // 如果不在异常列表中，且当前不是normal，则重置为normal
          if (p.status !== 'normal') {
             p.status = 'normal'
             updateCount++
          }
        }
      })
      console.log(`已同步 ${updateCount} 个测点的实时风险状态`)
    }
  } catch (error) {
    console.warn('同步风险状态失败:', error)
  }
}

/**
 * 优化后：从后端 API 获取处理好的实时状态，而非直接拉取数据库全量表
 */
async function loadMonitoringPoints() {
  try {
    // 1. 并行请求：测点基础信息 + 实时状态
    // 如果 /api/realtime_status 返回了所有信息，甚至可以省去第一次 Supabase 查询
    const response = await fetch('/api/realtime_status');
    const result = await response.json();
    
    if (result.success && result.data) {
      // 直接使用后端返回的高效数据
      monitoringPoints.value = result.data.map((item: any, index: number) => ({
        id: item.name,      // 注意：后端返回的 id 可能是 UUID，name 是显示名
        name: item.name,
        type: item.type,
        value: Number(item.value.toFixed(2)),
        status: item.status,
        lon: 0, // 待模型加载后更新
        lat: 0,
        height: 100,
        index,
        last_update: item.last_update
      }));
      
      console.log(`成功加载 ${monitoringPoints.value.length} 个测点 (API 模式)`);
    } else {
      throw new Error(result.error || 'API 返回错误');
    }
  } catch (e) {
    console.error('加载测点失败:', e);
    ElMessage.warning('测点数据加载失败');
  }
}

/**
 * 核心算法：将 IFC 坐标对齐到 3D Tiles 模型
 * 
 * 原理：
 * 1. 计算 IFC 点集的中心点 (centroid)
 * 2. 获取 3D Tiles 模型的中心点 (boundingSphere.center)
 * 3. 假设 IFC 的相对坐标系与 Cesium 的 ENU (东北上) 坐标系存在对应关系：
 *    - IFC Y (最大跨度方向) -> Cesium East (X)
 *    - IFC X (其次) -> Cesium North (Y)
 *    - IFC Z -> Cesium Up (Z)
 * 4. 计算每个点相对于 IFC 中心的偏移量 (转为米)
 * 5. 将偏移量应用到 3D Tiles 模型的中心点上
 */
function updatePointsFromIFC(tileset: Cesium.Cesium3DTileset) {
  if (monitoringPoints.value.length === 0) return
  
  // 1. 获取 Tileset 中心 (世界坐标)
  const centerWorld = tileset.boundingSphere.center
  // 建立以 Tileset 中心为原点的 ENU 局部坐标系转换矩阵
  const centerTransform = Cesium.Transforms.eastNorthUpToFixedFrame(centerWorld)
  
  // 2. 计算 IFC 点集的中心 (Bounding Box Center)
  // 过滤出有效的 IFC 点 (排除 NaN)
  const validIfcPoints = ifcPointsData.filter(p => !isNaN(p.x) && !isNaN(p.y) && !isNaN(p.z))
  if (validIfcPoints.length === 0) {
    console.warn("没有有效的 IFC 坐标数据")
    return
  }
  
  let minX = Infinity, maxX = -Infinity
  let minY = Infinity, maxY = -Infinity
  let minZ = Infinity, maxZ = -Infinity
  
  validIfcPoints.forEach(p => {
    minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x)
    minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y)
    minZ = Math.min(minZ, p.z); maxZ = Math.max(maxZ, p.z)
  })
  
  // 移除质心对齐逻辑，改为直接使用 IFC 原点 (0,0,0) 对齐模型中心
  // 之前的逻辑会导致偏心分布的测点被强制拉回中心，导致"悬浮"在空中
  // const centerIfc = {
  //   x: (minX + maxX) / 2,
  //   y: (minY + maxY) / 2,
  //   z: (minZ + maxZ) / 2
  // }
  const centerIfc = { x: 0, y: 0, z: 0 }
  
  console.log("IFC Center (set to Origin):", centerIfc)
  
  // 3. 匹配并更新监测点坐标
  let matchedCount = 0
  
  monitoringPoints.value = monitoringPoints.value.map(point => {
    // 尝试匹配 IFC 数据
    // 数据库名称 point.name (如 EX1-2) -> 基础名称 (EX1)
    const baseName = point.name.split('-')[0]
    
    // 首先尝试精确匹配 point_id
    let ifcMatch = ifcPointsData.find((p: any) => p.point_id === point.name)
    
    // 如果精确匹配失败，尝试用基础名称匹配
    if (!ifcMatch) {
      ifcMatch = ifcPointsData.find((p: any) => p.point_id === baseName)
    }
    
    // EX2-4 匹配不到的问题修复 (EX2 应该是 EX2-4 的基名)
    if (!ifcMatch && baseName === 'EX2') {
      ifcMatch = ifcPointsData.find((ifc: any) => ifc.point_id === 'EX2')
    }
    
    if (ifcMatch) {
      matchedCount++
      
      // 计算偏移 (转为米)
      // 使用直接坐标，不减去质心
      // 注意：这里可能需要根据实际情况再次微调轴向 (X/Y)
      // 如果发现方向反了，可能需要反转 max/min 或直接 negate
      const dx = (ifcMatch.y - centerIfc.y) / 1000 // Y -> East
      const dy = (ifcMatch.x - centerIfc.x) / 1000 // X -> North 
      const dz = (ifcMatch.z - centerIfc.z) / 1000 // Z -> Up
      
      const offset = new Cesium.Cartesian3(dx, dy, dz)
      
      // 将偏移量应用到世界坐标系
      // WorldPos = CenterWorldMatrix * Offset
      const finalPos = Cesium.Matrix4.multiplyByPoint(centerTransform, offset, new Cesium.Cartesian3())
      
      // 存入 pointRealPositions 以便后续通过 ID 查找
      // 使用 baseName 作为 key，因为 flyToPoint 中使用的是 baseName
      pointRealPositions.value.set(baseName, finalPos)
      // ...
      pointRealPositions.value.set(point.id, finalPos)
      
      // 转回经纬度用于 Entity 显示
      const carto = Cesium.Cartographic.fromCartesian(finalPos)
      
      return {
        ...point,
        lon: Cesium.Math.toDegrees(carto.longitude),
        lat: Cesium.Math.toDegrees(carto.latitude),
        height: carto.height,
        ifcData: ifcMatch
      }
    } else {
      // 未匹配到的点，保持原样或默认分布
      // 暂时保留原位置 (0,0,100) 或之前逻辑生成的
      return point
    }
  })
  
  console.log(`IFC 坐标对齐完成，匹配成功: ${matchedCount} / ${monitoringPoints.value.length}`)
  
  // Debug specific points
  const p1 = monitoringPoints.value.find(p => p.name.includes('EX2-4'))
  const p2 = monitoringPoints.value.find(p => p.name.includes('TC1-6'))
  console.log('Update Complete Debug:', { 
    EX2_4: p1 ? { lon: p1.lon, lat: p1.lat, ifc: p1.ifcData?.point_id } : 'Not Found',
    TC1_6: p2 ? { lon: p2.lon, lat: p2.lat, ifc: p2.ifcData?.point_id } : 'Not Found'
  })

  // 刷新地图上的点
  addPointsToMap() 
}

/**
 * 初始化 Cesium
 */
async function initCesium() {
  if (!cesiumContainer.value) return
  if (!import.meta.env.VITE_CESIUM_TOKEN) {
    ElMessage.error('请配置 VITE_CESIUM_TOKEN')
    return
  }

  Cesium.Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_TOKEN

  try {
    viewer = new Cesium.Viewer(cesiumContainer.value, {
      terrain: Cesium.Terrain.fromWorldTerrain(),
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: false,
      vrButton: false,
      infoBox: false, // 关闭默认信息框，使用自定义面板
      selectionIndicator: true,
      creditContainer: document.createElement('div') // 隐藏水印
    })

    // 暗色主题
    viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString('#0a192f')
    viewer.scene.backgroundColor = Cesium.Color.fromCssColorString('#0a192f')
    if (viewer.scene.skyAtmosphere) {
      viewer.scene.skyAtmosphere.show = false
    }
    viewer.scene.fog.enabled = false
    
    // 配置 DepthTesting，确保点显示在模型表面之上/之中
    // viewer.scene.globe.depthTestAgainstTerrain = true; 

    // 只加载 D3 模型（包含监测仪器的大坝）
    const assetConfigs = [
      { id: 4338007, name: 'D3 (大坝含仪器)', tx: 0, ty: 0, tz: 0, scale: 1.0 }
    ]

    try {
      for (const config of assetConfigs) {
        const tileset = await Cesium.Cesium3DTileset.fromIonAssetId(config.id)
        viewer!.scene.primitives.add(tileset)
        
        // 应用位置微调 (由于已经 await，模型基本已就绪)
        const cartographic = Cesium.Cartographic.fromCartesian(tileset.boundingSphere.center)
        if (cartographic) {
          const surface = Cesium.Cartesian3.fromRadians(cartographic.longitude, cartographic.latitude, 0.0)
          const offset = Cesium.Cartesian3.fromRadians(
            cartographic.longitude + Cesium.Math.toRadians(config.tx * 0.00001), 
            cartographic.latitude + Cesium.Math.toRadians(config.ty * 0.00001), 
            config.tz
          )
          const translation = Cesium.Cartesian3.subtract(offset, surface, new Cesium.Cartesian3())
          tileset.modelMatrix = Cesium.Matrix4.fromTranslation(translation)
        }

        // 直接 zoomTo 到模型
        await viewer.zoomTo(tileset)
        
        // 核心改造：使用 IFC 数据对齐测点
    // updatePointsFromIFC(tileset) // 已移动到外部并行执行
    
    // 添加动态水面（基于模型位置）
    // createWaterSurface(tileset) // 已注释：不再显示水面方块
    
    return tileset
  }
  
  ElMessage.success('大坝完整三维模型组加载完成！')
} catch (e: any) {
      console.error('=== 模型加载失败详情 ===')
      console.error('错误对象:', e)
      console.error('错误消息:', e?.message)
      console.error('错误堆栈:', e?.stack)
      ElMessage.error(`模型加载失败: ${e?.message || '未知错误'}`)
      
      // 如果viewer已成功创建，飞到默认位置
      if (viewer) {
        try {
          viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(118.852, 32.051, 800),
            orientation: {
              heading: Cesium.Math.toRadians(30),
              pitch: Cesium.Math.toRadians(-30),
              roll: 0
            }
          })
          // 使用默认坐标创建水面
          createWaterSurface()
        } catch (fallbackError) {
          console.error('错误恢复失败:', fallbackError)
        }
      }
    }

    // 点击事件 - 支持点击模型构件和测点标注
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    handler.setInputAction(async (e: { position: Cesium.Cartesian2 }) => {
      const picked = viewer!.scene.pick(e.position)
      
      if (Cesium.defined(picked)) {
        // 情况1: 点击的是我们添加的测点标注 (Entity)
        if (picked.id && picked.id.properties) {
          const props = picked.id.properties
          const pointName = props.name?.getValue(Cesium.JulianDate.now()) || ''
          // 设置选中状态并异步加载历史数据
          selectedPoint.value = {
            id: props.id?.getValue(Cesium.JulianDate.now()) || '',
            name: pointName,
            type: props.type?.getValue(Cesium.JulianDate.now()) || '',
            value: props.value?.getValue(Cesium.JulianDate.now()) || 0,
            status: props.status?.getValue(Cesium.JulianDate.now()) || '',
            historyData: null,
            prediction: null,
            loadingHistory: true,
            loadingPrediction: false
          }
          // 异步加载历史数据
          loadPointHistory(pointName)
        }
        // 情况2: 点击的是 3D Tiles 模型构件 (Cesium3DTileFeature)
        else if (picked instanceof Cesium.Cesium3DTileFeature) {
          const feature = picked
          // 获取构件属性
          const propertyNames = feature.getPropertyIds ? feature.getPropertyIds() : []
          console.log('点击模型构件，属性:', propertyNames)
          
          // 获取 tag 属性（这是 IFC 模型的唯一标识）
          const tag = feature.getProperty('tag')
          console.log('构件 tag:', tag)
          
            if (tag) {
              // 使用 tag 映射表查找测点
              const pointId = TAG_TO_POINT[String(tag)]
            
            if (pointId) {
              console.log('IFC测点:', pointId)
              
              // 使用 IFC_TO_DB_MAPPING 将 IFC 测点名称转换为数据库测点名称
              const dbPointName = IFC_TO_DB_MAPPING[pointId.toUpperCase()] || IFC_TO_DB_MAPPING[pointId]
              console.log('映射到数据库测点:', dbPointName)
              
              // 在数据库测点中查找
              let matchedPoint = null
              if (dbPointName) {
                // 优先使用映射表的精确匹配
                matchedPoint = monitoringPoints.value.find(p => p.name === dbPointName)
              }
              
              // 如果映射表没有找到，使用模糊匹配作为后备
              if (!matchedPoint) {
                matchedPoint = monitoringPoints.value.find(p => 
                  p.name.toUpperCase().includes(pointId.toUpperCase()) ||
                  pointId.toUpperCase().includes(p.name.replace(/-\d+$/, '').toUpperCase())
                )
              }
              
              if (matchedPoint) {
                // 获取点击位置的 Cartesian3 坐标
                const clickPosition = viewer!.scene.pickPosition(e.position)
                if (clickPosition) {
                  // 保存测点真实的 3D 位置
                  const basePointId = matchedPoint.name.split('-')[0].toUpperCase()
                  pointRealPositions.value.set(basePointId, clickPosition)
                  console.log(`保存测点位置: ${basePointId}`, clickPosition)
                }
                
                selectedPoint.value = {
                  id: matchedPoint.id,
                  name: matchedPoint.name,
                  type: matchedPoint.type,
                  value: matchedPoint.value,
                  status: matchedPoint.status,
                  historyData: null,
                  prediction: null,
                  loadingHistory: true,
                  loadingPrediction: false
                }
                // 异步加载历史数据
                loadPointHistory(matchedPoint.name)
                ElMessage.success(`已选中测点: ${matchedPoint.name}`)
              } else {
                // 显示 IFC 测点信息（数据库中无对应记录）
                selectedPoint.value = {
                  id: String(tag),
                  name: pointId,
                  type: 'IFC测点',
                  value: 0,
                  status: 'normal',
                  historyData: null,
                  prediction: null,
                  loadingHistory: false,
                  loadingPrediction: false
                }
                ElMessage.info(`IFC测点: ${pointId} (数据库中无记录)`)
              }
            } else {
              // tag 不在测点映射表中，是坝段或其他建筑构件
              // 提取并显示构件详细信息面板
              const name1 = feature.getProperty('name_1') || feature.getProperty('Name') || '未知构件'
              const className = feature.getProperty('className') || feature.getProperty('ClassName') || 'IfcBuildingElement'
              const tag = feature.getProperty('tag') || feature.getProperty('Tag') || ''
              
              // 收集所有属性
              const properties: Record<string, any> = {}
              const propertyIds = feature.getPropertyIds()
              propertyIds.forEach((propId: string) => {
                const value = feature.getProperty(propId)
                if (value !== undefined && value !== null) {
                  properties[propId] = value
                }
              })
              
              // 设置选中的建筑构件信息
              selectedBuilding.value = {
                name: String(name1),
                tag: String(tag),
                className: String(className),
                properties
              }
              
              // 清空测点选择
              selectedPoint.value = null
              
              ElMessage.success(`已选中构件: ${String(name1).split(':')[0]}`)
            }
          }
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

  } catch (error) {
    console.error('Cesium 初始化失败:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 创建动态水面 - 根据大坝模型位置动态生成
 * @param tileset 大坝模型 tileset，用于获取模型中心位置
 */
function createWaterSurface(tileset?: Cesium.Cesium3DTileset) {
  if (!viewer) return

  let centerLon = 118.852  // 默认经度
  let centerLat = 32.051   // 默认纬度
  
  // 如果传入了 tileset，则从模型中心获取坐标
  if (tileset && tileset.boundingSphere) {
    const cartographic = Cesium.Cartographic.fromCartesian(tileset.boundingSphere.center)
    if (cartographic) {
      centerLon = Cesium.Math.toDegrees(cartographic.longitude)
      centerLat = Cesium.Math.toDegrees(cartographic.latitude)
      console.log(`水面位置基于模型中心: (${centerLon.toFixed(6)}, ${centerLat.toFixed(6)})`)
    }
  }

  // 在大坝上游（北侧）创建水面
  // 水面范围：大约 200m x 300m 的矩形区域
  const halfWidth = 0.001   // 约 100m（经度方向）
  const halfHeight = 0.0015 // 约 150m（纬度方向）
  const offsetNorth = 0.001 // 向北偏移约 100m（上游方向）
  
  const waterPositions = Cesium.Cartesian3.fromDegreesArray([
    centerLon - halfWidth, centerLat + offsetNorth,
    centerLon + halfWidth, centerLat + offsetNorth,
    centerLon + halfWidth, centerLat + offsetNorth + halfHeight,
    centerLon - halfWidth, centerLat + offsetNorth + halfHeight
  ])

  viewer.entities.add({
    name: '库区水面',
    polygon: {
      hierarchy: waterPositions,
      // 水面高度：使用当前水位作为高度
      height: new Cesium.CallbackProperty(() => waterLevel.value, false),
      material: new Cesium.ColorMaterialProperty(
        Cesium.Color.fromCssColorString('rgba(0, 191, 255, 0.5)')
      ),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString('rgba(0, 191, 255, 0.8)')
    }
  })

  console.log('库区水面已创建')
}

/**
 * 添加测点到地图
 */
function addPointsToMap() {
  if (!viewer) return

  // 用户要求删除地图上的绿色测点显示
  // viewer!.entities.removeAll() // 如果需要清除之前的点
  
  // monitoringPoints.value.forEach(point => {
  //   // 添加微型测点标注
  //   viewer!.entities.add({
  //     name: point.id,
  //     position: Cesium.Cartesian3.fromDegrees(point.lon, point.lat, point.height),
  //     point: {
  //       pixelSize: 10, // 稍微加大基础尺寸，依靠 scaleByDistance 控制视觉大小
  //       color: getStatusColor(point.status).withAlpha(0.9),
  //       outlineColor: Cesium.Color.WHITE.withAlpha(0.8),
  //       outlineWidth: 2,
  //       // 关键修复：添加距离缩放，防止远景下点太大
  //       // 距离 100m 时缩放 1.0，距离 3000m 时缩放 0.4
  //       scaleByDistance: new Cesium.NearFarScalar(100, 1.0, 3000, 0.4),
  //       // 开启深度检测，防止透视模型（如果需要穿透显示，设为 Number.POSITIVE_INFINITY）
  //       disableDepthTestDistance: 50000 
  //     },
  //     label: {
  //       text: point.name, // 显示中文名称或短ID
  //       font: '12px "Microsoft YaHei", sans-serif',
  //       fillColor: Cesium.Color.WHITE,
  //       outlineColor: Cesium.Color.BLACK,
  //       outlineWidth: 2,
  //       style: Cesium.LabelStyle.FILL_AND_OUTLINE,
  //       verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
  //       pixelOffset: new Cesium.Cartesian2(0, -15),
  //       showBackground: true,
  //       backgroundColor: new Cesium.Color(0.1, 0.1, 0.1, 0.6),
  //       backgroundPadding: new Cesium.Cartesian2(4, 2),
  //       // 标签的距离缩放
  //       scaleByDistance: new Cesium.NearFarScalar(100, 1.0, 3000, 0.0), // 远处直接隐藏标签
  //       distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 3000) // 超过3000米不显示标签
  //     },
  //     properties: {
  //       id: point.id,
  //       name: point.name,
  //       type: point.type,
  //       value: point.value,
  //       status: point.status
  //     }
  //   })
  // })
}

/**
 * 选中测点（不飞行，只显示详情和加载历史数据）
 */
async function selectPoint(point: typeof monitoringPoints.value[0]) {
  // 设置选中状态
  selectedPoint.value = {
    id: point.id,
    name: point.name,
    type: point.type,
    value: point.value,
    status: point.status,
    historyData: null,
    prediction: null,
    loadingHistory: true,
    loadingPrediction: false
  }
  
  // 异步加载历史数据
  await loadPointHistory(point.name)
}

/**
 * 加载测点历史数据 - 直接从 Supabase 数据库获取
 */
async function loadPointHistory(pointName: string) {
  if (!selectedPoint.value) return
  
  try {
    selectedPoint.value.loadingHistory = true
    
    // 先获取测点 ID
    const { data: pointData, error: pointError } = await supabase
      .from('monitoring_points')
      .select('id')
      .eq('name', pointName)
      .single()
    
    if (pointError || !pointData) {
      throw new Error(`测点 ${pointName} 不存在`)
    }
    
    // 从 monitoring_values 表获取历史数据
    const { data: historyData, error: historyError } = await supabase
      .from('monitoring_values')
      .select('measured_at, value')
      .eq('point_id', pointData.id)
      .order('measured_at', { ascending: true })
      .limit(50)
    
    if (historyError) throw historyError
    
    if (historyData && historyData.length > 0 && selectedPoint.value?.name === pointName) {
      selectedPoint.value.historyData = {
        dates: historyData.map((d: any) => d.measured_at?.split('T')[0] || ''),
        values: historyData.map((d: any) => Number(d.value) || 0)
      }
      console.log(`加载 ${pointName} 历史数据成功: ${historyData.length} 条`)
    } else {
      throw new Error('无历史数据')
    }
  } catch (e) {
    console.error('获取历史数据失败:', e)
    // 如果数据库也获取失败，尝试用 ML 后端
    try {
      const result = await mlApi.getPointHistory(pointName, 50)
      if (selectedPoint.value?.name === pointName) {
        selectedPoint.value.historyData = {
          dates: result.dates,
          values: result.values
        }
      }
    } catch {
      // 最终兜底：使用示例数据
      if (selectedPoint.value?.name === pointName) {
        selectedPoint.value.historyData = {
          dates: ['2025-12-01', '2025-12-02', '2025-12-03', '2025-12-04', '2025-12-05'],
          values: [0.2, 0.35, 0.42, 0.38, 0.45]
        }
      }
      ElMessage.warning('历史数据加载失败，使用示例数据')
    }
  } finally {
    if (selectedPoint.value) {
      selectedPoint.value.loadingHistory = false
    }
  }
}

/**
 * 执行预测（优先使用数据库缓存）
 */
async function runPrediction() {
  if (!selectedPoint.value) return
  
  selectedPoint.value.loadingPrediction = true
  
  try {
    const pointName = selectedPoint.value.name
    
    // 🚀 优先尝试从数据库获取预先计算好的预测（快速！）
    console.log(`[BigScreen] 🔍 尝试从数据库获取 ${pointName} 的缓存预测...`)
    const cachedResult = await mlApi.getCachedPrediction(pointName)
    
    if (cachedResult && cachedResult.predictions.length > 0) {
      // ✅ 使用缓存的预测结果
      console.log(`[BigScreen] ✅ 找到缓存预测，共 ${cachedResult.predictions.length} 天`)
      
      // 生成未来日期
      const futureDates: string[] = []
      let baseDate = new Date()
      
      if (selectedPoint.value.historyData && selectedPoint.value.historyData.dates.length > 0) {
        const lastDateStr = selectedPoint.value.historyData.dates[selectedPoint.value.historyData.dates.length - 1]
        if (lastDateStr) {
          baseDate = new Date(lastDateStr)
        }
      }
      
      for (let i = 1; i <= cachedResult.predictions.length; i++) {
        const date = new Date(baseDate)
        date.setDate(date.getDate() + i)
        futureDates.push(date.toISOString().split('T')[0])
      }
      
      if (selectedPoint.value && selectedPoint.value.name === pointName) {
        selectedPoint.value.prediction = {
          dates: futureDates,
          values: cachedResult.predictions,
          upper: cachedResult.confidence_upper,
          lower: cachedResult.confidence_lower
        }
        selectedPoint.value.loadingPrediction = false
      }
      
      ElMessage.success(`✅ 预测完成（来自缓存，${futureDates.length}天）`)
      return
    }
    
    // ⚠️ 没有缓存，fallback到实时API计算
    console.log('[BigScreen] ⚠️ 没有缓存预测，调用实时ML API...')
    ElMessage.warning('正在实时计算预测（可能需要几秒钟）...')
    
    let predictions: number[] = []
    let upper: number[] = []
    let lower: number[] = []
    
    // 检查ML后端状态
    if (!mlBackendConnected.value) {
      throw new Error('ML后端未连接，无法进行实时预测')
    }
    
    // 构造最近历史数据
    const recentHistory: { measure_time: string; value: number }[] = []
    if (selectedPoint.value.historyData?.dates && selectedPoint.value.historyData?.values) {
      const dates = selectedPoint.value.historyData.dates
      const values = selectedPoint.value.historyData.values
      const len = dates.length
      const start = Math.max(0, len - 60)
      
      for (let i = start; i < len; i++) {
        recentHistory.push({
          measure_time: dates[i],
          value: values[i]
        })
      }
    }

    console.log(`发送 ${recentHistory.length} 条实时历史数据用于预测校准`)
    const result = await predictPoint(pointName, 14, recentHistory)
    predictions = result.predictions
    upper = result.confidence_upper
    lower = result.confidence_lower
    
    // 生成未来日期
    const futureDates: string[] = []
    let baseDate = new Date()
    
    if (selectedPoint.value.historyData && selectedPoint.value.historyData.dates.length > 0) {
      const lastDateStr = selectedPoint.value.historyData.dates[selectedPoint.value.historyData.dates.length - 1]
      if (lastDateStr) {
        baseDate = new Date(lastDateStr)
      }
    }
    
    for (let i = 1; i <= predictions.length; i++) {
      const date = new Date(baseDate)
      date.setDate(date.getDate() + i)
      futureDates.push(date.toISOString().split('T')[0])
    }
    
    if (selectedPoint.value && selectedPoint.value.name === pointName) {
      selectedPoint.value.prediction = {
        dates: futureDates,
        values: predictions,
        upper: upper || predictions.map(v => v * 1.1),
        lower: lower || predictions.map(v => v * 0.9)
      }
      selectedPoint.value.loadingPrediction = false
    }
    
    ElMessage.success(`✅ 实时预测完成（${futureDates.length}天）`)
  } catch (e: any) {
    console.error('预测失败:', e)
    ElMessage.error(`预测失败: ${e.message || '未知错误'}`)
    if (selectedPoint.value) {
      selectedPoint.value.loadingPrediction = false
    }
  }
}

/**
 * 更新时间
 */
function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 定时器
let timer: ReturnType<typeof setInterval>

onMounted(async () => {
  // 检测 ML 后端连接状态
  mlBackendConnected.value = await mlApi.checkMLBackend()
  console.log('ML后端连接状态:', mlBackendConnected.value ? '已连接' : '未连接')
  
  // 并行加载数据和模型，提升首屏速度
  console.time('ParallelLoading')
  
  // 同时启动数据加载和3D引擎初始化
  const [_, tileset] = await Promise.all([
    loadMonitoringPoints(), // 数据加载 (已改为 API 极速模式)
    initCesium()            // 3D 引擎加载 (耗时操作)
  ])
  
  console.timeEnd('ParallelLoading')
  
  // 只有当两者都完成后，且 Tileset 加载成功，才执行坐标对齐
  if (tileset && monitoringPoints.value.length > 0) {
    updatePointsFromIFC(tileset as Cesium.Cesium3DTileset)
  }
  
  // 3. 异步调用 AI 深度检测 (不阻塞首屏)
  // 这会更新那些虽然 Z-Score 正常但 AI 模型认为异常的测点
  syncRiskStatus()
  
  updateTime()
  timer = setInterval(() => {
    updateTime()
    // 模拟水位微小波动 (更真实)
    // 基础水位 142.35，波动范围 ±0.02m
    const baseLevel = 142.35
    const fluctuation = (Math.random() - 0.5) * 0.04
    // 平滑过渡：当前水位 + 微小增量
    const current = waterLevel.value
    const target = baseLevel + fluctuation
    const step = (target - current) * 0.1
    
    waterLevel.value = Number((current + step).toFixed(2))
  }, 1000)
})

onUnmounted(() => {
  clearInterval(timer)
  if (viewer) {
    viewer.destroy()
  }
})
</script>

<template>
  <div class="big-screen">
    <!-- 顶部标题栏 -->
    <header class="header">
      <div class="header-left">
        <button class="back-btn" @click="$router.push('/dashboard')">← 返回系统</button>
        <span class="time">{{ currentTime }}</span>
      </div>
      <h1 class="title">
        <span class="title-icon">💧</span>
        智慧水利监测与管理平台
        <span class="title-sub">SMART WATER MONITORING SYSTEM</span>
      </h1>
      <div class="header-right">
        <span class="weather">🌤 晴 25°C</span>
      </div>
    </header>

    <!-- 主体内容 -->
    <main class="main-content">
      <!-- 左侧面板 -->
      <aside class="left-panel" :class="{ collapsed: leftPanelCollapsed }">
        <!-- 折叠按钮 -->
        <button class="collapse-btn left" @click="leftPanelCollapsed = !leftPanelCollapsed">
          {{ leftPanelCollapsed ? '▶' : '◀' }}
        </button>
        <!-- 测点统计 -->
        <div class="panel-card">
          <div class="panel-title">
            <span class="icon">📊</span>
            测点状态统计
          </div>
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-value">{{ stats.total }}</div>
              <div class="stat-label">测点总数</div>
            </div>
            <div class="stat-item stat-normal">
              <div class="stat-value">{{ stats.normal }}</div>
              <div class="stat-label">正常</div>
            </div>
            <div class="stat-item stat-warning">
              <div class="stat-value">{{ stats.warning }}</div>
              <div class="stat-label">警告</div>
            </div>
            <div class="stat-item stat-danger">
              <div class="stat-value">{{ stats.danger }}</div>
              <div class="stat-label">危险</div>
            </div>
          </div>
        </div>

        <!-- 测点列表 -->
        <div class="panel-card flex-1">
          <div class="panel-title">
            <span class="icon">📍</span>
            监测点列表
          </div>
          <div class="point-list">
            <div
              v-for="point in monitoringPoints"
              :key="point.id"
              class="point-item"
              :class="{ active: selectedPoint?.id === point.id }"
              @click="selectPoint(point)"
            >
              <div class="point-status" :class="point.status"></div>
              <div class="point-info">
                <div class="point-name">{{ point.id }}</div>
                <div class="point-type">{{ point.type }}</div>
              </div>
              <div class="point-value" :class="point.status">
                {{ point.value.toFixed(2) }} mm
              </div>
            </div>
          </div>
        </div>

        <!-- 库水位 -->
        <div class="panel-card">
          <div class="panel-title">
            <span class="icon">🌊</span>
            当前库水位
          </div>
          <v-chart :option="gaugeOption" autoresize style="height: 150px;" />
        </div>
      </aside>

      <!-- 中间3D区域 -->
      <section class="center-3d">
        <div ref="cesiumContainer" class="cesium-container">
          <div v-if="loading" class="loading-overlay">
            <div class="loading-spinner"></div>
            <span>正在加载三维场景...</span>
          </div>
        </div>

        <!-- 选中测点的弹窗 -->
        <transition name="popup">
          <div v-if="selectedPoint" class="point-popup">
            <div class="popup-header">
              <h3>{{ selectedPoint.name }}</h3>
              <button class="close-btn" @click="selectedPoint = null">×</button>
            </div>
            <div class="popup-body">
              <div class="popup-row">
                <span class="label">监测类型</span>
                <span class="value">{{ selectedPoint.type }}</span>
              </div>
              <div class="popup-row">
                <span class="label">当前测值</span>
                <span class="value highlight" :class="selectedPoint.status">
                  {{ selectedPoint.value.toFixed(2) }} mm
                </span>
              </div>
              <div class="popup-row">
                <span class="label">运行状态</span>
                <span class="status-badge" :class="selectedPoint.status">
                  {{ selectedPoint.status === 'normal' ? '正常' : selectedPoint.status === 'warning' ? '警告' : '危险' }}
                </span>
              </div>
            </div>
            
            <!-- ML后端状态提示 -->
            <div v-if="!mlBackendConnected" class="ml-status-warning">
              ⚠️ ML后端未连接，预测功能不可用
            </div>
            
            <!-- 历史数据 - 图表 + 表格双视图 -->
            <el-tabs v-model="historyTab" class="history-tabs">
              <!-- 图表标签 -->
              <el-tab-pane label="📈 趋势图" name="chart">
                <div class="popup-chart">
                  <div v-if="selectedPoint.loadingHistory" class="chart-loading">
                    加载中...
                  </div>
                  <v-chart v-else :option="selectedPointChartOption" autoresize style="height: 250px;" />
                </div>
              </el-tab-pane>
              
              <!-- 表格标签 -->
              <el-tab-pane label="📊 数据表" name="table">
                <div class="history-table-container">
                  <el-table 
                    :data="historyTableData" 
                    height="250" 
                    size="small"
                    :header-cell-style="{ background: 'rgba(0, 212, 255, 0.1)', color: '#00d4ff', fontSize: '12px' }"
                    :cell-style="{ background: 'rgba(13, 33, 55, 0.8)', color: '#94a3b8', fontSize: '11px' }"
                  >
                    <el-table-column prop="date" label="日期" width="110" />
                    <el-table-column prop="value" label="测值(mm)" align="right">
                      <template #default="{ row }">
                        <span :style="{ color: Math.abs(row.rawValue) > 3 ? '#ef4444' : Math.abs(row.rawValue) > 1.5 ? '#f59e0b' : '#10b981' }">
                          {{ row.value }}
                        </span>
                      </template>
                    </el-table-column>
                    <el-table-column prop="waterLevel" label="库水位(m)" width="100" align="right" />
                    <el-table-column prop="change" label="变化量" width="90" align="right">
                      <template #default="{ row }">
                        <span v-if="row.change" :style="{ color: row.change > 0 ? '#ef4444' : '#10b981' }">
                          {{ row.change > 0 ? '+' : '' }}{{ row.change }}
                        </span>
                        <span v-else>-</span>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </el-tab-pane>
            </el-tabs>
            
            <!-- 预测按钮 -->
            <div class="popup-actions">
              <button 
                class="predict-btn" 
                @click="runPrediction" 
                :disabled="!mlBackendConnected || selectedPoint.loadingPrediction"
              >
                <span v-if="selectedPoint.loadingPrediction">预测中...</span>
                <span v-else>🔮 执行预测</span>
              </button>
            </div>
            
            <!-- 预测结果 - 简单显示 -->
            <div v-if="selectedPoint.prediction" class="prediction-result">
              <div class="prediction-title">📈 预测结果（14天）</div>
              <div class="prediction-values">
                {{ selectedPoint.prediction.values.slice(0, 3).map(v => v.toFixed(2)).join(' → ') }} ...
              </div>
            </div>
          </div>
        </transition>

        <!-- 选中建筑构件的弹窗 -->
        <transition name="popup">
          <div v-if="selectedBuilding && !selectedPoint" class="building-popup point-popup">
            <div class="popup-header">
              <h3>{{ selectedBuilding.name.split(':')[0] }}</h3>
              <button class="close-btn" @click="selectedBuilding = null">×</button>
            </div>
            
            <div class="popup-body">
              <!-- 基本信息 -->
              <div class="popup-info">
                <div class="info-row">
                  <span class="info-label">构件标签</span>
                  <span class="info-value">{{ selectedBuilding.tag }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">构件类型</span>
                  <span class="info-value">{{ selectedBuilding.className }}</span>
                </div>
              </div>
              
              <!-- 属性列表 -->
              <div class="properties-section">
                <div class="section-title">📋 详细属性</div>
                <el-table 
                  :data="Object.entries(selectedBuilding.properties).map(([key, value]) => ({ key, value }))" 
                  height="300" 
                  size="small"
                  :header-cell-style="{ background: 'rgba(0, 212, 255, 0.1)', color: '#00d4ff', fontSize: '12px' }"
                  :cell-style="{ background: 'rgba(13, 33, 55, 0.8)', color: '#94a3b8', fontSize: '11px' }"
                >
                  <el-table-column prop="key" label="属性名" width="180" />
                  <el-table-column prop="value" label="属性值" show-overflow-tooltip>
                    <template #default="{ row }">
                      <span>{{ String(row.value).length > 50 ? String(row.value).substring(0, 50) + '...' : row.value }}</span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </div>
        </transition>
      </section>

      <!-- 右侧面板 -->
      <aside class="right-panel" :class="{ collapsed: rightPanelCollapsed }">
        <!-- 折叠按钮 -->
        <button class="collapse-btn right" @click="rightPanelCollapsed = !rightPanelCollapsed">
          {{ rightPanelCollapsed ? '◀' : '▶' }}
        </button>
        <!-- 实时趋势 - 显示选中测点的数据 -->
        <div class="panel-card">
          <div class="panel-title">
            <span class="icon">📈</span>
            {{ selectedPoint ? selectedPoint.name + ' 趋势' : '变形趋势分析' }}
          </div>
          <v-chart :option="selectedPoint?.historyData ? selectedPointChartOption : realtimeChartOption" autoresize style="height: 180px;" />
        </div>

        <!-- 预警信息 - 动态生成 -->
        <div class="panel-card flex-1">
          <div class="panel-title">
            <span class="icon">🚨</span>
            实时预警 ({{ warningPoints.length + dangerPoints.length }})
          </div>
          <div class="alarm-list">
            <!-- 危险测点 -->
            <div v-for="point in dangerPoints.slice(0, 2)" :key="'danger-'+point.id" class="alarm-item danger" @click="selectPoint(point)">
              <div class="alarm-icon">🔴</div>
              <div class="alarm-content">
                <div class="alarm-title">{{ point.name }} 严重超限</div>
                <div class="alarm-desc">当前值 {{ point.value.toFixed(2) }}mm，需立即处理</div>
                <div class="alarm-time">实时</div>
              </div>
            </div>
            <!-- 警告测点 -->
            <div v-for="point in warningPoints.slice(0, 3)" :key="'warning-'+point.id" class="alarm-item warning" @click="selectPoint(point)">
              <div class="alarm-icon">⚠️</div>
              <div class="alarm-content">
                <div class="alarm-title">{{ point.name }} 测值超限</div>
                <div class="alarm-desc">当前值 {{ point.value.toFixed(2) }}mm，超过阈值</div>
                <div class="alarm-time">实时</div>
              </div>
            </div>
            <!-- 无预警时显示 -->
            <div v-if="warningPoints.length === 0 && dangerPoints.length === 0" class="no-alarm">
              ✅ 所有测点运行正常
            </div>
          </div>
        </div>

        <!-- 系统信息 -->
        <div class="panel-card">
          <div class="panel-title">
            <span class="icon">ℹ️</span>
            系统信息
          </div>
          <div class="sys-info">
            <div class="info-row">
              <span>数据更新</span>
              <span class="online">实时</span>
            </div>
            <div class="info-row">
              <span>系统状态</span>
              <span class="online">● 在线</span>
            </div>
            <div class="info-row">
              <span>数据源</span>
              <span>Supabase</span>
            </div>
          </div>
        </div>
      </aside>
    </main>

    <!-- 底部信息栏 -->
    <footer class="footer">
      <span>河海大学水利水电学院 | 智慧水利专业课程设计</span>
      <span>开发者：章涵硕</span>
    </footer>
  </div>
</template>

<style scoped>
.big-screen {
  width: 100vw;
  height: 100vh;
  background: linear-gradient(135deg, #0a192f 0%, #0d2137 50%, #0a192f 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: 'Microsoft YaHei', sans-serif;
}

/* 顶部标题栏 */
.header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: linear-gradient(90deg, rgba(0,212,255,0.1) 0%, rgba(0,212,255,0.2) 50%, rgba(0,212,255,0.1) 100%);
  border-bottom: 1px solid rgba(0,212,255,0.3);
}

.header-left, .header-right {
  min-width: 200px;
}

.time {
  color: #00d4ff;
  font-size: 14px;
  font-family: 'Courier New', monospace;
}

.back-btn {
  background: rgba(0, 212, 255, 0.2);
  border: 1px solid rgba(0, 212, 255, 0.5);
  color: #00d4ff;
  padding: 6px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  margin-right: 16px;
  transition: all 0.2s;
}

.back-btn:hover {
  background: rgba(0, 212, 255, 0.4);
}

.title {
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  text-align: center;
  text-shadow: 0 0 20px rgba(0,212,255,0.5);
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  font-size: 28px;
}

.title-sub {
  font-size: 12px;
  font-weight: 400;
  color: rgba(0,212,255,0.7);
  letter-spacing: 2px;
}

.weather {
  color: #94a3b8;
  font-size: 14px;
}

.header-right {
  text-align: right;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
}

.logout-btn {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.5);
  color: #ef4444;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
}

.logout-btn:hover {
  background: rgba(239, 68, 68, 0.4);
}

/* 主体内容 */
.main-content {
  flex: 1;
  display: flex;
  gap: 16px;
  padding: 16px;
  min-height: 0;
}

/* 左右面板 */
.left-panel, .right-panel {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: relative;
  transition: width 0.3s ease, opacity 0.3s ease;
  overflow: hidden;
}

/* 面板折叠状态 */
.left-panel.collapsed, .right-panel.collapsed {
  width: 40px;
}

.left-panel.collapsed .panel-card,
.right-panel.collapsed .panel-card {
  opacity: 0;
  pointer-events: none;
}

/* 折叠按钮 */
.collapse-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 60px;
  background: rgba(0, 212, 255, 0.2);
  border: 1px solid rgba(0, 212, 255, 0.4);
  color: #00d4ff;
  cursor: pointer;
  border-radius: 4px;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.collapse-btn:hover {
  background: rgba(0, 212, 255, 0.4);
}

.collapse-btn.left {
  right: -12px;
}

.collapse-btn.right {
  left: -12px;
}
/* 面板卡片 */
.panel-card {
  background: rgba(13, 33, 55, 0.8);
  border: 1px solid rgba(0,212,255,0.2);
  border-radius: 8px;
  padding: 16px;
  backdrop-filter: blur(10px);
}

.panel-card.flex-1 {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(0,212,255,0.2);
}

.panel-title .icon {
  font-size: 16px;
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.stat-item {
  text-align: center;
  padding: 12px 8px;
  background: rgba(0,212,255,0.1);
  border-radius: 6px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #00d4ff;
}

.stat-label {
  font-size: 11px;
  color: #64748b;
  margin-top: 4px;
}

.stat-normal .stat-value { color: #10b981; }
.stat-warning .stat-value { color: #f59e0b; }
.stat-danger .stat-value { color: #ef4444; }

/* 测点列表 */
.point-list {
  flex: 1;
  overflow-y: auto;
}

.point-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: rgba(0,212,255,0.05);
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.point-item:hover, .point-item.active {
  background: rgba(0,212,255,0.15);
  border-color: rgba(0,212,255,0.3);
}

.point-status {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #10b981;
}

.point-status.warning { background: #f59e0b; }
.point-status.danger { background: #ef4444; animation: pulse 1s infinite; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.point-info {
  flex: 1;
}

.point-name {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}

.point-type {
  font-size: 11px;
  color: #64748b;
}

.point-value {
  font-size: 14px;
  font-weight: 600;
  color: #10b981;
}

.point-value.warning { color: #f59e0b; }
.point-value.danger { color: #ef4444; }

/* 中间3D区域 */
.center-3d {
  flex: 1;
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(0,212,255,0.2);
}

.cesium-container {
  width: 100%;
  height: 100%;
}

.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: rgba(10,25,47,0.9);
  color: #fff;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(0,212,255,0.2);
  border-top-color: #00d4ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 测点弹窗 */
.point-popup {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 500px;
  background: rgba(13, 33, 55, 0.95);
  border: 1px solid rgba(0,212,255,0.3);
  border-radius: 8px;
  backdrop-filter: blur(10px);
  overflow: hidden;
}

.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(0,212,255,0.1);
  border-bottom: 1px solid rgba(0,212,255,0.2);
}

.popup-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #00d4ff;
}

.close-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 18px;
  cursor: pointer;
}

.close-btn:hover {
  color: #fff;
}

.popup-body {
  padding: 16px;
}

.popup-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.popup-row .label {
  color: #64748b;
  font-size: 13px;
}

.popup-row .value {
  color: #fff;
  font-size: 13px;
  font-weight: 500;
}

.popup-row .value.highlight {
  font-size: 16px;
}

.popup-row .value.normal { color: #10b981; }
.popup-row .value.warning { color: #f59e0b; }
.popup-row .value.danger { color: #ef4444; }

.status-badge {
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
}

.status-badge.normal { background: rgba(16,185,129,0.2); color: #10b981; }
.status-badge.warning { background: rgba(245,158,11,0.2); color: #f59e0b; }
.status-badge.danger { background: rgba(239,68,68,0.2); color: #ef4444; }

.popup-chart {
  padding: 0 16px 16px;
}

/* 预警列表 */
.alarm-list {
  flex: 1;
  overflow-y: auto;
}

.alarm-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 6px;
  background: rgba(245,158,11,0.1);
  border-left: 3px solid #f59e0b;
}

.alarm-item.danger {
  background: rgba(239,68,68,0.1);
  border-left-color: #ef4444;
}

.alarm-icon {
  font-size: 20px;
}

.alarm-content {
  flex: 1;
}

.alarm-title {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}

.alarm-desc {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}

.alarm-time {
  font-size: 10px;
  color: #64748b;
  margin-top: 4px;
}

/* 系统信息 */
.sys-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #64748b;
}

.info-row .online {
  color: #10b981;
}

/* 建筑构件属性区域 */
.properties-section {
  margin-top: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #00d4ff;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(0,212,255,0.2);
}

/* 底部 */
.footer {
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(0,212,255,0.05);
  border-top: 1px solid rgba(0,212,255,0.1);
  font-size: 12px;
  color: #64748b;
}

/* 动画 */
.popup-enter-active, .popup-leave-active {
  transition: all 0.3s ease;
}

.popup-enter-from, .popup-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

/* ML 后端状态提示 */
.ml-status-warning {
  background: rgba(245, 158, 11, 0.2);
  border: 1px solid rgba(245, 158, 11, 0.5);
  border-radius: 6px;
  padding: 8px 12px;
  margin: 10px 0;
  font-size: 12px;
  color: #f59e0b;
  text-align: center;
}

/* 图表加载状态 */
.chart-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 140px;
  color: #64748b;
  font-size: 13px;
}

/* 预测按钮容器 */
.popup-actions {
  margin: 12px 0;
  text-align: center;
}

/* 预测按钮 */
.predict-btn {
  background: linear-gradient(135deg, #0ea5e9, #06b6d4);
  border: none;
  border-radius: 8px;
  padding: 10px 24px;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
}

.predict-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(14, 165, 233, 0.4);
}

.predict-btn:disabled {
  background: #334155;
  color: #64748b;
  cursor: not-allowed;
  box-shadow: none;
}

/* 预测结果 */
.prediction-result {
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.3);
  border-radius: 8px;
  padding: 12px;
  margin-top: 10px;
}

.prediction-title {
  font-size: 13px;
  font-weight: 600;
  color: #00d4ff;
  margin-bottom: 6px;
}

.prediction-values {
  font-size: 14px;
  color: #f59e0b;
  font-weight: 500;
}

/* 无预警时的显示 */
.no-alarm {
  text-align: center;
  color: #10b981;
  font-size: 14px;
  padding: 20px;
}

/* 预警项可点击 */
.alarm-item {
  cursor: pointer;
  transition: transform 0.2s ease;
}

.alarm-item:hover {
  transform: translateX(5px);
}
</style>
