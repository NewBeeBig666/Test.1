<script setup>
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/stores/auth'
import request from '@/api/request'

const auth = useAuthStore()

// ============================== 消息管理 ==============================
const MESSAGES_KEY = 'recsys_ai_chat_history' // localStorage 持久化 key

const messages = ref([])
const input = ref('')
const sending = ref(false)
const open = ref(false)

onMounted(() => {
  // 加载本地对话历史（刷新不丢失）
  try {
    const raw = localStorage.getItem(MESSAGES_KEY)
    if (raw) {
      messages.value = JSON.parse(raw)
        .filter(m => (m.role === 'user' || m.role === 'assistant') && m.content?.length < 500)
        .map(m => ({ role: m.role, content: String(m.content) }))
    }
  } catch { /* JSON 解析失败则忽略 */ }
})

// 持久化最近 20 条对话，避免影响系统整体性能
watch(messages, (v) => {
  localStorage.setItem(MESSAGES_KEY, JSON.stringify(v.slice(-20)))
}, { deep: true })

const scrollEl = ref(null)
watch(() => messages.value.length, async () => {
  await nextTick()
  if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
})
watch(open, async (v) => {
  if (v) {
    await nextTick()
    if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
  }
})

const QUICK_QUESTIONS = [
  '为我推荐一些图书、课程或电影',
  '推荐指数是怎么计算的？',
  '这个系统有哪些功能？',
]

async function send(text) {
  const q = (typeof text === 'string' ? text : input.value).trim()
  if (!q || sending.value) return

  // 无会话时自动创建游客会话（复用全局路由守卫逻辑）
  if (!auth.token) await auth.ensureSession()

  input.value = ''
  messages.value.push({ role: 'user', content: q })
  sending.value = true
  try {
    // 历史截取最近 20 条（服务端再截取 10 条），保证上下文窗口可控
    const history = messages.value.slice(0, -1).map(m => ({ role: m.role, content: m.content }))
    const res = await request.post('/ai/chat', {
      question: q,
      history,
    })
    messages.value.push({ role: 'assistant', content: String(res.answer || '') })
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: '抱歉，AI 助手暂时无法回答，请稍后再试。'
    })
  } finally {
    sending.value = false
  }
}

function clearMessages() {
  if (!confirm('确定清空当前对话记录吗？')) return
  messages.value = []
  localStorage.removeItem(MESSAGES_KEY)
}

// ============================== 图标交互 ==============================
// 圆形图标支持拖拽；移动 < 5px 视为点击（打开/关闭对话窗口）
let pressX = 0, pressY = 0, iconX = 0, iconY = 0, moved = false, pressed = false

const iconStyle = ref(null) // { left, top }；null 时回到默认右下角

function onPointerDown(e) {
  pressed = true
  moved = false
  pressX = e.clientX
  pressY = e.clientY
  const rect = e.currentTarget.getBoundingClientRect()
  iconX = rect.left
  iconY = rect.top
  e.currentTarget.setPointerCapture(e.pointerId)
}

function onPointerMove(e) {
  if (!pressed) return
  const dx = e.clientX - pressX
  const dy = e.clientY - pressY
  if (!moved && Math.hypot(dx, dy) < 5) return
  moved = true

  // 拖拽位置限制在视口内
  const vw = window.innerWidth
  const vh = window.innerHeight
  const size = 56
  const cx = Math.max(12, Math.min(iconX + dx, vw - size - 12))
  const cy = Math.max(12, Math.min(iconY + dy, vh - size - 12))
  iconStyle.value = { left: cx + 'px', top: cy + 'px' }
}

function onPointerUp() {
  pressed = false
  if (moved) return // 拖拽结束不触发点击
  open.value = !open.value
}

onBeforeUnmount(() => { pressed = false })
</script>

