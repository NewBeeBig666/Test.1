import { defineStore } from 'pinia'
import axios from 'axios'

/** 认证状态：token + 用户信息持久化 localStorage；支持匿名游客自动会话 */
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('rec_token') || '',
    user: JSON.parse(localStorage.getItem('rec_user') || 'null'),
  }),
  getters: {
    isLogin: (s) => !!s.token,
    /** kind: user=注册 / guest=数据集体验用户 / anon=匿名游客 */
    kind: (s) => s.user?.kind || (s.user ? (s.user.guest ? 'guest' : 'user') : null),
    isRegistered: (s) => s.user?.kind === 'user',
    displayName: (s) => s.user?.username || '游客',
  },
  actions: {
    set(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem('rec_token', token)
      localStorage.setItem('rec_user', JSON.stringify(user))
    },
    clear() {
      this.token = ''
      this.user = null
      localStorage.removeItem('rec_token')
      localStorage.removeItem('rec_user')
    },
    /** 无会话时自动创建匿名游客会话（免登录直达系统）；返回是否成功 */
    async ensureSession() {
      if (this.token) return true
      try {
        const { data } = await axios.post('/api/auth/guest-auto')
        this.set(data.token, data.user)
        return true
      } catch (e) {
        return false
      }
    },
  },
})
