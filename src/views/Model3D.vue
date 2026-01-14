<!--
  组件名: Model3D.vue
  功能: Cesium 三维模型展示页面
  作者: 章涵硕
  特色: 大坝三维模型 + 测点标注 + 数据联动
-->
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as Cesium from 'cesium'
import { ElMessage } from 'element-plus'

// Cesium Viewer 实例
let viewer: Cesium.Viewer | null = null
const cesiumContainer = ref<HTMLDivElement>()
const loading = ref(true)
const selectedPointInfo = ref<{
  name: string
  type: string
  value: number
  status: string
} | null>(null)

// 模型加载状态
const modelLoaded = ref(false)

// 示例测点数据（用于在模型上标注）
const monitoringPoints = [
  { id: 'EX1-2', lon: 118.85, lat: 32.05, height: 153, type: '引张线', value: 0.49, status: 'normal' },
  { id: 'EX1-3', lon: 118.851, lat: 32.051, height: 153, type: '引张线', value: 2.10, status: 'normal' },
  { id: 'EX1-4', lon: 118.852, lat: 32.052, height: 153, type: '引张线', value: 3.45, status: 'warning' },
  { id: 'TC1-5', lon: 118.853, lat: 32.053, height: 160, type: '静力水准', value: 0.96, status: 'danger' },
  { id: 'IP3', lon: 118.854, lat: 32.054, height: 80, type: '倒垂线', value: 0.25, status: 'normal' }
]

/**
 * 获取状态对应的颜色
 */
function getStatusColor(status: string): Cesium.Color {
  switch (status) {
    case 'warning': return Cesium.Color.YELLOW
    case 'danger': return Cesium.Color.RED
    default: return Cesium.Color.GREEN
  }
}

/**
 * 初始化 Cesium Viewer
 */
async function initCesium() {
  if (!cesiumContainer.value) return

  // 设置 Cesium Ion Token
  Cesium.Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_TOKEN

  try {
    // 创建 Viewer
    viewer = new Cesium.Viewer(cesiumContainer.value, {
      terrain: Cesium.Terrain.fromWorldTerrain(),
      baseLayerPicker: false,
      geocoder: false,
      homeButton: true,
      sceneModePicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: false,
      vrButton: false,
      infoBox: false,
      selectionIndicator: false
    })

    // 设置暗色主题
    viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString('#0a192f')
    viewer.scene.backgroundColor = Cesium.Color.fromCssColorString('#0a192f')
    // 修正天空大气显示
    if (viewer.scene.skyAtmosphere) {
      viewer.scene.skyAtmosphere.show = false
    }

    // 只加载 D1 大坝主体模型（简化版）
    const assetConfigs = [
      { id: 4337765, name: 'D1 (大坝主体)', tx: 0, ty: 0, tz: 0 }
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

        if (config.id === 4337765) {
          await viewer.zoomTo(tileset)
        }
      }
      
      ElMessage.success('大坝三维模型加载成功！')
    } catch (modelError) {
      console.error('模型加载失败:', modelError)
      ElMessage.warning('模型加载中，请稍候...')
      
      // 如果模型加载失败，飞到默认位置
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(118.852, 32.052, 2000),
        orientation: {
          heading: Cesium.Math.toRadians(0),
          pitch: Cesium.Math.toRadians(-45),
          roll: 0
        },
        duration: 2
      })
    }

    // 添加测点标注
    addMonitoringPointsToMap()

    // 添加点击事件
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    handler.setInputAction((movement: { position: Cesium.Cartesian2 }) => {
      const pickedObject = viewer!.scene.pick(movement.position)
      if (Cesium.defined(pickedObject) && pickedObject.id) {
        const entity = pickedObject.id as Cesium.Entity
        if (entity.properties) {
          selectedPointInfo.value = {
            name: entity.properties.name?.getValue(Cesium.JulianDate.now()) || '',
            type: entity.properties.type?.getValue(Cesium.JulianDate.now()) || '',
            value: entity.properties.value?.getValue(Cesium.JulianDate.now()) || 0,
            status: entity.properties.status?.getValue(Cesium.JulianDate.now()) || ''
          }
        }
      } else {
        selectedPointInfo.value = null
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

    modelLoaded.value = true
    ElMessage.success('三维场景加载成功！')
  } catch (error) {
    console.error('Cesium 初始化失败:', error)
    ElMessage.error('三维场景加载失败，请检查网络连接')
  } finally {
    loading.value = false
  }
}

/**
 * 添加测点标注到地图
 */
function addMonitoringPointsToMap() {
  if (!viewer) return

  monitoringPoints.forEach(point => {
    viewer!.entities.add({
      name: point.id,
      position: Cesium.Cartesian3.fromDegrees(point.lon, point.lat, point.height),
      point: {
        pixelSize: 12,
        color: getStatusColor(point.status),
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2
      },
      label: {
        text: point.id,
        font: '14px Microsoft YaHei',
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 2,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -15)
      },
      properties: {
        name: point.id,
        type: point.type,
        value: point.value,
        status: point.status
      }
    })
  })
}

