import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { public: true } },
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
  { path: '/books', name: 'books', component: () => import('@/views/DomainView.vue'), props: { domain: 'books' } },
  { path: '/courses', name: 'courses', component: () => import('@/views/DomainView.vue'), props: { domain: 'courses' } },
  { path: '/movies', name: 'movies', component: () => import('@/views/DomainView.vue'), props: { domain: 'movies' } },
  { path: '/profile', name: 'profile', component: () => import('@/views/ProfileView.vue') },
  { path: '/lab', name: 'lab', component: () => import('@/views/LabView.vue') },
  { path: '/away', name: 'away', component: () => import('@/views/AwayView.vue') },
  { path: '/admin', name: 'admin', component: () => import('@/views/AdminView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes, scrollBehavior: () => ({ top: 0 }) })

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  // 游客模式默认登录：无会话时自动创建匿名游客会话，无需认证即可访问全部页面
  if (!to.meta.public && !auth.isLogin) {
    const ok = await auth.ensureSession()
    if (!ok) return { name: 'login' }
  }
  // 已注册登录的用户访问登录/注册页时直接回首页（游客/匿名仍可进入登录页）
  if ((to.name === 'login' || to.name === 'register') && auth.isRegistered) {
    return { name: 'home' }
  }
  // 管理后台仅 admin 账号可见
  if (to.name === 'admin' && auth.user?.username !== 'admin') {
    return { name: 'home' }
  }
})

export default router
