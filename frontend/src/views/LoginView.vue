<script setup>
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = reactive({ username: '', password: '' })
const guestId = ref('')
const loading = ref(false)

const login = async () => {
  if (!form.username || !form.password) return
  loading.value = true
  try {
    const data = await request.post('/auth/login', form)
    auth.set(data.token, data.user)
    router.push(route.query.redirect || '/')
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '登录失败')
  } finally {
    loading.value = false
  }
}

const guest = async () => {
  const id = Number(guestId.value)
  if (!id || id <= 0) return
  loading.value = true
  try {
    const data = await request.post('/auth/guest', { userId: id })
    auth.set(data.token, data.user)
    router.push('/')
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '体验用户ID无效')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="login-card card reveal in" style="padding: 44px 40px; max-width: 430px; width: 100%">
      <h1 class="hero-title" style="font-size: 38px; margin-bottom: 6px">智荐。</h1>
      <p class="hero-sub" style="font-size: 19px; margin-bottom: 30px">图书 · 课程 · 电影，一个账户。</p>

      <form @submit.prevent="login" style="display: flex; flex-direction: column; gap: 14px">
        <el-input v-model="form.username" placeholder="用户名" size="large" autocomplete="username" />
        <el-input v-model="form.password" type="password" placeholder="密码" size="large"
                  show-password autocomplete="current-password" />
        <button class="btn btn-lg" type="submit" :disabled="loading" style="width: 100%; margin-top: 6px">
          {{ loading ? '登录中…' : '登录' }}
        </button>
      </form>
      <p class="note" style="margin-top: 16px; text-align: center">
        还没有账户？<router-link to="/register">立即注册</router-link>
      </p>

      <el-divider style="margin: 22px 0">或</el-divider>

      <div class="note" style="margin-bottom: 10px">
        体验用户：直接使用数据集真实用户ID探索个性化推荐
        <span style="white-space: nowrap">（图书 1~278858 · 电影 1~610 · 课程 10000~12499）</span>
      </div>
      <div style="display: flex; gap: 10px">
        <el-input v-model="guestId" placeholder="如 114" size="large" style="flex: 1" />
        <button class="btn btn-ghost" :disabled="loading" @click="guest">进入体验</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: calc(100vh - var(--nav-h));
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(1200px 600px at 50% -10%, #eef3fb 0%, var(--bg-alt) 60%);
  padding: 40px 22px;
}
</style>