/**
 * 飞到指定测点
 */
function flyToPoint(pointId: string) {
  if (!viewer) return
  
  const point = monitoringPoints.find(p => p.id === pointId)
  if (point) {
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(point.lon, point.lat, 500),
      duration: 1.5
    })
  }
}

/**
 * 获取状态文本
 */
function getStatusText(status: string) {
  const map: Record<string, string> = {
    normal: '正常',
    warning: '警告',
    danger: '危险'
  }
  return map[status] || status
}

/**
 * 获取状态样式类
 */
function getStatusClass(status: string) {
  return `status-tag status-tag--${status}`
}

onMounted(() => {
  initCesium()
})

onUnmounted(() => {
  if (viewer) {
    viewer.destroy()
    viewer = null
  }
})
</script>

<template>
  <div class="model3d-page">
    <!-- Cesium 容器 -->
    <div ref="cesiumContainer" class="cesium-container">
      <!-- 加载状态 -->
      <div v-if="loading" class="loading-overlay">
        <el-icon class="loading-icon" :size="48"><Loading /></el-icon>
        <span>正在加载三维场景...</span>
      </div>
    </div>
    
    <!-- 左侧控制面板 -->
    <div class="control-panel glass-card">
      <h3 class="panel-title">
        <el-icon><Position /></el-icon>
        测点导航
      </h3>
      
      <div class="point-buttons">
        <el-button 
          v-for="point in monitoringPoints" 
          :key="point.id"
          size="small"
          :type="point.status === 'danger' ? 'danger' : point.status === 'warning' ? 'warning' : 'default'"
          @click="flyToPoint(point.id)"
        >
          {{ point.id }}
        </el-button>
      </div>
      
      <div class="legend">
        <h4>图例</h4>
        <div class="legend-item">
          <span class="dot" style="background: #10b981;"></span>
          <span>正常</span>
        </div>
        <div class="legend-item">
          <span class="dot" style="background: #f59e0b;"></span>
          <span>警告</span>
        </div>
        <div class="legend-item">
          <span class="dot" style="background: #ef4444;"></span>
          <span>危险</span>
        </div>
      </div>
    </div>
    
    <!-- 测点信息弹窗 -->
    <transition name="slide">
      <div v-if="selectedPointInfo" class="point-info-popup glass-card">
        <div class="popup-header">
          <h4>{{ selectedPointInfo.name }}</h4>
          <el-button type="primary" link @click="selectedPointInfo = null">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
        <div class="popup-content">
          <div class="info-row">
            <span class="label">监测类型</span>
            <span class="value">{{ selectedPointInfo.type }}</span>
          </div>
          <div class="info-row">
            <span class="label">当前测值</span>
            <span class="value">{{ selectedPointInfo.value.toFixed(2) }} mm</span>
          </div>
          <div class="info-row">
            <span class="label">运行状态</span>
            <span :class="getStatusClass(selectedPointInfo.status)">
              {{ getStatusText(selectedPointInfo.status) }}
            </span>
          </div>
        </div>
        <div class="popup-footer">
          <el-button type="primary" size="small">
            <el-icon><DataLine /></el-icon>
            查看历史数据
          </el-button>
        </div>
      </div>
    </transition>
    
    <!-- 提示信息 -->
    <div class="tips glass-card">
      <el-icon><InfoFilled /></el-icon>
      <span>提示：点击测点标注可查看详细信息，使用鼠标滚轮可缩放视图</span>
    </div>
  </div>
</template>

<style scoped>
.model3d-page {
  position: relative;
  height: 100%;
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.cesium-container {
  width: 100%;
  height: 100%;
}

/* 隐藏 Cesium 水印 */
:deep(.cesium-credit-logoContainer),
:deep(.cesium-credit-expand-link) {
  display: none !important;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: rgba(10, 25, 47, 0.9);
  color: var(--text-primary);
  z-index: 10;
}

.loading-icon {
  animation: spin 1s linear infinite;
  color: var(--accent);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 控制面板 */
.control-panel {
  position: absolute;
  top: 16px;
  left: 16px;
  width: 200px;
  padding: 16px;
  z-index: 5;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.point-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.legend h4 {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

/* 测点信息弹窗 */
.point-info-popup {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 280px;
  padding: 16px;
  z-index: 5;
}

.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.popup-header h4 {
  font-size: 16px;
  font-weight: 600;
  color: var(--accent);
}

.popup-content {
  padding: 12px 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}

.info-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-row .label {
  color: var(--text-secondary);
  font-size: 13px;
}

.info-row .value {
  color: var(--text-primary);
  font-weight: 500;
}

.popup-footer {
  margin-top: 12px;
}

/* 提示信息 */
.tips {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  z-index: 5;
}

/* 动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
