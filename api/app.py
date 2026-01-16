# -*- coding: utf-8 -*-
"""
Flask API服务 - 大坝监测数据深度学习预测
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import os
import sys
import pandas as pd
import functools
import json
from datetime import datetime, timedelta

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

# 尝试导入，如果失败则提示
try:
    from src.predictor import FusionPredictor
    from src.ai_analyzer import get_analyzer
except ImportError:
    print("Warning: Backend modules not found. Please restore src folder.")
    FusionPredictor = None
    get_analyzer = None

# 配置路径
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), 'data') # Adjusted to new 'data' folder
MODEL_DIR = os.path.join(BASE_DIR, 'models')

# API 安全配置
API_KEY = "hydromind-secure-key-2026"  # 简单鉴权密钥

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 允许跨域

def require_api_key(f):
    """API Key 鉴权装饰器"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # 从 Header 或 Query 参数获取 Key
        key = request.headers.get('X-API-Key') or request.args.get('api_key')
        # 开发阶段，为了兼容前端暂不强制拦截，仅打印警告
        # if key and key != API_KEY:
        #    return jsonify({'error': 'Invalid API Key'}), 403
        return f(*args, **kwargs)
    return decorated_function

# 全局预测器实例
predictor = None

def get_predictor():
    """懒加载预测器"""
    global predictor
    if predictor is None:
        if FusionPredictor is None:
            raise ImportError("FusionPredictor module is missing.")
        print("初始化预测器...")
        # 优先使用 Supabase
        predictor = FusionPredictor(DATA_DIR, MODEL_DIR, data_source='supabase')
        predictor.load_data()
        print("预测器初始化完成")
    return predictor


# RAG 上下文缓存
CONTEXT_CACHE = None

