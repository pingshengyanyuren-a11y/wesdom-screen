/**
 * IFC 模型 Tag 到测点名称的映射表
 * tag 是 IFC 模型构件的唯一标识符
 * 从 IFC 名称 "EX:EX10:239584" 提取，最后的数字即为 tag
 */

// 从 ifc_points.json 提取的 tag -> point_id 映射
export const tagToPointMapping: Record<string, string> = {
    // EX 系列 (引张线)
    "239584": "EX10",
    "239587": "EX1",
    "239590": "EX6",
    "239593": "EX7",
    "239596": "EX9",
    "239599": "EX3",
    "239602": "EX8",
    "239608": "EX5",
    "239611": "EX4",
    "239614": "EX2",

    // IP 系列 (倒垂线)
    "253389": "IP2",
    "257472": "IP3",
    "257492": "IP1",

    // PL 系列
    "258600": "PL1",
    "268515": "IP6",

    // UP 系列 (测点)
    "275992": "UPxdb10",
    "278035": "UPxdb9",
    "278051": "UPxdb1",
    "278067": "UPxdb2",
    "296123": "UPxdb8",
    "296141": "UPxdb7",
    "296157": "UPxdb6",
    "296177": "UPxdb5",
    "296199": "UPxdb4",
    "296217": "UPxdb3",
    "309047": "UPxdb5-1",
    "309059": "UPxdb8-1",
    "309076": "UPxdb8-2",
    "309091": "UPxdb3-1",
    "309102": "UPxdb3-2",

    // P 系列
    "310027": "Pxdb5-1",
    "310097": "Pxdb5-2",
    "310121": "Pxdb5-3",
    "310131": "Pxdb5-4",
    "310147": "Pxdb5-5",
    "310148": "Pxdb5-6",
    "310149": "Pxdb5-7",
    "310182": "Pxdb8-1",
    "310224": "Pxdb8-2",
    "310235": "Pxdb8-3",
    "310266": "Pxdb8-4",
    "310267": "Pxdb8-5",
    "310268": "Pxdb8-6",

    // WE 系列
    "311163": "WExdb2",
    "311213": "WExdb1",

    // UPR 系列
    "312054": "UPxby1",
    "312083": "UPxby2",
    "312099": "UPxby3",
    "312136": "UPxby4",
    "312182": "UPxbz1",
    "312198": "UPxbz2",
    "312222": "UPxbz3",
    "312232": "UPxbz4",

    // DL 系列
    "313546": "DL4",
    "314386": "DL3",
    "316930": "DL2",
    "316940": "DL1",
    "316948": "DL5",
    "316956": "DL6",
    "316964": "DL7",
    "316972": "DL8",
    "316980": "DL9",
    "316988": "DL10"
}

/**
 * 通过 tag 值获取测点 ID
 */
export function getPointIdByTag(tag: string | number): string | undefined {
    return tagToPointMapping[String(tag)]
}

export default {
    tagToPointMapping,
    getPointIdByTag
}
