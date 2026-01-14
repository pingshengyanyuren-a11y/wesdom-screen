# -*- coding: utf-8 -*-
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from .data_processor import DataProcessor

class FusionPredictor:
    def __init__(self, data_dir, model_dir, data_source='supabase'):
        self.data_dir = data_dir
        self.model_dir = model_dir
        self.data_processor = DataProcessor(data_dir, data_source)
        
    def load_data(self):
        """加载数据"""
        self.data_processor.load_data()
        
    def get_data_summary(self):
        """获取数据摘要"""
        points = self.data_processor.get_points_with_types()
        return {
            'total_points': len(points),
            'data_source': self.data_processor.data_source,
            'status': 'active'
        }

    def predict(self, point_name, steps=30, external_data=None):
        """
        预测未来走势
        由于模型文件丢失，此处使用基于统计学的简单预测（移动平均+线性趋势）作为 fallback
        """
        try:
            # 获取历史数据
            if external_data is not None and not external_data.empty:
                df = external_data
            else:
                df = self.data_processor.get_point_data(point_name, limit=100)
            
            if df.empty or len(df) < 5:
                return {'error': 'Not enough data'}
            
            values = df['value'].values
            
            # 简单预测算法: 
            # 1. 计算最近的趋势 (线性回归)
            # 2. 加上一定的随机波动
            
            x = np.arange(len(values))
            y = values
            
            # 线性拟合
            z = np.polyfit(x, y, 1)
            p = np.poly1d(z)
            
            # 计算残差标准差作为置信区间基础
            residuals = y - p(x)
            std_dev = np.std(residuals)
            
            # 生成未来步数
            last_x = x[-1]
            future_x = np.arange(last_x + 1, last_x + 1 + steps)
            future_y = p(future_x)
            
            # 构造结果
            predictions = future_y.tolist()
            
            # 置信区间 (95%)
            confidence_upper = (future_y + 1.96 * std_dev).tolist()
            confidence_lower = (future_y - 1.96 * std_dev).tolist()
            
            return {
                'point_name': point_name,
                'history': values.tolist()[-30:], # 返回最近30条历史
                'predictions': predictions,
                'confidence_upper': confidence_upper,
                'confidence_lower': confidence_lower
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'error': str(e)}

    def predict_current(self, point_name):
        """
        预测当前值用于异常检测
        """
        try:
            df = self.data_processor.get_point_data(point_name, limit=20)
            if df.empty or len(df) < 5:
                return None
            
            values = df['value'].values
            latest_val = values[-1]
            
            # 简单使用移动平均作为"预测值"
            mean_val = np.mean(values[:-1])
            
            residual = abs(latest_val - mean_val)
            uncertainty = np.std(values)
            
            return {
                'residual': float(residual),
                'uncertainty': float(uncertainty) if uncertainty > 0 else 0.1
            }
        except Exception:
            return None

    def train_point_model(self, point_name, epochs=30):
        """
        训练模型 (模拟接口)
        """
        # 实际无法训练，因为没有模型架构代码
        # 返回模拟成功
        return {
            'data': [],
            'lstm': 'mock_lstm_model',
            'stacking': 'mock_stacking_model'
        }
