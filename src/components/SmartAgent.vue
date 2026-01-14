<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Picture, Close, ChatDotRound, Delete, Promotion } from '@element-plus/icons-vue'

// 状态定义
const router = useRouter()
const visible = ref(false)
const input = ref('')
const loading = ref(false)
const chatBodyRef = ref<HTMLElement | null>(null)
const uploadInputRef = ref<HTMLInputElement | null>(null)

// 悬浮球拖拽逻辑
const floatBtnRef = ref<HTMLElement | null>(null)
const position = ref({ right: 30, bottom: 30 })
let isDragging = false
let startX = 0
let startY = 0
let startRight = 0
let startBottom = 0

// 防止点击和拖拽冲突
let isMoved = false

const handleMouseDown = (e: MouseEvent) => {
  if (!floatBtnRef.value) return
  isDragging = true
  isMoved = false
  startX = e.clientX
  startY = e.clientY
  
  // 获取当前的 right/bottom 值
  const rect = floatBtnRef.value.getBoundingClientRect()
  startRight = window.innerWidth - rect.right
  startBottom = window.innerHeight - rect.bottom
  
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
}

const handleMouseMove = (e: MouseEvent) => {
  if (!isDragging) return
  const dx = e.clientX - startX
  const dy = e.clientY - startY
  
  if (Math.abs(dx) > 2 || Math.abs(dy) > 2) isMoved = true
  
  // 更新位置 (反向计算，因为是 right/bottom)
  position.value = {
    right: Math.max(0, Math.min(window.innerWidth - 80, startRight - dx)),
    bottom: Math.max(0, Math.min(window.innerHeight - 80, startBottom - dy))
  }
}

const handleMouseUp = () => {
  isDragging = false
  document.removeEventListener('mousemove', handleMouseMove)
  document.removeEventListener('mouseup', handleMouseUp)
}

const toggleChat = () => {
  if (!isMoved) {
    visible.value = !visible.value
  }
}

// 图片相关
const selectedImage = ref<string | null>(null) // Base64 string

// 聊天记录结构
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  image?: string // 用户上传的图片
  time: string
}

const messages = ref<ChatMessage[]>([
  {
    role: 'assistant',
    content: '你好！我是 HydroMind Pro (水利智脑)。\n我可以为您分析监测数据、诊断异常，甚至通过您上传的截图进行视觉分析。\n请问有什么可以帮您？',
    time: new Date().toLocaleTimeString()
  }
])

// 自动滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (chatBodyRef.value) {
    chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
  }
}

watch(messages, scrollToBottom, { deep: true })
watch(visible, (val) => {
  if (val) scrollToBottom()
})

// 处理图片选择
const handleImageSelect = (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return

  if (file.size > 2 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 2MB')
    return
  }

  const reader = new FileReader()
  reader.onload = (e) => {
    selectedImage.value = e.target?.result as string
  }
  reader.readAsDataURL(file)
  
  // 清空 input 允许重复选择同一文件
  if (uploadInputRef.value) uploadInputRef.value.value = ''
}

const removeImage = () => {
  selectedImage.value = null
}

// 处理粘贴事件
const handlePaste = (event: ClipboardEvent) => {
  const items = event.clipboardData?.items
  if (!items) return

  for (const item of items) {
    if (item.type.indexOf('image') !== -1) {
      const file = item.getAsFile()
      if (!file) continue
      
      // 复用大小检查逻辑
      if (file.size > 2 * 1024 * 1024) {
        ElMessage.warning('粘贴的图片大小不能超过 2MB')
        return
      }

      const reader = new FileReader()
      reader.onload = (e) => {
        selectedImage.value = e.target?.result as string
        ElMessage.success('已识别剪贴板图片')
      }
      reader.readAsDataURL(file)
      
      // 阻止默认粘贴行为（避免文件名出现在输入框）
      event.preventDefault()
      return
    }
  }
}