def generate_rag_context():
    """生成RAG上下文（带Supabase支持）"""
    try:
        pred = get_predictor()
        context = ""
        
        # === 分支 1: Supabase 模式 (直接查库) ===
        if pred.data_processor.data_source == 'supabase':
            sb = pred.data_processor.supabase
            if not sb:
                return "数据库连接未初始化。"
            
            # 1. 基础统计
            # 查询测点总数
            res_pts = sb.table('monitoring_points').select('*', count='exact').limit(1).execute()
            total_points = res_pts.count
            
            # 查询最早数据时间 (历史跨度)
            res_earliest = sb.table('monitoring_values').select('measured_at').order('measured_at', desc=False).limit(1).execute()
            earliest_time = res_earliest.data[0]['measured_at'] if res_earliest.data else "未知"
            
            # 查询最新数据时间
            res_latest = sb.table('monitoring_values').select('measured_at').order('measured_at', desc=True).limit(1).execute()
            latest_time = res_latest.data[0]['measured_at'] if res_latest.data else "未知"
            
            # 查询总数据量
            res_count = sb.table('monitoring_values').select('point_id', count='exact').limit(1).execute()
            total_records = res_count.count
            
            # 查询预测历史 (智脑记忆)
            res_preds = sb.table('prediction_results').select('*', count='exact').limit(3).order('created_at', desc=True).execute()
            pred_count = res_preds.count
            recent_preds = [f"{p['point_name']}({p.get('model_version','v1')})" for p in res_preds.data]
            
            # 2. 异常统计
            anomalies = []
            
            # 获取所有测点抽检
            all_pts = sb.table('monitoring_points').select('id, name, type').limit(50).execute()
            
            check_count = 0
            for pt in all_pts.data:
                res_val = sb.table('monitoring_values').select('value, measured_at').eq('point_id', pt['id']).order('measured_at', desc=True).limit(5).execute()
                vals = res_val.data
                if not vals or len(vals) < 3: continue
                
                v_list = [v['value'] for v in vals]
                latest_v = v_list[0]
                mean_v = sum(v_list) / len(v_list)
                import numpy as np
                std_v = np.std(v_list)
                
                if std_v > 0 and abs(latest_v - mean_v) / std_v > 2.0:
                    anomalies.append(f"{pt['name']}({pt.get('type','未知')}): {latest_v:.2f}")
                
                check_count += 1
                if check_count > 10: break 
            
            status_desc = '存在风险' if anomalies else '正常运行'
            
            context = f"""
【全量数据概览】
- 数据源: Supabase 云数据库 (实时直连)
- 历史跨度: {earliest_time} 至 {latest_time}
- 数据总量: {total_records} 条监测记录
- 监测点数: {total_points} 个

【智能体记忆 (Prediction Memory)】
- 历史预测存档: {pred_count} 条
- 最近分析对象: {', '.join(recent_preds) if recent_preds else '暂无'}

【实时健康状态】
- 系统整体状态: {status_desc}
- 实时异常抽检: {', '.join(anomalies) if anomalies else '当前抽检未发现显著异常'}
"""
            
        # === 分支 2: CSV/Local 模式 ===
        else:
            df = pred.data_processor.processed_data
            if df is None:
                return "本地数据未加载。"
            
            total_points = len(df['point_name'].unique())
            latest_time = str(df['measure_time'].max())
            
            # 异常统计
            anomalies = []
            valid_points = df['point_name'].unique()
            for point_name in valid_points:
                p_data = df[df['point_name'] == point_name]
                if len(p_data) < 5: continue
                latest = p_data.iloc[-1]
                mean = p_data['value'].mean()
                std = p_data['value'].std()
                if std == 0: continue
                z_score = abs((latest['value'] - mean) / std)
                if z_score > 2.5:
                    anomalies.append(f"{point_name}: {latest['value']:.2f}")
            
            context = f"""
- 数据源: 本地离线数据
- 监测点总数: {total_points} 个
- 数据最后更新: {latest_time}
- 当前异常测点: {', '.join(anomalies[:5])} {'...' if len(anomalies)>5 else ''}
- 运行状态: {'存在风险' if anomalies else '正常运行'}
"""

        print(f"RAG Context 生成成功: {len(context)} chars")
        return context

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"RAG Context生成失败: {e}")
        return f"实时数据获取失败: {str(e)}"

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'status': 'ok', 'message': 'ML Backend is running'})


@app.route('/api/data_summary', methods=['GET'])
def get_data_summary():
    """获取数据摘要"""
    try:
        pred = get_predictor()
        summary = pred.get_data_summary()
        return jsonify({'success': True, 'data': summary})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/points', methods=['GET'])