<template>
  <!-- ==================== 悬浮图标（可拖拽） ==================== -->
  <button class="ai-icon" :style="iconStyle"
          aria-label="AI 助手"
          title="AI 助手（可拖拽）"
          @pointerdown="onPointerDown"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @pointercancel="onPointerUp">
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="4" y="8" width="16" height="11" rx="3.5" stroke="white" stroke-width="1.8"/>
      <path d="M12 8V5" stroke="white" stroke-width="1.8" stroke-linecap="round"/>
      <circle cx="12" cy="4" r="1.4" fill="white"/>
      <circle cx="9" cy="13" r="1.3" fill="white"/>
      <circle cx="15" cy="13" r="1.3" fill="white"/>
      <path d="M9.5 16.5h5" stroke="white" stroke-width="1.5" stroke-linecap="round"/>
    </svg>
    <span v-if="!open" class="ai-pulse" aria-hidden="true"></span>
  </button>

  <!-- ==================== 对话窗口（弹出在界面右侧） ==================== -->
  <transition name="ai-pop">
    <div v-if="open" class="ai-panel" role="dialog" aria-label="AI 助手对话窗口">

      <!-- 标题栏 -->
      <div class="ai-head">
        <div class="ai-head-info">
          <strong>小智 · AI 助手</strong>
          <span class="ai-note">GLM-4-Flash 驱动</span>
        </div>
        <button class="ai-head-btn" title="清空对话" @click="clearMessages">清空</button>
        <button class="ai-head-btn" title="关闭对话" @click="open = false">✕</button>
      </div>

      <!-- 消息展示区 -->
      <div ref="scrollEl" class="ai-body">
        <div v-if="!messages.length" class="ai-empty">
          <p class="ai-note">你好，我是本系统的 AI 助手「小智」。<br>
            可以问我推荐系统相关问题，也可以试试快捷提问：</p>
          <button v-for="q in QUICK_QUESTIONS" :key="q" class="ai-quick"
                  :disabled="sending" @click="send(q)">{{ q }}</button>
        </div>

        <template v-for="(m, i) in messages" :key="i">
          <div v-if="m.role === 'user'" class="ai-msg ai-msg-user">{{ m.content }}</div>
          <div v-else class="ai-msg ai-msg-bot">{{ m.content }}</div>
        </template>

        <!-- 正在输入指示器 -->
        <div v-if="sending" class="ai-msg ai-msg-bot ai-typing">
          <span></span><span></span><span></span>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="ai-input-area">
        <textarea v-model="input" rows="1" maxlength="2000"
                  placeholder="输入你的问题，Enter 发送…"
                  @keydown.enter.exact.prevent="send()"></textarea>
        <button class="ai-send" :disabled="sending || !input.trim()" @click="send()">
          {{ sending ? '…' : '发送' }}
        </button>
      </div>

    </div>
  </transition>
</template>

<style scoped>
/* ==================== 悬浮图标 ==================== */
.ai-icon {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 1500;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #0d66ff 0%, #5f8bff 55%, #9db4ff 100%);
  box-shadow: 0 10px 28px rgba(13, 102, 255, 0.35);
  cursor: grab;
  transition: box-shadow 0.25s;
  touch-action: none;
  user-select: none;
}
.ai-icon:hover { box-shadow: 0 12px 34px rgba(13, 102, 255, 0.5); }
.ai-icon:active { cursor: grabbing; }

.ai-pulse {
  position: absolute;
  inset: -5px;
  border-radius: 50%;
  border: 2px solid rgba(13, 102, 255, 0.5);
  animation: ai-pulse 2.4s ease-out infinite;
  pointer-events: none;
}
@keyframes ai-pulse {
  0%   { transform: scale(0.95); opacity: 1; }
  70%  { transform: scale(1.35); opacity: 0; }
  100% { transform: scale(1.35); opacity: 0; }
}

/* ==================== 对话面板 ==================== */
.ai-panel {
  position: fixed;
  right: 24px;
  bottom: 92px;
  z-index: 1500;
  width: 380px;
  max-width: calc(100vw - 48px);
  height: min(520px, calc(100vh - 120px));
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 18px 60px rgba(0, 20, 60, 0.22);
  border: 1px solid rgba(0, 0, 0, 0.06);
  overflow: hidden;
}
@media (max-width: 560px) {
  .ai-panel { right: 12px; bottom: 88px; max-width: calc(100vw - 24px); }
}