// 发送消息
const sendMessage = async () => {
  const text = input.value.trim()
  if (!text && !selectedImage.value) return
  if (loading.value) return

  // 1. 添加用户消息
  const userMsg: ChatMessage = {
    role: 'user',
    content: text,
    image: selectedImage.value || undefined,
    time: new Date().toLocaleTimeString()
  }
  messages.value.push(userMsg)

  // 暂存并清空输入
  const queryText = text
  const queryImage = selectedImage.value
  input.value = ''
  selectedImage.value = null
  loading.value = true

  try {
    // 2. 调用后端 API (通过Vite代理自动转发到localhost:5001)
    const response = await fetch('/api/ask_agent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: queryText,
        image: queryImage // Base64
      })
    })

    // 检查响应状态
    if (!response.ok) {
      throw new Error(`HTTP Error: ${response.status}`)
    }

    const data = await response.json()
    
    if (data.success) {
      let content = data.data
      
      // 解析控制指令 [CMD: NAVIGATE -> /path]
      const cmdMatch = content.match(/\[CMD: NAVIGATE -> (.*?)\]/)
      if (cmdMatch) {
        const path = cmdMatch[1].trim()
        // 移除指令文本，保持界面整洁
        content = content.replace(cmdMatch[0], '').trim()
        
        ElMessage.success({
          message: `智能体正在导航至: ${path}`,
          type: 'success',
          duration: 2000
        })
        
        // 执行路由跳转
        router.push(path)
      }

      messages.value.push({
        role: 'assistant',
        content: content,
        time: new Date().toLocaleTimeString()
      })
    } else {
      throw new Error(data.error || '请求失败')
    }
  } catch (e: any) {
    console.error('AI Chat Error:', e)
    messages.value.push({
      role: 'assistant',
      content: `⚠️ 连接大脑失败: ${e.message}\n请确认后端服务(port 5001)已启动。`,
      time: new Date().toLocaleTimeString()
    })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="smart-agent">
    <!-- 悬浮球 (可拖拽) -->
    <div 
      ref="floatBtnRef"
      class="float-btn" 
      :class="{ active: visible, dragging: isDragging }"
      :style="{ right: position.right + 'px', bottom: position.bottom + 'px' }"
      @mousedown="handleMouseDown"
      @click="toggleChat"
    >
      <div class="pulse-ring"></div>
      <div class="btn-content">
        <el-icon :size="32"><ChatDotRound /></el-icon>
        <span class="btn-label">水利智脑</span>
      </div>
    </div>

    <!-- 聊天窗口 -->
    <transition name="pop">
      <div v-show="visible" class="chat-window glass-panel">
        <!-- 头部 -->
        <div class="header">
          <div class="title-area">
            <div class="avatar-ring">
              <span class="ai-icon">🧠</span>
            </div>
            <div class="title-text">
              <h3>HydroMind Pro</h3>
              <span class="status">● 在线 (72B模型)</span>
            </div>
          </div>
          <el-button link class="close-btn" @click="visible = false">
            <el-icon :size="20"><Close /></el-icon>
          </el-button>
        </div>

        <!-- 消息区 -->
        <div class="body" ref="chatBodyRef">
          <div v-for="(msg, index) in messages" :key="index" :class="['message-row', msg.role]">
            <!-- 头像 -->
            <div class="avatar" v-if="msg.role === 'assistant'">🤖</div>
            
            <!-- 内容气泡 -->
            <div class="bubble-wrapper">
              <div class="bubble">
                <!-- 图片显示 -->
                <div v-if="msg.image" class="msg-image">
                  <el-image 
                    :src="msg.image" 
                    :preview-src-list="[msg.image]" 
                    fit="cover"
                    class="preview-img"
                  />
                </div>
                <!-- 文本显示 -->
                <div class="msg-text" style="white-space: pre-wrap;">{{ msg.content }}</div>
              </div>
              <div class="time">{{ msg.time }}</div>
            </div>

            <!-- 用户头像 -->
            <div class="avatar user" v-if="msg.role === 'user'">User</div>
          </div>

          <!-- 加载动画 -->
          <div v-if="loading" class="message-row assistant">
            <div class="avatar">🤖</div>
            <div class="bubble loading">
              <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="footer">
          <!-- 图片预览 -->
          <div v-if="selectedImage" class="img-preview-bar">
            <div class="img-item">
              <img :src="selectedImage" />
              <div class="remove-btn" @click="removeImage">
                <el-icon><Delete /></el-icon>
              </div>
            </div>
          </div>

          <div class="input-bar">
            <!-- 图片上传按钮 -->
            <div class="tool-btn" @click="uploadInputRef?.click()">
              <el-icon :size="20" color="#00d4ff"><Picture /></el-icon>
            </div>
            <input 
              type="file" 
              ref="uploadInputRef" 
              accept="image/*" 
              style="display: none" 
              @change="handleImageSelect"
            />

            <!-- 文本输入 -->
            <input 
              v-model="input" 
              class="text-input"
              placeholder="输入问题，或粘贴/上传图片..." 
              @keyup.enter="sendMessage"
              @paste="handlePaste"
            />
            
            <!-- 发送按钮 -->
            <button class="send-btn" @click="sendMessage" :disabled="loading || (!input && !selectedImage)">
              <el-icon><Promotion /></el-icon>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
/* 悬浮球 - 增强版 */
.float-btn {
  position: fixed;
  /* 移除固定的 bottom/right，改用 style 绑定 */
  width: 80px;  /* 增大尺寸 */
  height: 80px; /* 增大尺寸 */
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: grab;
  z-index: 10000; /* 提升层级 */
  user-select: none;
  background: rgba(15, 23, 42, 0.6); /* 玻璃态背景 */
  backdrop-filter: blur(10px);
  box-shadow: 0 0 0 1px rgba(0, 212, 255, 0.3), 0 8px 30px rgba(0, 0, 0, 0.5);
  transition: transform 0.2s;
}

.float-btn:active {
  cursor: grabbing;
}

/* 内部内容 */
.btn-content {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.8), rgba(37, 99, 235, 0.9));
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: white;
  position: relative;
  z-index: 2;
  box-shadow: inset 0 2px 10px rgba(255, 255, 255, 0.3);
}

