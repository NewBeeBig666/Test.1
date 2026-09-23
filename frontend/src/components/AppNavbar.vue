<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import request from '@/api/request'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

// 响应式：登录身份变化（如 admin 登录）后导航即时更新
// （画像 / 实验室 已移入右上角「更多」下拉，见 nav-right）
const links = computed(() => [
  { to: '/', label: '首页' },
  { to: '/books', label: '图书' },
  { to: '/courses', label: '课程' },
  { to: '/movies', label: '电影' },
  ...(auth.user?.username === 'admin' ? [{ to: '/admin', label: '管理' }] : []),
])

/** 「更多」下拉弹窗（画像 / 实验室） */
const moreOpen = ref(false)
const moreRoot = ref(null)
const MORE_ITEMS = [
  { to: '/profile', label: '画像', ico: '◎', desc: '跨域兴趣画像与行为分析' },
  { to: '/lab', label: '实验室', ico: '⚗', desc: '推荐算法对比实验' },
]
// 当前处于画像/实验室页时「更多」按钮呈激活态
const moreActive = computed(() => MORE_ITEMS.some((m) => route.path.startsWith(m.to)))

const toggleMore = () => { moreOpen.value = !moreOpen.value }
const closeMore = () => { moreOpen.value = false }

// 点击弹窗外部 / Escape 关闭
const onDocClick = (e) => {
  if (moreRoot.value && !moreRoot.value.contains(e.target)) closeMore()
}
const onKeydown = (e) => {
  if (e.key === 'Escape') closeMore()
}
onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKeydown)
})

const logout = async () => {
  try {
    await request.post('/auth/logout')
  } catch (e) { /* token 失效也可退出 */ }
  auth.clear()
  // 退出后回到匿名游客态并刷新页面状态
  await auth.ensureSession()
  router.push('/')
  window.location.reload()
}
</script>

<template>
  <header class="nav">
    <div class="nav-inner">
      <router-link to="/" class="nav-brand">
        <span style="font-size: 22px">◈</span>智荐
        <span class="brand-sub text-3" style="font-size: 12px; font-weight: 500">RecOS</span>
      </router-link>
      <nav class="nav-links">
        <router-link v-for="l in links" :key="l.to" :to="l.to" class="nav-link">
          {{ l.label }}
        </router-link>
      </nav>
      <div class="nav-right">
        <!-- 注册用户：用户名 + 退出 -->
        <template v-if="auth.kind === 'user'">
          <span class="chip chip-c">{{ auth.user.username }}</span>
          <a href="#" @click.prevent="logout()" class="nav-link">退出</a>
        </template>
        <!-- 数据集体验用户：徽章 + 登录 + 退出 -->
        <template v-else-if="auth.kind === 'guest'">
          <span class="chip">{{ auth.user.username }}</span>
          <router-link to="/login" class="btn" style="padding: 5px 16px; font-size: 13px">登录</router-link>
          <a href="#" @click.prevent="logout()" class="nav-link">退出</a>
        </template>
        <!-- 匿名游客：显著登录按钮 -->
        <template v-else>
          <router-link to="/login" class="btn" style="padding: 5px 16px; font-size: 13px">登录</router-link>
        </template>
        <!-- 更多（登录按钮右侧）：画像 / 实验室 二级功能入口（气泡下拉，不直接跳转） -->
        <div ref="moreRoot" class="nav-more">
          <button class="nav-link more-btn" :class="{ active: moreActive }"
                  type="button" @click.stop="toggleMore">
            更多 <span class="caret" :class="{ open: moreOpen }">▾</span>
          </button>
          <transition name="pop">
            <div v-if="moreOpen" class="more-pop" @click.stop>
              <router-link v-for="m in MORE_ITEMS" :key="m.to" :to="m.to"
                           class="more-item" :class="{ active: route.path.startsWith(m.to) }"
                           @click="closeMore">
                <span class="more-ico">{{ m.ico }}</span>
                <span class="more-txt">
                  <span class="more-label">{{ m.label }}</span>
                  <span class="more-desc">{{ m.desc }}</span>
                </span>
              </router-link>
            </div>
          </transition>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
/* ---------- 更多按钮与气泡弹窗 ---------- */
.nav-more { position: relative; display: inline-flex; }
.more-btn {
  background: none;
  border: none;
  cursor: pointer;
  font: inherit;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
/* 激活态（当前位于画像/实验室页）与主导航链接样式一致 */
.more-btn.active { color: var(--text); font-weight: 600; }
.more-btn:hover { color: var(--text); }
.more-btn .caret { font-size: 10px; transition: transform .2s ease; }
.more-btn .caret.open { transform: rotate(180deg); }

/* 气泡弹窗：右缘对齐触发按钮（向左展开，任何视口宽度均不超出右边界），
   白底 + 阴影 + 细边框区分层级，风格与平台卡片一致 */
.more-pop {
  position: absolute;
  top: calc(100% + 12px);
  right: 0;
  min-width: 216px;
  max-width: calc(100vw - 28px);
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--card-shadow-hover);
  padding: 6px;
  z-index: 90;
}
/* 气泡小箭头（指向更多按钮） */
.more-pop::before {
  content: '';
  position: absolute;
  top: -5px;
  right: 22px;
  width: 10px;
  height: 10px;
  background: #fff;
  border-left: 1px solid var(--border);
  border-top: 1px solid var(--border);
  transform: rotate(45deg);
  border-top-left-radius: 3px;
}
.more-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  color: var(--text);
  text-decoration: none;
  transition: background .15s ease;
}
.more-item:hover { background: var(--bg-alt); }
.more-item.active { background: rgba(0, 113, 227, 0.08); }
.more-ico {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: linear-gradient(150deg, rgba(0, 113, 227, 0.14), rgba(88, 86, 214, 0.14));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: var(--accent);
  flex: 0 0 auto;
}
.more-txt { display: flex; flex-direction: column; min-width: 0; }
.more-label { font-weight: 600; font-size: 14px; }
.more-desc { font-size: 12px; color: var(--text-3); margin-top: 1px; }

/* 气泡弹出场动画（与平台渐入风格一致） */
.pop-enter-active, .pop-leave-active { transition: opacity .16s ease, transform .16s ease; }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateY(-6px) scale(.97); }

@media (max-width: 560px) {
  .more-btn { padding: 5px 8px; font-size: 12px; }
  .more-pop { right: 0; min-width: 172px; }
  .more-pop::before { right: 16px; }
  .more-desc { display: none; }
}
</style>
