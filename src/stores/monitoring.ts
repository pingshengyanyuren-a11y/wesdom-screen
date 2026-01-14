/**
 * 文件名: monitoring.ts
 * 功能: 监测数据状态管理 (Pinia Store)
 * 作者: 章涵硕
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { MonitoringPoint, MonitoringValue, Statistics } from '@/types'
import * as api from '@/api/monitoring'

export const useMonitoringStore = defineStore('monitoring', () => {
    // 状态
    const points = ref<MonitoringPoint[]>([])
    const selectedPoint = ref<MonitoringPoint | null>(null)
    const selectedPointValues = ref<MonitoringValue[]>([])
    const statistics = ref<Statistics>({
        totalPoints: 0,
        normalCount: 0,
        warningCount: 0,
        dangerCount: 0,
        latestUpdate: ''
    })
    const loading = ref(false)
    const error = ref<string | null>(null)

    // 计算属性
    const tensionWirePoints = computed(() =>
        points.value.filter(p => p.type === 'tension_wire')
    )

    const hydrostaticLevelPoints = computed(() =>
        points.value.filter(p => p.type === 'hydrostatic_level')
    )

    const plumbLinePoints = computed(() =>
        points.value.filter(p => p.type === 'plumb_line')
    )

    const warningPoints = computed(() =>
        points.value.filter(p => p.status === 'warning' || p.status === 'danger')
    )

    /**
     * 加载所有测点
     */
    async function loadPoints(type?: string) {
        loading.value = true
        error.value = null
        try {
            points.value = await api.getMonitoringPoints(type)
        } catch (e) {
            error.value = (e as Error).message
        } finally {
            loading.value = false
        }
    }

    /**
     * 选择测点并加载其历史数据
     */
    async function selectPoint(point: MonitoringPoint) {
        selectedPoint.value = point
        loading.value = true
        try {
            selectedPointValues.value = await api.getMonitoringValues(point.id)
        } catch (e) {
            error.value = (e as Error).message
        } finally {
            loading.value = false
        }
    }

    /**
     * 加载统计数据
     */
    async function loadStatistics() {
        try {
            statistics.value = await api.getStatistics()
        } catch (e) {
            error.value = (e as Error).message
        }
    }

    /**
     * 新增测值
     */
    async function addValue(pointId: string, value: number, measuredAt: string) {
        try {
            const newValue = await api.addMonitoringValue(pointId, value, measuredAt)
            // 如果是当前选中的测点，更新其历史数据
            if (selectedPoint.value?.id === pointId) {
                selectedPointValues.value.push(newValue)
            }
            // 刷新统计
            await loadStatistics()
            return { success: true, data: newValue }
        } catch (e) {
            return { success: false, error: (e as Error).message }
        }
    }

    /**
     * 新增测点
     */
    async function addPoint(point: Partial<MonitoringPoint>) {
        try {
            const newPoint = await api.addMonitoringPoint(point)
            points.value.push(newPoint)
            await loadStatistics()
            return { success: true, data: newPoint }
        } catch (e) {
            return { success: false, error: (e as Error).message }
        }
    }

    /**
     * 订阅实时数据更新
     */
    function subscribeToUpdates() {
        const subscription = api.subscribeToValues((payload) => {
            console.log('收到新测值:', payload.new)
            // 更新对应测点的最新值
            const point = points.value.find(p => p.id === payload.new.pointId)
            if (point) {
                point.latestValue = payload.new.value
            }
            // 更新统计时间
            statistics.value.latestUpdate = new Date().toLocaleString('zh-CN')
        })
        return subscription
    }

    return {
        // 状态
        points,
        selectedPoint,
        selectedPointValues,
        statistics,
        loading,
        error,
        // 计算属性
        tensionWirePoints,
        hydrostaticLevelPoints,
        plumbLinePoints,
        warningPoints,
        // 方法
        loadPoints,
        selectPoint,
        loadStatistics,
        addValue,
        addPoint,
        subscribeToUpdates
    }
})
