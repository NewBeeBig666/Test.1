import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

/** 统一 API 客户端：自动注入 Bearer Token；401 自动跳登录 */
const request = axios.create({ baseURL: '/api', timeout: 20000 })

request.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) config.headers.Authorization = `Bearer ${auth.token}`
  return config
})

request.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    if (err.response?.status === 401) {
      // 会话过期：清除本地会话回首页，路由守卫将自动重建匿名游客会话
      const auth = useAuthStore()
      auth.clear()
      const current = router.currentRoute.value
      if (current.name !== 'login' && current.name !== 'register') {
        router.push({ name: 'home' })
      }
    }
    return Promise.reject(err)
  },
)

export default request
