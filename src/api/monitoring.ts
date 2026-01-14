/**
 * 文件名: monitoring.ts
 * 功能: 监测数据 API 服务 - 连接 Supabase 获取真实数据
 * 作者: 章涵硕
 */

import { supabase } from '@/lib/supabase'
import type { MonitoringPoint, MonitoringValue, Statistics } from '@/types'

/**
 * 获取所有测点列表
 * @param type 可选，筛选监测类型
 */
export async function getMonitoringPoints(type?: string): Promise<MonitoringPoint[]> {
    // 使用关联查询直接获取最新测值
    let query = supabase
        .from('monitoring_points')
        .select(`
            *,
            monitoring_values (
                value,
                measured_at
            )
        `)
        .order('name')
        .order('measured_at', { foreignTable: 'monitoring_values', ascending: false })
        .limit(1, { foreignTable: 'monitoring_values' })

    if (type && type !== 'all') {
        query = query.eq('type', type)
    }

    const { data, error } = await query

    if (error) {
        console.error('获取测点失败:', error)
        throw error
    }

    return (data || []).map(item => {
        // 获取最新的测值记录（如果有）
        const latestRecord = item.monitoring_values?.[0]

        return {
            id: item.id,
            name: item.name,
            type: item.type,
            typeName: item.type_name || formatTypeName(item.type),
            location: item.location,
            elevation: item.elevation,
            section: item.section,
            installDate: item.install_date,
            status: item.status,
            // 优先使用关联查询到的最新值，其次是视图字段，最后默认为0
            latestValue: latestRecord ? latestRecord.value : (item.latest_value || 0)
        }
    })
}

function formatTypeName(type: string): string {
    const map: Record<string, string> = {
        'tension_wire': '引张线',
        'hydrostatic_level': '静力水准',
        'plumb_line': '倒垂线',
        'seepage': '渗流量',
        'temp': '温度',
        'stress': '应力'
    }
    return map[type] || type
}

/**
 * 获取单个测点详情
 */
export async function getMonitoringPoint(id: string): Promise<MonitoringPoint | null> {
    const { data, error } = await supabase
        .from('monitoring_points')
        .select('*')
        .eq('id', id)
        .single()

    if (error) {
        console.error('获取测点详情失败:', error)
        return null
    }

    return data ? {
        id: data.id,
        name: data.name,
        type: data.type,
        typeName: data.type_name || formatTypeName(data.type),
        location: data.location,
        elevation: data.elevation,
        section: data.section,
        installDate: data.install_date,
        status: data.status,
        latestValue: data.latest_value
    } : null
}

/**
 * 获取测点历史测值
 * @param pointId 测点ID
 * @param startDate 可选，开始日期 (YYYY-MM-DD)
 * @param endDate 可选，结束日期 (YYYY-MM-DD)
 * @param limit 限制数量，默认1000条
 */
export async function getMonitoringValues(
    pointId: string,
    startDate?: string,
    endDate?: string,
    limit: number = 1000
): Promise<MonitoringValue[]> {
    let query = supabase
        .from('monitoring_values')
        .select('*')
        .eq('point_id', pointId)
        .order('measured_at', { ascending: true })

    // 添加时间范围筛选
    if (startDate) {
        query = query.gte('measured_at', startDate)
    }
    if (endDate) {
        query = query.lte('measured_at', endDate + ' 23:59:59') // 包含结束日期的全天数据
    }

    query = query.limit(limit)

    const { data, error } = await query

    if (error) {
        console.error('获取测值失败:', error)
        throw error
    }

    return (data || []).map(item => ({
        id: item.id,
        pointId: item.point_id,
        value: item.value,
        unit: item.unit,
        waterLevel: item.water_level,
        measuredAt: item.measured_at,
        isAnomaly: item.is_anomaly
    }))
}

/**
 * 新增测值
 */
export async function addMonitoringValue(
    pointId: string,
    value: number,
    measuredAt: string
): Promise<MonitoringValue> {
    const { data, error } = await supabase
        .from('monitoring_values')
        .insert({
            point_id: pointId,
            value,
            unit: 'mm',
            measured_at: measuredAt
        })
        .select()
        .single()

    if (error) {
        console.error('新增测值失败:', error)
        throw error
    }

    return {
        id: data.id,
        pointId: data.point_id,
        value: data.value,
        unit: data.unit,
        measuredAt: data.measured_at
    }
}

/**
 * 新增测点
 */
export async function addMonitoringPoint(
    point: Partial<MonitoringPoint>
): Promise<MonitoringPoint> {
    const { data, error } = await supabase
        .from('monitoring_points')
        .insert({
            name: point.name,
            type: point.type,
            location: point.location,
            elevation: point.elevation,
            section: point.section,
            install_date: point.installDate,
            status: 'normal'
        })
        .select()
        .single()

    if (error) {
        console.error('新增测点失败:', error)
        throw error
    }

    return {
        id: data.id,
        name: data.name,
        type: data.type,
        location: data.location,
        elevation: data.elevation,
        section: data.section,
        installDate: data.install_date,
        status: data.status
    }
}

/**
 * 获取统计数据
 */
export async function getStatistics(): Promise<Statistics> {
    // 获取各状态测点数量
    const { data: points, error } = await supabase
        .from('monitoring_points')
        .select('status')

    if (error) {
        console.error('获取统计失败:', error)
        throw error
    }

    const stats = {
        totalPoints: points?.length || 0,
        normalCount: points?.filter(p => p.status === 'normal').length || 0,
        warningCount: points?.filter(p => p.status === 'warning').length || 0,
        dangerCount: points?.filter(p => p.status === 'danger').length || 0,
        latestUpdate: new Date().toLocaleString('zh-CN')
    }

    return stats
}

/**
 * 订阅测值实时更新
 * @param callback 收到新数据时的回调函数
 */
export function subscribeToValues(
    callback: (payload: { new: MonitoringValue }) => void
) {
    return supabase
        .channel('monitoring_values_changes')
        .on(
            'postgres_changes',
            { event: 'INSERT', schema: 'public', table: 'monitoring_values' },
            (payload) => {
                callback({
                    new: {
                        id: payload.new.id,
                        pointId: payload.new.point_id,
                        value: payload.new.value,
                        unit: payload.new.unit,
                        measuredAt: payload.new.measured_at
                    }
                })
            }
        )
        .subscribe()
}

/**
 * 取消订阅
 */
export function unsubscribeFromValues(subscription: ReturnType<typeof supabase.channel>) {
    supabase.removeChannel(subscription)
}
