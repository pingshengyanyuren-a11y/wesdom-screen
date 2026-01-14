# -*- coding: utf-8 -*-
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config import supabase

class DataProcessor:
    def __init__(self, data_dir, data_source='supabase'):
        self.data_dir = data_dir
        self.data_source = data_source
        self.supabase = supabase
        self.processed_data = None
        self.points_cache = {}
        
    def load_data(self):
        """加载数据"""
        if self.data_source == 'supabase':
            # Supabase 模式下主要依赖实时查询，这里可以预加载一些元数据
            self._load_points_metadata()
        else:
            # CSV 模式 (暂不实现详细逻辑，保持兼容)
            print("Warning: CSV mode not fully implemented in restoration.")
            self.processed_data = pd.DataFrame()

    def _load_points_metadata(self):
        """缓存测点元数据"""
        try:
            if not self.supabase:
                return
            res = self.supabase.table('monitoring_points').select('id, name, type').execute()
            if res.data:
                self.points_cache = {p['name']: p for p in res.data}
                print(f"Loaded metadata for {len(self.points_cache)} points.")
        except Exception as e:
            print(f"Failed to load metadata: {e}")

    def get_points_with_types(self):
        """获取 {name: type} 映射"""
        if not self.points_cache:
            self._load_points_metadata()
        return {name: info['type'] for name, info in self.points_cache.items()}

    def get_point_data(self, point_name, limit=1000):
        """获取指定测点的历史数据"""
        if self.data_source == 'supabase':
            try:
                # 1. 获取 ID
                point_info = self.points_cache.get(point_name)
                if not point_info:
                    # 尝试重新加载
                    self._load_points_metadata()
                    point_info = self.points_cache.get(point_name)
                    if not point_info:
                        return pd.DataFrame()
                
                # 2. 查询数据
                res = self.supabase.table('monitoring_values')\
                    .select('value, measured_at')\
                    .eq('point_id', point_info['id'])\
                    .order('measured_at', desc=True)\
                    .limit(limit)\
                    .execute()
                
                if not res.data:
                    return pd.DataFrame()
                
                df = pd.DataFrame(res.data)
                df['value'] = pd.to_numeric(df['value'])
                df['measure_time'] = pd.to_datetime(df['measured_at'])
                df['type'] = point_info['type']
                df['point_name'] = point_name
                
                # 按时间正序排列
                return df.sort_values('measure_time')
            except Exception as e:
                print(f"Error getting point data for {point_name}: {e}")
                return pd.DataFrame()
        else:
            return pd.DataFrame()

    def process_point_history(self, history, point_name, point_type):
        """处理前端传入的实时历史数据"""
        # 简单转换为 DataFrame
        try:
            df = pd.DataFrame(history)
            df['measure_time'] = pd.to_datetime(df['measure_time'])
            df['value'] = pd.to_numeric(df['value'])
            return df
        except Exception:
            return None
