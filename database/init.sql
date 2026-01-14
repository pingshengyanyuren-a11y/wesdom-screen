-- ============================================================
-- 智慧水利监测平台 - Supabase 数据库初始化脚本
-- 作者: 章涵硕
-- 学院: 河海大学水利水电学院
-- ============================================================

-- 1. 创建监测类型枚举
CREATE TYPE monitoring_type AS ENUM ('tension_wire', 'hydrostatic_level', 'plumb_line');

-- 2. 创建测点状态枚举
CREATE TYPE point_status AS ENUM ('normal', 'warning', 'danger');

-- ============================================================
-- 3. 创建测点表 (monitoring_points)
-- ============================================================
CREATE TABLE monitoring_points (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE,          -- 仪器编号 (如 EX1-2, TC1-1)
  type monitoring_type NOT NULL,              -- 监测类型
  location VARCHAR(100),                       -- 平面位置
  elevation DECIMAL(10, 2),                    -- 高程 (m)
  section VARCHAR(50),                         -- 坝段
  install_date DATE,                           -- 埋设时间
  longitude DECIMAL(10, 6),                    -- 经度
  latitude DECIMAL(10, 6),                     -- 纬度
  model_element_id VARCHAR(100),               -- 3D模型构件ID
  status point_status DEFAULT 'normal',        -- 运行状态
  warning_threshold DECIMAL(10, 4),            -- 警告阈值
  danger_threshold DECIMAL(10, 4),             -- 危险阈值
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_points_type ON monitoring_points(type);
CREATE INDEX idx_points_status ON monitoring_points(status);
CREATE INDEX idx_points_section ON monitoring_points(section);

-- ============================================================
-- 4. 创建测值表 (monitoring_values)
-- ============================================================
CREATE TABLE monitoring_values (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  point_id UUID NOT NULL REFERENCES monitoring_points(id) ON DELETE CASCADE,
  value DECIMAL(10, 4) NOT NULL,               -- 测量值
  unit VARCHAR(20) DEFAULT 'mm',               -- 单位
  water_level DECIMAL(10, 2),                  -- 库水位
  measured_at TIMESTAMPTZ NOT NULL,            -- 测量时间
  is_anomaly BOOLEAN DEFAULT FALSE,            -- 是否异常
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_values_point ON monitoring_values(point_id);
CREATE INDEX idx_values_measured_at ON monitoring_values(measured_at DESC);
CREATE INDEX idx_values_anomaly ON monitoring_values(is_anomaly) WHERE is_anomaly = TRUE;

-- ============================================================
-- 5. 创建用户配置表 (user_profiles)
-- ============================================================
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  name VARCHAR(100),
  phone VARCHAR(20),
  role VARCHAR(20) DEFAULT 'viewer',           -- admin/engineer/viewer
  department VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 6. 创建告警记录表 (alarm_records)
-- ============================================================
CREATE TABLE alarm_records (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  point_id UUID NOT NULL REFERENCES monitoring_points(id) ON DELETE CASCADE,
  value_id UUID REFERENCES monitoring_values(id),
  alarm_type VARCHAR(20) NOT NULL,             -- warning/danger
  message TEXT,
  is_acknowledged BOOLEAN DEFAULT FALSE,       -- 是否已确认
  acknowledged_at TIMESTAMPTZ,
  acknowledged_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alarms_point ON alarm_records(point_id);
CREATE INDEX idx_alarms_unack ON alarm_records(is_acknowledged) WHERE is_acknowledged = FALSE;

-- ============================================================
-- 7. 启用行级安全 (RLS)
-- ============================================================
ALTER TABLE monitoring_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring_values ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE alarm_records ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 8. 创建公开读取策略 (课设演示用，生产环境需更严格)
-- ============================================================
-- 测点表 - 允许所有认证用户读取，仅管理员可写
CREATE POLICY "允许认证用户读取测点" ON monitoring_points 
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "允许认证用户插入测点" ON monitoring_points 
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "允许认证用户更新测点" ON monitoring_points 
  FOR UPDATE USING (auth.role() = 'authenticated');

-- 测值表 - 允许所有认证用户读写
CREATE POLICY "允许认证用户读取测值" ON monitoring_values 
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "允许认证用户插入测值" ON monitoring_values 
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- 用户配置 - 用户只能访问自己的配置
CREATE POLICY "用户可读取自己的配置" ON user_profiles 
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "用户可更新自己的配置" ON user_profiles 
  FOR UPDATE USING (auth.uid() = id);

-- 告警记录 - 允许认证用户读取和更新
CREATE POLICY "允许认证用户读取告警" ON alarm_records 
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "允许认证用户确认告警" ON alarm_records 
  FOR UPDATE USING (auth.role() = 'authenticated');

-- ============================================================
-- 9. 创建触发器：自动更新 updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_points_updated_at
  BEFORE UPDATE ON monitoring_points
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_profiles_updated_at
  BEFORE UPDATE ON user_profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- 10. 创建视图：带最新测值的测点列表
-- ============================================================
CREATE OR REPLACE VIEW monitoring_points_with_latest AS
SELECT 
  p.*,
  v.value AS latest_value,
  v.measured_at AS latest_measured_at,
  CASE p.type
    WHEN 'tension_wire' THEN '引张线'
    WHEN 'hydrostatic_level' THEN '静力水准'
    WHEN 'plumb_line' THEN '倒垂线'
  END AS type_name
FROM monitoring_points p
LEFT JOIN LATERAL (
  SELECT value, measured_at 
  FROM monitoring_values 
  WHERE point_id = p.id 
  ORDER BY measured_at DESC 
  LIMIT 1
) v ON TRUE;

-- ============================================================
-- 完成！
-- ============================================================
