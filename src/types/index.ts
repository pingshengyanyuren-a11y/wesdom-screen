/**
 * 文件名: index.ts
 * 功能: 全局类型定义
 * 作者: 章涵硕
 */

// 测点类型
export interface MonitoringPoint {
    id: string
    name: string                    // 仪器编号 (如 EX1-2, TC1-1)
    type: 'tension_wire' | 'hydrostatic_level' | 'plumb_line'  // 引张线/静力水准/倒垂线
    typeName?: string               // 类型中文名称
    location: string                // 平面位置
    elevation: number               // 高程
    section: string                 // 坝段 (如 2号坝段)
    installDate: string             // 埋设时间
    longitude?: number              // 经度
    latitude?: number               // 纬度
    status: 'normal' | 'warning' | 'danger'  // 状态
    latestValue?: number            // 最新测值
    createdAt?: string
}

// 测值类型
export interface MonitoringValue {
    id: string
    pointId: string                 // 关联测点ID
    pointName?: string              // 测点名称
    value: number                   // 测量值
    unit: string                    // 单位 (mm)
    waterLevel?: number             // 库水位
    measuredAt: string              // 测量时间
    createdAt?: string
    isAnomaly?: boolean             // 是否异常
}

// 统计数据类型
export interface Statistics {
    totalPoints: number             // 测点总数
    normalCount: number             // 正常测点数
    warningCount: number            // 警告测点数
    dangerCount: number             // 危险测点数
    latestUpdate: string            // 最近更新时间
}

// 图表数据类型
export interface ChartData {
    labels: string[]
    datasets: {
        name: string
        data: number[]
        color?: string
    }[]
}

// 用户类型
export interface User {
    id: string
    email: string
    phone?: string
    name?: string
    role: 'admin' | 'engineer' | 'viewer'
    createdAt: string
}

// API 响应类型
export interface ApiResponse<T> {
    success: boolean
    data?: T
    error?: string
    message?: string
}

// 异常检测结果
export interface AnomalyResult {
    pointId: string
    pointName: string
    value: number
    threshold: number
    deviation: number               // 偏差百分比
    severity: 'low' | 'medium' | 'high'
    detectedAt: string
}

// 趋势预测结果
export interface TrendPrediction {
    pointId: string
    pointName: string
    predictions: {
        date: string
        value: number
        confidence: number            // 置信度 0-1
    }[]
    trend: 'rising' | 'falling' | 'stable'
}
