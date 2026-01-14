/**
 * ML后端API - 深度学习预测服务
 */

// ML后端地址 (通过Vite代理转发到5001)
const ML_API_BASE = '/api'

/**
 * 统一请求封装
 */
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${ML_API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`
    
    // 默认 Header
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    }

    try {
        const response = await fetch(url, { ...options, headers })
        
        if (!response.ok) {
            throw new Error(`HTTP Error: ${response.status} ${response.statusText}`)
        }

        const data = await response.json()
        
        // 后端统一返回格式: { success: boolean, data: any, error?: string }
        if (data.success === false) {
            throw new Error(data.error || 'Unknown backend error')
        }

        return data.data
    } catch (error: any) {
        console.error(`API Request Failed [${endpoint}]:`, error)
        throw error // 继续抛出供调用方处理
    }
}

/**
 * 数据摘要
 */
export interface DataSummary {
    total_records: number
    unique_points: number
    point_list: string[]
    types: Record<string, number>
    date_range: { start: string; end: string }
    statistics: {
        mean: number
        std: number
        min: number
        max: number
    }
}

/**
 * 预测结果
 */
export interface PredictionResult {
    point_name: string
    type: string
    history: number[]
    dates: string[]
    predictions: number[]
    confidence_upper: number[]
    confidence_lower: number[]
    lstm_pred: number[] | null
    stacking_pred: number[] | null
    fusion_pred: number[] | null
    attention_weights?: number[]
    weights: { lstm: number; stacking: number }
    fusion_details?: {
        global_weights: { lstm: number; stacking: number }
        local_weights: { lstm: number; stacking: number }
        confidence_weights: { lstm: number; stacking: number }
        model_consistency: number
        uncertainty_std: number
    }
}

/**
 * 异常检测结果
 */
export interface AnomalyResult {
    point_name: string
    type: string
    current_value: number
    mean: number
    std: number
    z_score: number
    change_rate: number
    severity: 'high' | 'medium' | 'low'
    measure_time: string
}

/**
 * 测点分组
 */
export interface PointsData {
    all_points: string[]
    grouped: Record<string, string[]>
    count: number
}

/**
 * 检查ML后端是否可用
 */
export async function checkMLBackend(): Promise<boolean> {
    try {
        await request('/health', { signal: AbortSignal.timeout(3000) })
        return true
    } catch {
        return false
    }
}

/**
 * 获取数据摘要
 */
export async function getDataSummary(): Promise<DataSummary> {
    return request<DataSummary>('/data_summary')
}

/**
 * 获取所有测点
 */
export async function getPoints(): Promise<PointsData> {
    return request<PointsData>('/points')
}

/**
 * 预测单个测点
 */
export async function predictPoint(
    pointName: string,
    steps: number = 30,
    recentHistory: { measure_time: string; value: number }[] = []
): Promise<PredictionResult> {
    return request<PredictionResult>('/predict', {
        method: 'POST',
        body: JSON.stringify({
            point_name: pointName,
            steps,
            recent_history: recentHistory
        })
    })
}

/**
 * 批量预测
 */
export async function batchPredict(pointNames: string[], steps: number = 30): Promise<Record<string, PredictionResult>> {
    return request<Record<string, PredictionResult>>('/batch_predict', {
        method: 'POST',
        body: JSON.stringify({ point_names: pointNames, steps })
    })
}

/**
 * 获取测点历史数据
 */
export async function getPointHistory(pointName: string, limit: number = 100): Promise<{
    point_name: string
    type: string
    count: number
    dates: string[]
    values: number[]
    statistics: { mean: number; std: number; min: number; max: number }
}> {
    return request(`/point_history?point_name=${encodeURIComponent(pointName)}&limit=${limit}`)
}

/**
 * 训练测点模型
 */
export async function trainPointModel(pointName: string, epochs: number = 30): Promise<{
    point_name: string
    data_count: number
    lstm_trained: boolean
    stacking_trained: boolean
}> {
    return request('/train', {
        method: 'POST',
        body: JSON.stringify({ point_name: pointName, epochs })
    })
}

/**
 * 触发全量训练并存储
 */
export async function triggerBatchTrainAndStore(): Promise<{
    message: string
    total_points: number
    success_count: number
}> {
    return request('/batch_train_and_store', {
        method: 'POST'
    })
}

/**
 * 异常检测
 */
export async function detectAnomalies(): Promise<{
    anomalies: AnomalyResult[]
    total_anomalies: number
    by_severity: { high: number; medium: number; low: number }
}> {
    return request('/anomaly_detection')
}

/**
 * 从数据库获取预先计算好的预测结果（快速！）
 * 这些预测是离线批量计算并保存到数据库的
 * @param pointName 测点名称
 * @returns 预测结果
 */
export async function getCachedPrediction(pointName: string): Promise<{
    predictions: number[]
    confidence_upper: number[]
    confidence_lower: number[]
    predicted_at: string
} | null> {
    const { supabase } = await import('@/lib/supabase')

    const { data, error } = await supabase
        .from('predictions')
        .select('*')
        .eq('point_name', pointName)
        .single()

    if (error || !data) {
        console.warn(`No cached prediction for ${pointName}:`, error)
        return null
    }

    return {
        predictions: data.predictions || [],
        confidence_upper: data.confidence_upper || [],
        confidence_lower: data.confidence_lower || [],
        predicted_at: data.predicted_at || new Date().toISOString()
    }
}

/**
 * 保存预测结果
 */
export async function savePrediction(data: {
    point_name: string
    result_json: any
    predict_steps?: number
    input_range?: string
    is_favorite?: boolean
}): Promise<any> {
    return request('/save_prediction', {
        method: 'POST',
        body: JSON.stringify(data)
    })
}

/**
 * 获取预测历史
 */
export async function getPredictionHistory(params?: {
    point_name?: string
    is_favorite?: boolean
    limit?: number
}): Promise<any[]> {
    const query = new URLSearchParams()
    if (params?.point_name) query.append('point_name', params.point_name)
    if (params?.is_favorite) query.append('is_favorite', 'true')
    if (params?.limit) query.append('limit', params.limit.toString())

    return request(`/prediction_history?${query.toString()}`)
}

/**
 * 切换收藏状态
 */
export async function toggleFavorite(id: string, is_favorite: boolean): Promise<any> {
    return request('/toggle_favorite', {
        method: 'POST',
        body: JSON.stringify({ id, is_favorite })
    })
}
