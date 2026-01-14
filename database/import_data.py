"""
文件名: import_data.py
功能: 将监测资料 Excel 数据导入到 Supabase 数据库
作者: 章涵硕
使用方法: python import_data.py
"""

import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import os

# Supabase 配置
SUPABASE_URL = "https://urkuikqshznvmefzmdlh.supabase.co"
SUPABASE_KEY = "sb_publishable_qMACYNzXYCmchEcwvGbejw_icvrMDgK"

# 数据文件路径 - 使用绝对路径
DATA_DIR = r"c:\Users\ASUS\Desktop\领导快乐屏\课设材料\数据"

def get_supabase_client() -> Client:
    """创建 Supabase 客户端"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def import_monitoring_points(supabase: Client):
    """导入测点数据"""
    print("📍 开始导入测点数据...")
    
    # 读取测点 Excel
    df = pd.read_excel(os.path.join(DATA_DIR, "测点.xlsx"))
    
    # 根据仪器编号判断类型
    def get_type(name: str) -> str:
        if name.startswith("EX"):
            return "tension_wire"
        elif name.startswith("TC"):
            return "hydrostatic_level"
        elif name.startswith("IP"):
            return "plumb_line"
        return "tension_wire"
    
    points = []
    for _, row in df.iterrows():
        point = {
            "name": str(row["仪器编号"]).strip(),
            "type": get_type(str(row["仪器编号"])),
            "location": str(row["平面位置"]) if pd.notna(row["平面位置"]) else None,
            "elevation": float(row["高程"]) if pd.notna(row["高程"]) else None,
            "section": str(row["部位"]) if pd.notna(row["部位"]) else None,
            "install_date": str(row["埋设时间"])[:10] if pd.notna(row["埋设时间"]) else None,
            "status": "normal"
        }
        points.append(point)
    
    # 批量插入
    result = supabase.table("monitoring_points").upsert(points, on_conflict="name").execute()
    print(f"✅ 成功导入 {len(points)} 个测点")
    return result

def import_tension_wire_values(supabase: Client):
    """导入引张线测值数据"""
    print("📊 开始导入引张线数据...")
    
    # 读取引张线 Excel
    df = pd.read_excel(os.path.join(DATA_DIR, "引张线.xlsx"))
    
    # 获取已导入的测点 ID 映射
    points_result = supabase.table("monitoring_points").select("id, name").execute()
    point_map = {p["name"]: p["id"] for p in points_result.data}
    
    values = []
    # 遍历每一行数据
    for _, row in df.iterrows():
        measured_at = row["观测时间"]
        water_level = row["库水位"] if pd.notna(row["库水位"]) else None
        
        # 遍历每个测点列
        for col in df.columns:
            if col in ["观测时间", "库水位"] or col.startswith("IP"):
                continue
            
            if col in point_map and pd.notna(row[col]):
                values.append({
                    "point_id": point_map[col],
                    "value": float(row[col]),
                    "unit": "mm",
                    "water_level": float(water_level) if water_level else None,
                    "measured_at": str(measured_at)
                })
    
    # 分批插入 (每批 500 条)
    batch_size = 500
    for i in range(0, len(values), batch_size):
        batch = values[i:i + batch_size]
        supabase.table("monitoring_values").insert(batch).execute()
        print(f"  - 已导入 {min(i + batch_size, len(values))}/{len(values)} 条")
    
    print(f"✅ 成功导入 {len(values)} 条引张线测值")

def import_hydrostatic_level_values(supabase: Client):
    """导入静力水准测值数据"""
    print("📊 开始导入静力水准数据...")
    
    df = pd.read_excel(os.path.join(DATA_DIR, "静力水准.xlsx"))
    
    points_result = supabase.table("monitoring_points").select("id, name").execute()
    point_map = {p["name"]: p["id"] for p in points_result.data}
    
    values = []
    for _, row in df.iterrows():
        measured_at = row["观测时间"]
        
        for col in df.columns:
            if col == "观测时间":
                continue
            
            if col in point_map and pd.notna(row[col]):
                values.append({
                    "point_id": point_map[col],
                    "value": float(row[col]),
                    "unit": "mm",
                    "measured_at": str(measured_at)
                })
    
    batch_size = 500
    for i in range(0, len(values), batch_size):
        batch = values[i:i + batch_size]
        supabase.table("monitoring_values").insert(batch).execute()
        print(f"  - 已导入 {min(i + batch_size, len(values))}/{len(values)} 条")
    
    print(f"✅ 成功导入 {len(values)} 条静力水准测值")

def import_plumb_line_values(supabase: Client):
    """导入倒垂线测值数据"""
    print("📊 开始导入倒垂线数据...")
    
    df = pd.read_excel(os.path.join(DATA_DIR, "倒垂线.xlsx"))
    
    points_result = supabase.table("monitoring_points").select("id, name").execute()
    point_map = {p["name"]: p["id"] for p in points_result.data}
    
    values = []
    for _, row in df.iterrows():
        measured_at = row["观测时间"]
        water_level = row["库水位"] if pd.notna(row.get("库水位")) else None
        
        # 倒垂线有左右岸和上下游两个方向
        for col in df.columns:
            if col in ["观测时间", "库水位"]:
                continue
            
            # 提取测点名称 (如 IP3左右岸 -> IP3)
            point_name = col.replace("左右岸", "").replace("上下游", "")
            
            if point_name in point_map and pd.notna(row[col]):
                values.append({
                    "point_id": point_map[point_name],
                    "value": float(row[col]),
                    "unit": "mm",
                    "water_level": float(water_level) if water_level else None,
                    "measured_at": str(measured_at)
                })
    
    # 去重 (同一测点同一时间可能有多个方向的数据)
    unique_values = []
    seen = set()
    for v in values:
        key = (v["point_id"], v["measured_at"])
        if key not in seen:
            seen.add(key)
            unique_values.append(v)
    
    batch_size = 500
    for i in range(0, len(unique_values), batch_size):
        batch = unique_values[i:i + batch_size]
        supabase.table("monitoring_values").insert(batch).execute()
        print(f"  - 已导入 {min(i + batch_size, len(unique_values))}/{len(unique_values)} 条")
    
    print(f"✅ 成功导入 {len(unique_values)} 条倒垂线测值")

def main():
    """主函数"""
    print("=" * 50)
    print("智慧水利监测平台 - 数据导入工具")
    print("=" * 50)
    
    supabase = get_supabase_client()
    
    try:
        # 1. 导入测点
        import_monitoring_points(supabase)
        
        # 2. 导入引张线数据
        import_tension_wire_values(supabase)
        
        # 3. 导入静力水准数据
        import_hydrostatic_level_values(supabase)
        
        # 4. 导入倒垂线数据
        import_plumb_line_values(supabase)
        
        print("\n" + "=" * 50)
        print("🎉 所有数据导入完成！")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ 导入失败: {e}")
        raise

if __name__ == "__main__":
    main()