.btn-label {
  font-size: 11px;
  margin-top: 4px;
  font-weight: 600;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}

/* 脉冲动画环 */
.pulse-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid #00d4ff;
  opacity: 0;
  z-index: 1;
  animation: pulse-glow 2s infinite cubic-bezier(0.4, 0, 0.6, 1);
}

/* 添加第二个脉冲环，增加层次感 */
.float-btn::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: rgba(0, 212, 255, 0.3);
  z-index: 0;
  animation: pulse-dot 2s infinite cubic-bezier(0.4, 0, 0.6, 1);
}

@keyframes pulse-glow {
  0% { transform: translate(-50%, -50%) scale(1); opacity: 0.8; }
  100% { transform: translate(-50%, -50%) scale(1.6); opacity: 0; }
}

@keyframes pulse-dot {
  0% { transform: translate(-50%, -50%) scale(0.9); opacity: 0.5; }
  50% { transform: translate(-50%, -50%) scale(1.1); opacity: 0.2; }
  100% { transform: translate(-50%, -50%) scale(0.9); opacity: 0.5; }
}


.float-btn:hover {
  transform: scale(1.05);
}

.float-btn.active {
  transform: scale(0.95);
}

.float-btn.active .btn-content {
  background: linear-gradient(135deg, #0f172a, #1e293b);
  border: 2px solid #00d4ff;
}


/* 聊天窗口位置 */
.chat-window {
  position: fixed;
  bottom: 120px;
  right: 30px;
  width: 420px;
  height: 650px;
  max-height: 80vh;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(0, 212, 255, 0.3);
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 9998;
  box-shadow: 0 10px 50px rgba(0, 0, 0, 0.8);
}

.header {
  padding: 16px;
  background: rgba(0, 212, 255, 0.1);
  border-bottom: 1px solid rgba(0, 212, 255, 0.2);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar-ring {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0ea5e9, #2563eb);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.title-text h3 {
  margin: 0;
  font-size: 16px;
  color: #fff;
  font-weight: 600;
}

.status {
  font-size: 11px;
  color: #10b981;
}

.close-btn {
  color: #94a3b8;
}

.close-btn:hover {
  color: #fff;
}

/* 消息区 */
.body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message-row {
  display: flex;
  gap: 12px;
  max-width: 100%;
}

.message-row.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #1e293b;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.avatar.user {
  background: #2563eb;
  color: #fff;
  font-size: 10px;
}

.bubble-wrapper {
  max-width: 80%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bubble {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  color: #e2e8f0;
  word-break: break-word;
}

.assistant .bubble {
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-top-left-radius: 2px;
}

.user .bubble {
  background: linear-gradient(135deg, #2563eb, #0284c7);
  color: white;
  border-top-right-radius: 2px;
}

.msg-image {
  margin-bottom: 8px;
  border-radius: 8px;
  overflow: hidden;
  max-width: 200px;
}

.preview-img {
  width: 100%;
  height: auto;
  display: block;
}

.time {
  font-size: 10px;
  color: #64748b;
  align-self: flex-start;
}

.user .time {
  align-self: flex-end;
}

/* 加载动画 */
.loading .dot {
  animation: bounce 1.4s infinite ease-in-out both;
  font-size: 20px;
  line-height: 10px;
}

.loading .dot:nth-child(1) { animation-delay: -0.32s; }
.loading .dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 底部输入区 */
.footer {
  padding: 16px;
  background: rgba(15, 23, 42, 0.8);
  border-top: 1px solid rgba(0, 212, 255, 0.1);
}

.img-preview-bar {
  margin-bottom: 10px;
  display: flex;
  gap: 10px;
}

.img-item {
  width: 60px;
  height: 60px;
  border-radius: 8px;
  position: relative;
  border: 1px solid #00d4ff;
  overflow: hidden;
}

.img-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.remove-btn {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 16px;
  height: 16px;
  background: rgba(0,0,0,0.6);
  border-radius: 50%;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 10px;
}

.input-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(30, 41, 59, 0.5);
  padding: 8px 12px;
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.tool-btn {
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 4px;
  border-radius: 50%;
  transition: bg 0.2s;
}

.tool-btn:hover {
  background: rgba(255,255,255,0.1);
}

.text-input {
  flex: 1;
  background: transparent;
  border: none;
  color: #fff;
  outline: none;
  font-size: 14px;
}

.send-btn {
  background: #00d4ff;
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #0f172a;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover {
  transform: scale(1.1);
  box-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
}

.send-btn:disabled {
  background: #334155;
  color: #64748b;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* 动画 */
.pop-enter-active, .pop-leave-active {
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.pop-enter-from, .pop-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}
</style>