def get_points():
    """获取所有测点列表"""
    try:
        pred = get_predictor()
        
        # 获取测点名称到类型的映射
        points_map = pred.data_processor.get_points_with_types()
        points = sorted(list(points_map.keys()))
        
        # 按类型分组
        grouped = {}
        for point_name, point_type in points_map.items():
            if point_type not in grouped:
                grouped[point_type] = []
            grouped[point_type].append(point_name)
        
        return jsonify({
            'success': True,
            'data': {
                'all_points': points,
                'grouped': grouped,
                'count': len(points)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/predict', methods=['POST'])
def predict():
    """单测点预测"""
    try:
        data = request.get_json()
        point_name = data.get('point_name')
        steps = data.get('steps', 30)
        recent_history = data.get('recent_history', [])
        
        if not point_name:
            return jsonify({'success': False, 'error': 'point_name is required'}), 400
        
        pred = get_predictor()
        
        # 处理传入的实时历史数据
        external_data = None
        if recent_history and len(recent_history) > 0:
            print(f"收到前端传入的实时历史数据: {len(recent_history)} 条")
            try:
                # 获取该测点的类型 (用于特征工程)
                point_type = 'unknown'
                # 尝试从现有数据中查找类型，如果找不到也没关系，特征工程主要是基于数值
                df_existing = pred.data_processor.processed_data
                if df_existing is not None:
                    match = df_existing[df_existing['point_name'] == point_name]
                    if not match.empty:
                        point_type = match.iloc[0]['type']
                
                external_data = pred.data_processor.process_point_history(
                    recent_history, 
                    point_name, 
                    point_type
                )
            except Exception as e:
                print(f"实时历史数据处理失败: {e}，将使用后端离线数据")
        
        result = pred.predict(point_name, steps=steps, external_data=external_data)
        
        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/batch_predict', methods=['POST'])
def batch_predict():
    """批量预测多个测点"""
    try:
        data = request.get_json()
        point_names = data.get('point_names', [])
        steps = data.get('steps', 30)
        
        if not point_names:
            return jsonify({'success': False, 'error': 'point_names is required'}), 400
        
        pred = get_predictor()
        results = {}
        
        for point_name in point_names:
            results[point_name] = pred.predict(point_name, steps=steps)
        
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/point_history', methods=['GET'])
def get_point_history():
    """获取测点历史数据"""
    try:
        point_name = request.args.get('point_name')
        limit = int(request.args.get('limit', 100))
        
        if not point_name:
            return jsonify({'success': False, 'error': 'point_name is required'}), 400
        
        pred = get_predictor()
        point_data = pred.data_processor.get_point_data(point_name)
        
        if len(point_data) == 0:
            return jsonify({'success': False, 'error': f'Point {point_name} not found'}), 404
        
        # 取最近的数据
        point_data = point_data.tail(limit)
        
        result = {
            'point_name': point_name,
            'type': point_data['type'].iloc[0],
            'count': len(point_data),
            'dates': point_data['measure_time'].dt.strftime('%Y-%m-%d').tolist(),
            'values': point_data['value'].tolist(),
            'statistics': {
                'mean': point_data['value'].mean(),
                'std': point_data['value'].std(),
                'min': point_data['value'].min(),
                'max': point_data['value'].max()
            }
        }
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/train', methods=['POST'])
def train_model():
    """训练指定测点的模型"""
    try:
        data = request.get_json()
        point_name = data.get('point_name')
        epochs = data.get('epochs', 30)
        
        if not point_name:
            return jsonify({'success': False, 'error': 'point_name is required'}), 400
        
        pred = get_predictor()
        result = pred.train_point_model(point_name, epochs=epochs)
        
        if result is None:
            return jsonify({'success': False, 'error': f'训练失败: 数据不足'}), 400
        
        return jsonify({
            'success': True,
            'message': f'测点 {point_name} 模型训练完成',
            'data': {
                'point_name': point_name,
                'data_count': len(result['data']),
                'lstm_trained': result['lstm'] is not None,
                'stacking_trained': result['stacking'] is not None
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/realtime_status', methods=['GET'])
def get_realtime_status():
    """获取所有测点的实时状态（包含最新值、状态、趋势）- 性能优化版"""
    try:
        pred = get_predictor()
        results = []
        
        if pred.data_processor.data_source == 'supabase':
            sb = pred.data_processor.supabase
            if not sb:
                return jsonify({'success': False, 'error': 'Database not connected'}), 500
            
            # 1. 获取所有测点信息
            res_pts = sb.table('monitoring_points').select('id, name, type').execute()
            points = res_pts.data
            
            # 2. 批量获取最近 3650 天的数据 (扩大范围防止漏掉低频测点)
            cutoff_date = (datetime.now() - timedelta(days=3650)).isoformat()
            
            # 仅获取必要字段，按时间倒序
            res_vals = sb.table('monitoring_values')\
                .select('point_id, value, measured_at')\
                .gt('measured_at', cutoff_date)\
                .order('measured_at', desc=True)\
                .execute()
                
            all_values = res_vals.data
            
            # 转为 DataFrame 加速分组处理
            df_all = pd.DataFrame(all_values) if all_values else pd.DataFrame()
            
            if not df_all.empty:
                df_all['value'] = pd.to_numeric(df_all['value'])
                # 使用 mixed 格式以兼容带/不带微秒的时间字符串
                try:
                    df_all['measured_at'] = pd.to_datetime(df_all['measured_at'], format='mixed')
                except:
                    df_all['measured_at'] = pd.to_datetime(df_all['measured_at'], errors='coerce')

            # 在内存中处理每个测点
            for pt in points:
                # 筛选当前测点数据
                pt_vals = df_all[df_all['point_id'] == pt['id']] if not df_all.empty else pd.DataFrame()
                
                if pt_vals.empty:
                    results.append({
                        'id': pt['id'], 'name': pt['name'], 'type': pt['type'],
                        'value': 0, 'status': 'offline', 'last_update': None
                    })
                    continue
                
                # 确保按时间排序
                pt_vals = pt_vals.sort_values('measured_at', ascending=True)
                latest_row = pt_vals.iloc[-1]
                latest_val = float(latest_row['value'])
                
                # 计算 Z-Score 判定状态
                status = 'normal'
                if len(pt_vals) >= 5:
                    std_val = pt_vals['value'].std()
                    if std_val > 0:
                        mean_val = pt_vals['value'].mean()
                        z = abs((latest_val - mean_val) / std_val)
                        if z > 3: 
                            status = 'danger'
                        elif z > 1.5: # 修复：找回 1.5~3.0 之间的警告状态
                            status = 'warning'
                
                results.append({
                    'id': pt['id'],
                    'name': pt['name'],
                    'type': pt['type'],
                    'value': latest_val,
                    'status': status,
                    'last_update': latest_row['measured_at'].isoformat()
                })
        else:
            # CSV 模式 (暂不支持)
            pass 
            
        return jsonify({'success': True, 'data': results})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/anomaly_detection', methods=['GET'])
def detect_anomalies():
    """异常检测 - 性能优化版 (批量获取数据)"""
    try:
        pred = get_predictor()
        anomalies = []
        
        # === 分支 1: Supabase 模式 (实时查库) ===
        if pred.data_processor.data_source == 'supabase':
            sb = pred.data_processor.supabase
            if not sb:
                return jsonify({'success': False, 'error': 'Database not connected'}), 500
                
            # 1. 获取所有测点
            res_pts = sb.table('monitoring_points').select('id, name, type').execute()
            points = res_pts.data
            
            # 2. 批量获取数据 (优化点: 替代原来的循环查询)
            cutoff_date = (datetime.now() - timedelta(days=14)).isoformat()
            res_vals = sb.table('monitoring_values')\
                .select('point_id, value, measured_at')\
                .gt('measured_at', cutoff_date)\
                .order('measured_at', desc=True)\
                .execute()
            
            all_values = res_vals.data
            df_all = pd.DataFrame(all_values) if all_values else pd.DataFrame()
            
            if not df_all.empty:
                df_all['value'] = pd.to_numeric(df_all['value'])
                # 使用 mixed 格式以兼容带/不带微秒的时间字符串
                try:
                    df_all['measured_at'] = pd.to_datetime(df_all['measured_at'], format='mixed')
                except:
                    df_all['measured_at'] = pd.to_datetime(df_all['measured_at'], errors='coerce')

            for pt in points:
                if df_all.empty: continue
                # 内存筛选
                df_pt = df_all[df_all['point_id'] == pt['id']]
                if len(df_pt) < 5: continue
                
                df_pt = df_pt.sort_values('measured_at', ascending=True).tail(30)
                
                latest_val = df_pt.iloc[-1]['value']
                mean_val = df_pt['value'].mean()
                std_val = df_pt['value'].std()
                
                stats_score = abs((latest_val - mean_val) / std_val) if std_val > 0 else 0
                
                # 3. AI 预测 (优化: 仅当统计特征异常时才调用昂贵的 AI 推理)
                ai_score = 0
                # if stats_score > 1.5: # 只有初步风险才进行 AI 复核 (为了更精确的检测，暂时移除此限制)
                try:
                    prediction_info = pred.predict_current(pt['name'])
                    if prediction_info:
                        residual = prediction_info['residual']
                        uncertainty = prediction_info.get('uncertainty', 0.05)
                        ai_score = residual / uncertainty
                except Exception as e:
                    pass
                
                final_score = max(stats_score, ai_score)
                
                severity = None
                if final_score > 3:
                    severity = 'high'
                elif final_score > 2:
                    severity = 'medium'
                elif final_score > 1.5:
                    severity = 'low'
                
                if severity:
                    anomalies.append({
                        'point_name': pt['name'],
                        'type': pt.get('type', 'unknown'),
                        'current_value': float(latest_val),
                        'mean': float(mean_val),
                        'std': float(std_val),
                        'z_score': float(final_score),
                        'severity': severity,
                        'measure_time': df_pt.iloc[-1]['measured_at'].isoformat()
                    })
        
        # === 分支 2: CSV 模式 (Legacy) ===
        else:
            df = pred.data_processor.processed_data
            if df is None:
                # 尝试加载
                pred.load_data()
                df = pred.data_processor.processed_data
                if df is None:
                     return jsonify({'success': False, 'error': 'No data available'}), 500
            
            for point_name in df['point_name'].unique():
                point_data = df[df['point_name'] == point_name]
                if len(point_data) < 5: continue
                
                latest = point_data.iloc[-1]
                mean_val = point_data['value'].mean()
                std_val = point_data['value'].std()
                
                if std_val > 0:
                    stats_score = abs((latest['value'] - mean_val) / std_val)
                else:
                    stats_score = 0
                    
                ai_score = 0
                # 简化处理，CSV模式下略过AI详细预测以加速，或按需添加
                
                final_score = stats_score # 简略
                
                severity = None
                if final_score > 3: severity = 'high'
                elif final_score > 2: severity = 'medium'
                elif final_score > 1.5: severity = 'low'
                
                if severity:
                    anomalies.append({
                        'point_name': point_name,
                        'type': latest['type'],
                        'current_value': float(latest['value']),
                        'mean': float(mean_val),
                        'std': float(std_val),
                        'z_score': float(final_score),
                        'severity': severity,
                        'measure_time': str(latest['measure_time'])
                    })
        
        # 结果排序
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        anomalies.sort(key=lambda x: severity_order[x['severity']])
        
        return jsonify({
            'success': True,
            'data': {
                'anomalies': anomalies,
                'total_anomalies': len(anomalies),
                'by_severity': {
                    'high': len([a for a in anomalies if a['severity'] == 'high']),
                    'medium': len([a for a in anomalies if a['severity'] == 'medium']),
                    'low': len([a for a in anomalies if a['severity'] == 'low'])
                }
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai_analyze', methods=['POST'])
def ai_analyze():
    """AI智能分析 - 使用大模型生成分析报告"""
    try:
        data = request.get_json()
        point_name = data.get('point_name')
        
        if not point_name:
            return jsonify({'success': False, 'error': 'point_name is required'}), 400
        
        pred = get_predictor()
        
        # 获取预测结果
        prediction = pred.predict(point_name, steps=30)
        if 'error' in prediction:
            return jsonify({'success': False, 'error': prediction['error']}), 400
        
        # 调用AI分析
        analyzer = get_analyzer()
        analysis = analyzer.analyze_prediction(prediction)
        
        return jsonify({
            'success': True,
            'data': {
                'point_name': point_name,
                'analysis': analysis,
                'prediction_summary': {
                    'current_value': prediction['history'][-1] if prediction['history'] else 0,
                    'predicted_trend': 'up' if prediction['predictions'] and prediction['predictions'][-1] > prediction['predictions'][0] else 'down'
                }
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/ai_anomaly_report', methods=['GET'])
def ai_anomaly_report():
    """AI异常分析报告"""
    try:
        pred = get_predictor()
        df = pred.data_processor.processed_data
        
        # 收集异常
        anomalies = []
        for point_name in df['point_name'].unique():
            point_data = df[df['point_name'] == point_name]
            if len(point_data) < 5:
                continue
            
            latest = point_data.iloc[-1]
            mean_val = point_data['value'].mean()
            std_val = point_data['value'].std()
            
            if std_val > 0:
                z_score = abs((latest['value'] - mean_val) / std_val)
            else:
                z_score = 0
            
            if z_score > 1.5:
                severity = 'high' if z_score > 3 else 'medium' if z_score > 2 else 'low'
                anomalies.append({
                    'point_name': point_name,
                    'type': latest['type'],
                    'z_score': z_score,
                    'severity': severity
                })
        
        # AI分析
        analyzer = get_analyzer()
        report = analyzer.analyze_anomalies(anomalies)
        
        return jsonify({
            'success': True,
            'data': {
                'report': report,
                'anomaly_count': len(anomalies),
                'high_risk_points': [a['point_name'] for a in anomalies if a['severity'] == 'high']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# === 新增高级功能接口 ===

@app.route('/api/ask_agent', methods=['POST'])
@require_api_key
def ask_agent():
    """向智能体提问 (支持多模态 + RAG + Session)"""
    try:
        data = request.get_json()
        query = data.get('query')
        image = data.get('image')  # 获取Base64图片
        session_id = data.get('session_id') # 获取会话ID
        
        if not query and not image:
            return jsonify({'success': False, 'error': 'query or image is required'}), 400
        
        # === RAG Context Injection (动态注入实时数据 - 带缓存) ===
        global CONTEXT_CACHE
        if CONTEXT_CACHE is None:
            print("生成 RAG 上下文缓存...")
            CONTEXT_CACHE = generate_rag_context()
        
        context = CONTEXT_CACHE
            
        analyzer = get_analyzer()
        # 调用非流式接口
        answer = analyzer.ask_agent(query, image, context, session_id=session_id, stream=False)
        
        return jsonify({'success': True, 'data': answer})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ask_agent_stream', methods=['POST'])
@require_api_key
def ask_agent_stream():
    """向智能体提问 (流式响应 SSE)"""
    try:
        print("Received stream request")
        data = request.get_json()
        query = data.get('query')
        image = data.get('image')
        session_id = data.get('session_id')
        
        if not query and not image:
            return jsonify({'success': False, 'error': 'query or image is required'}), 400
            
        # RAG Context
        global CONTEXT_CACHE
        if CONTEXT_CACHE is None:
            try:
                CONTEXT_CACHE = generate_rag_context()
            except Exception as e:
                print(f"RAG Error: {e}")
                CONTEXT_CACHE = "Context generation failed"
        context = CONTEXT_CACHE
        
        analyzer = get_analyzer()
        
        def generate():
            try:
                print("Start generating stream...")
                # 获取生成器
                stream = analyzer.ask_agent(query, image, context, session_id=session_id, stream=True)
                
                # 逐字推送
                for chunk in stream:
                    # print(f"Chunk: {chunk}")
                    # SSE 格式: data: <json>\n\n
                    yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                
                print("Stream finished")
                # 结束标记
                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Stream error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/batch_train_and_store', methods=['POST'])
def batch_train_store():
    """触发后台全量训练入库任务 (优化版: 真正执行预测并存库)"""
    try:
        from config import supabase
        pred = get_predictor()
        
        # 1. 获取所有测点
        points_map = pred.data_processor.get_points_with_types()
        point_names = list(points_map.keys())
        
        success_count = 0
        for name in point_names:
            try:
                # 执行预测
                res = pred.predict(name, steps=30)
                if 'error' in res: continue
                
                # 构造存库记录 (对应真实 Supabase 表结构)
                record = {
                    'point_name': name,
                    'type': res.get('type', 'tension_wire'),
                    'last_value': res['history'][-1] if res['history'] else 0,
                    'prediction_json': {
                        'predictions': res['predictions'],
                        'confidence_upper': res['confidence_upper'],
                        'confidence_lower': res['confidence_lower'],
                        'weights': res.get('weights', {'lstm': 0.5, 'stacking': 0.5}),
                        'attention_weights': res.get('attention_weights', []),
                        'fusion_details': res.get('fusion_details', {})
                    },
                    'updated_at': datetime.now().isoformat()
                }
                
                # 写入数据库 (使用 upsert，如果已存在则更新)
                supabase.table('predictions').upsert(record, on_conflict='point_name').execute()
                success_count += 1
            except Exception as e:
                print(f"Error processing point {name}: {e}")
        
        return jsonify({
            'success': True, 
            'message': '全量预计算任务完成',
            'total_points': len(point_names),
            'success_count': success_count
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# === 预测结果存储与收藏 ===

@app.route('/api/save_prediction', methods=['POST'])
def save_prediction():
    """保存预测结果"""
    try:
        from config import supabase
        data = request.get_json()
        
        # 必需字段
        required = ['point_name', 'result_json']
        if not all(k in data for k in required):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
            
        record = {
            'point_name': data['point_name'],
            'predict_steps': data.get('predict_steps', 30),
            'result_json': data['result_json'], # 应该是字典/JSON对象
            'input_range': data.get('input_range', ''),
            'is_favorite': data.get('is_favorite', False),
            'model_version': data.get('model_version', 'v1'),
            'user_id': data.get('user_id', 'admin')
        }
        
        # 插入 Supabase
        res = supabase.table('prediction_results').insert(record).execute()
        
        return jsonify({'success': True, 'data': res.data})
    except Exception as e:
        print(f"Save prediction failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/prediction_history', methods=['GET'])
def get_prediction_history():
    """获取预测历史/收藏列表"""
    try:
        from config import supabase
        
        # 参数
        point_name = request.args.get('point_name')
        is_favorite = request.args.get('is_favorite')
        limit = int(request.args.get('limit', 20))
        
        query = supabase.table('prediction_results').select('*').order('created_at', desc=True).limit(limit)
        
        if point_name:
            query = query.eq('point_name', point_name)
            
        if is_favorite == 'true':
            query = query.eq('is_favorite', True)
            
        res = query.execute()
        
        return jsonify({'success': True, 'data': res.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/toggle_favorite', methods=['POST'])
def toggle_favorite():
    """切换收藏状态"""
    try:
        from config import supabase
        data = request.get_json()
        record_id = data.get('id')
        is_favorite = data.get('is_favorite')
        
        if not record_id or is_favorite is None:
            return jsonify({'success': False, 'error': 'id and is_favorite are required'}), 400
            
        res = supabase.table('prediction_results')\
            .update({'is_favorite': is_favorite})\
            .eq('id', record_id)\
            .execute()
            
        return jsonify({'success': True, 'data': res.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500




if __name__ == '__main__':
    print("=" * 60)
    print("  大坝监测数据深度学习预测 API 服务")
    print("=" * 60)
    print(f"数据目录: {DATA_DIR}")
    print(f"模型目录: {MODEL_DIR}")
    print("API 端点:")
    print("  GET  /api/health           - 健康检查")
    print("  GET  /api/data_summary     - 数据摘要")
    print("  GET  /api/points           - 测点列表")
    print("  POST /api/predict          - 单点预测")
    print("  POST /api/batch_predict    - 批量预测")
    print("  GET  /api/point_history    - 历史数据")
    print("  POST /api/train            - 训练模型")
    print("  GET  /api/anomaly_detection - 异常检测")
    print("  POST /api/ai_analyze       - AI智能分析")
    print("  GET  /api/ai_anomaly_report - AI异常报告")
    print("=" * 60)
    
    print(" * Running on http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
