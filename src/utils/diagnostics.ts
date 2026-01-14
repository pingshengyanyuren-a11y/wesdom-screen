/**
 * 系统自检与诊断工具
 * 用于运行时验证各模块功能的完整性与可用性
 */
import * as mlApi from '@/api/ml'

export interface DiagnosticResult {
    id: string
    name: string
    status: 'pending' | 'success' | 'failure' | 'running'
    message?: string
    timestamp: number
}

export class SystemDiagnostician {
    private results: DiagnosticResult[] = []
    private onUpdate: (results: DiagnosticResult[]) => void

    constructor(onUpdate: (results: DiagnosticResult[]) => void) {
        this.onUpdate = onUpdate
        this.reset()
    }

    private reset() {
        this.results = [
            { id: 'backend_conn', name: '后端服务连接', status: 'pending', timestamp: 0 },
            { id: 'data_integrity', name: '数据完整性检查', status: 'pending', timestamp: 0 },
            { id: 'prediction_flow', name: 'AI预测链路测试', status: 'pending', timestamp: 0 },
            { id: 'anomaly_detection', name: '异常检测服务', status: 'pending', timestamp: 0 }
        ]
        this.notify()
    }

    private notify() {
        this.onUpdate([...this.results])
    }

    private updateResult(id: string, status: DiagnosticResult['status'], message?: string) {
        const item = this.results.find(r => r.id === id)
        if (item) {
            item.status = status
            item.message = message
            item.timestamp = Date.now()
            this.notify()
        }
    }

    /**
     * 运行所有诊断测试
     */
    async runDiagnostics() {
        this.reset()

        // 1. 检查后端连接
        await this.runTest('backend_conn', async () => {
            const isConnected = await mlApi.checkMLBackend()
            if (!isConnected) throw new Error('无法连接到ML后端服务 (Connection Refused)')
            return '连接正常'
        })

        // 如果后端连不上，后续测试无意义
        if (this.results.find(r => r.id === 'backend_conn')?.status === 'failure') {
            return
        }

        // 2. 检查数据完整性
        await this.runTest('data_integrity', async () => {
            const summary = await mlApi.getDataSummary()
            if (summary.total_records === 0) throw new Error('数据库中无监测记录')
            if (summary.unique_points === 0) throw new Error('未发现有效测点')
            return `发现 ${summary.unique_points} 个测点，共 ${summary.total_records} 条记录`
        })

        // 3. AI预测链路测试 (使用第一个可用测点)
        await this.runTest('prediction_flow', async () => {
            const pointsData = await mlApi.getPoints()
            const testPoint = pointsData.all_points[0]
            if (!testPoint) throw new Error('无可用测点进行预测测试')
            
            // 模拟小范围预测
            const result = await mlApi.predictPoint(testPoint, 7)
            if (!result.predictions || result.predictions.length !== 7) {
                throw new Error('预测结果格式不正确或长度不匹配')
            }
            return `测点 ${testPoint} 预测成功 (LSTM权重: ${(result.weights.lstm * 100).toFixed(0)}%)`
        })

        // 4. 异常检测服务
        await this.runTest('anomaly_detection', async () => {
            const result = await mlApi.detectAnomalies()
            if (typeof result.total_anomalies !== 'number') throw new Error('返回格式无效')
            return `检测服务正常，当前发现 ${result.total_anomalies} 个异常`
        })
    }

    private async runTest(id: string, testFn: () => Promise<string>) {
        this.updateResult(id, 'running')
        try {
            const successMsg = await testFn()
            this.updateResult(id, 'success', successMsg)
        } catch (e: any) {
            this.updateResult(id, 'failure', e.message || '未知错误')
        }
    }
}
