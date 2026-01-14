<!--
  组件名: Login.vue
  功能: 用户登录/注册页面
  作者: 章涵硕
  特色: 水利科技风格背景 + 玻璃拟态登录框
-->
<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 表单状态
const isLogin = ref(true)
const loading = ref(false)

const form = reactive({
  email: '',
  password: '',
  confirmPassword: ''
})

// 表单验证规则
const rules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ]
}

/**
 * 处理登录/注册
 */
async function handleSubmit() {
  loading.value = true
  
  try {
    if (isLogin.value) {
      // 登录
      const result = await authStore.signInWithEmail(form.email, form.password)
      if (result.success) {
        ElMessage.success('登录成功！')
        const redirect = route.query.redirect as string || '/dashboard'
        router.push(redirect)
      } else {
        ElMessage.error(result.error || '登录失败')
      }
    } else {
      // 注册
      if (form.password !== form.confirmPassword) {
        ElMessage.error('两次输入的密码不一致')
        return
      }
      const result = await authStore.signUpWithEmail(form.email, form.password)
      if (result.success) {
        ElMessage.success('注册成功！请查收验证邮件')
        isLogin.value = true
      } else {
        ElMessage.error(result.error || '注册失败')
      }
    }
  } finally {
    loading.value = false
  }
}

/**
 * 切换登录/注册模式
 */
function toggleMode() {
  isLogin.value = !isLogin.value
  form.confirmPassword = ''
}
</script>

<template>
  <div class="login-container">
    <!-- 背景动画 -->
    <div class="bg-animation">
      <div class="wave wave1"></div>
      <div class="wave wave2"></div>
      <div class="wave wave3"></div>
    </div>
    
    <!-- 登录卡片 -->
    <div class="login-card glass-card animate-fade-in-up">
      <!-- Logo 和标题 -->
      <div class="login-header">
        <div class="logo">
          <el-icon :size="48" color="var(--accent)">
            <Monitor />
          </el-icon>
        </div>
        <h1 class="title">智慧水利监测平台</h1>
        <p class="subtitle">河海大学水利水电学院</p>
      </div>
      
      <!-- 登录表单 -->
      <el-form 
        :model="form" 
        :rules="rules" 
        class="login-form"
        @submit.prevent="handleSubmit"
      >
        <el-form-item prop="email">
          <el-input 
            v-model="form.email" 
            placeholder="邮箱地址"
            size="large"
            prefix-icon="Message"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input 
            v-model="form.password" 
            type="password" 
            placeholder="密码"
            size="large"
            prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        
        <el-form-item v-if="!isLogin" prop="confirmPassword">
          <el-input 
            v-model="form.confirmPassword" 
            type="password" 
            placeholder="确认密码"
            size="large"
            prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            size="large" 
            :loading="loading"
            class="submit-btn"
            native-type="submit"
          >
            {{ isLogin ? '登 录' : '注 册' }}
          </el-button>
        </el-form-item>
      </el-form>
      
      <!-- 切换登录/注册 -->
      <div class="login-footer">
        <span class="text">{{ isLogin ? '还没有账号？' : '已有账号？' }}</span>
        <el-button type="primary" link @click="toggleMode">
          {{ isLogin ? '立即注册' : '去登录' }}
        </el-button>
      </div>
      
      <!-- 技术标签 -->
      <div class="tech-tags">
        <span class="tag">Vue 3</span>
        <span class="tag">Supabase</span>
        <span class="tag">Cesium</span>
        <span class="tag">ECharts</span>
      </div>
    </div>
    
    <!-- 版权信息 -->
    <div class="copyright">
      © 2026 章涵硕 | 智慧水利专业 | 河海大学
    </div>
  </div>
</template>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, var(--primary-dark) 0%, #0d2137 100%);
}

/* 波浪背景动画 */
.bg-animation {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  z-index: 0;
}

.wave {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 200%;
  height: 300px;
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1440 320'%3E%3Cpath fill='%2300d4ff' fill-opacity='0.1' d='M0,160L48,170.7C96,181,192,203,288,186.7C384,171,480,117,576,112C672,107,768,149,864,165.3C960,181,1056,171,1152,149.3C1248,128,1344,96,1392,80L1440,64L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z'%3E%3C/path%3E%3C/svg%3E") repeat-x;
  animation: wave 15s linear infinite;
}

.wave1 { opacity: 0.5; animation-delay: 0s; }
.wave2 { opacity: 0.3; animation-delay: -5s; bottom: 20px; }
.wave3 { opacity: 0.2; animation-delay: -10s; bottom: 40px; }

@keyframes wave {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

/* 登录卡片 */
.login-card {
  width: 420px;
  padding: 40px;
  z-index: 1;
  background: rgba(17, 34, 64, 0.8);
  border: 1px solid rgba(0, 212, 255, 0.2);
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.logo {
  margin-bottom: 16px;
}

.title {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  background: linear-gradient(135deg, #fff 0%, var(--accent) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  font-size: 14px;
  color: var(--text-secondary);
}

/* 表单 */
.login-form {
  margin-top: 20px;
}

.submit-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
}

/* 底部 */
.login-footer {
  text-align: center;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

.login-footer .text {
  color: var(--text-secondary);
  font-size: 14px;
}

/* 技术标签 */
.tech-tags {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 24px;
  flex-wrap: wrap;
}

.tech-tags .tag {
  padding: 4px 12px;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 20px;
  font-size: 12px;
  color: var(--accent);
}

/* 版权 */
.copyright {
  position: absolute;
  bottom: 20px;
  color: var(--text-muted);
  font-size: 12px;
  z-index: 1;
}
</style>
