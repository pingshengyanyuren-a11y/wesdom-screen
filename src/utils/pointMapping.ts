/**
 * 模型测点名称映射表
 * 将 IFC 模型中的测点构件名称映射到数据库测点名称
 * 
 * IFC 模型命名格式: EX:EX1:239587, IP:IP2:253389 等
 * 数据库命名格式: EX1-2, EX2-4, IP1, TC1-1 等
 */

// 测点类型说明
// EX - 引张线测点
// IP - 倒垂线测点
// TC - 静力水准测点
// UP - 测点（通用）
// P  - 测点（渗压计等）
// DL - 测点（扬压力等）
// WE - 测点（渗流量等）

/**
 * 从 IFC 模型构件名称中提取测点编号
 * @param ifcName 例如 "EX:EX1:239587"
 * @returns 例如 "EX1"
 */
export function extractPointIdFromIfc(ifcName: string): string {
    // 格式: 类型:编号:ID
    const parts = ifcName.split(':')
    if (parts.length >= 2) {
        return parts[1] // 返回 "EX1", "IP2" 等
    }
    return ifcName
}

/**
 * 根据 IFC 测点编号查找匹配的数据库测点
 * 使用模糊匹配逻辑
 * @param ifcPointId 例如 "EX1"
 * @param dbPoints 数据库测点列表
 * @returns 匹配的数据库测点数组
 */
export function findMatchingDbPoints(
    ifcPointId: string,
    dbPoints: Array<{ id: number; name: string; type: string }>
): Array<{ id: number; name: string; type: string }> {
    const baseId = ifcPointId.toUpperCase()

    return dbPoints.filter(point => {
        const dbName = point.name.toUpperCase()

        // 精确匹配 (如 IP1 匹配 IP1)
        if (dbName === baseId) return true

        // 前缀匹配 (如 EX1 匹配 EX1-2, EX1-3, EX1-11 等)
        if (dbName.startsWith(baseId + '-')) return true
        if (dbName.startsWith(baseId + ' ')) return true

        return false
    })
}

/**
 * 完整的映射表 (可手动扩展)
 * 格式: { IFC模型名称: 数据库测点名称 }
 */
export const pointMappingTable: Record<string, string[]> = {
    // 引张线
    'EX1': ['EX1-2', 'EX1-3', 'EX1-4', 'EX1-5', 'EX1-6', 'EX1-7', 'EX1-8', 'EX1-9', 'EX1-10', 'EX1-11'],
    'EX2': ['EX2-2', 'EX2-3', 'EX2-4', 'EX2-5', 'EX2-6', 'EX2-7'],
    'EX3': ['EX3-2', 'EX3-3', 'EX3-4', 'EX3-5'],

    // 倒垂线
    'IP1': ['IP1'],
    'IP2': ['IP2'],
    'IP3': ['IP3'],
    'IP5': ['IP5'],
    'IP6': ['IP6'],
    'IP8': ['IP8'],

    // 静力水准 (TC 可能对应 UP 系列)
    'UPxdb1': ['TC1-1', 'TC1-2', 'TC1-3', 'TC1-4', 'TC1-5'],
    'UPxdb3': ['TC3-1', 'TC3-2', 'TC3-3', 'TC3-4', 'TC3-5'],
}

export default {
    extractPointIdFromIfc,
    findMatchingDbPoints,
    pointMappingTable
}