/* 弹出动画 */
.ai-pop-enter-active { transition: opacity 0.22s, transform 0.22s; }
.ai-pop-leave-active { transition: opacity 0.15s, transform 0.15s; }
.ai-pop-enter-from,
.ai-pop-leave-to { opacity: 0; transform: translateY(12px) scale(0.97); }

/* ==================== 标题栏 ==================== */
.ai-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: linear-gradient(135deg, #0d66ff 0%, #5f8bff 60%, #9db4ff 100%);
  color: #fff;
  gap: 8px;
}
.ai-head-info { display: flex; flex-direction: column; gap: 1px; }
.ai-head-info strong { font-size: 14px; letter-spacing: 0.4px; }
.ai-head .ai-note { font-size: 10px; opacity: 0.85; }
.ai-panel > .ai-note { font-size: 12px; }

.ai-head-btn {
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 5px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}
.ai-head-btn:hover { background: rgba(255, 255, 255, 0.3); }

/* ==================== 消息展示区 ==================== */
.ai-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #f8fafd;
}
.ai-body::-webkit-scrollbar { width: 6px; }
.ai-body::-webkit-scrollbar-thumb { background: rgba(13, 102, 255, 0.25); border-radius: 3px; }

.ai-note { color: var(--text-3, #787f8c); font-size: 12px; }

.ai-empty { display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }
.ai-quick {
  text-align: left;
  background: #fff;
  border: 1px solid rgba(13, 102, 255, 0.25);
  color: #0d66ff;
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
}
.ai-quick:hover { background: rgba(13, 102, 255, 0.06); border-color: rgba(13, 102, 255, 0.45); }

.ai-msg {
  max-width: 86%;
  padding: 9px 13px;
  border-radius: 12px;
  font-size: 13.5px;
  line-height: 1.55;
  word-break: break-word;
  white-space: pre-wrap;
}
.ai-msg-user {
  align-self: flex-end;
  background: linear-gradient(135deg, #0d66ff, #4a86ff);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 3px 10px rgba(13, 102, 255, 0.22);
}
.ai-msg-bot {
  align-self: flex-start;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-bottom-left-radius: 4px;
}

/* 正在输入指示器（三点动画） */
.ai-typing { display: flex; gap: 5px; align-items: center; height: 36px; }
.ai-typing span {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: rgba(13, 102, 255, 0.55);
  animation: ai-dot 1.2s ease-in-out infinite;
}
.ai-typing span:nth-child(2) { animation-delay: 0.18s; }
.ai-typing span:nth-child(3) { animation-delay: 0.36s; }
@keyframes ai-dot {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.45; }
  30%           { transform: translateY(-4px); opacity: 1; }
}

/* ==================== 输入区 ==================== */
.ai-input-area {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
  background: #fff;
}
.ai-input-area textarea {
  flex: 1;
  resize: none;
  border: 1px solid rgba(0, 0, 0, 0.14);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13.5px;
  font-family: inherit;
  line-height: 1.4;
  max-height: 96px;
  outline: none;
  transition: border-color 0.2s;
}
.ai-input-area textarea:focus { border-color: rgba(13, 102, 255, 0.55); }

.ai-send {
  align-self: flex-end;
  border: none;
  border-radius: 10px;
  padding: 11px 16px;
  font-size: 13px;
  color: #fff;
  background: linear-gradient(135deg, #0d66ff, #4a86ff);
  cursor: pointer;
  transition: opacity 0.2s, box-shadow 0.2s;
}
.ai-send:hover:not(:disabled) { box-shadow: 0 4px 14px rgba(13, 102, 255, 0.3); }
.ai-send:disabled { opacity: 0.45; cursor: not-allowed; }
</style>
