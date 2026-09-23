<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const form = reactive({ username: '', password: '', confirm: '' })
const loading = ref(false)

const register = async () => {
  if (!form.username || !form.password) return
  if (form.password.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  if (form.password !== form.confirm) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  loading.value = true
  try {
    const data = await request.post('/auth/register', { username: form.username, password: form.password })
    auth.set(data.token, data.user)
    ElMessage.success('注册成功，欢迎体验个性化推荐')
    router.push('/')
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="card reveal in" style="padding: 44px 40px; max-width: 430px; width: 100%">
      <h1 class="hero-title" style="font-size: 38px; margin-bottom: 6px">创建账户。</h1>
      <p class="hero-sub" style="font-size: 19px; margin-bottom: 30px">你的跨域兴趣，从此融合。</p>

      <form @submit.prevent="register" style="display: flex; flex-direction: column; gap: 14px">
        <el-input v-model="form.username" placeholder="用户名（1~32 个字符）" size="large" />
        <el-input v-model="form.password" type="password" placeholder="密码（至少 6 位）" size="large" show-password />
        <el-input v-model="form.confirm" type="password" placeholder="确认密码" size="large" show-password />
        <button class="btn btn-lg" type="submit" :disabled="loading" style="width: 100%; margin-top: 6px">
          {{ loading ? '创建中…' : '注册' }}
        </button>
      </form>
      <p class="note" style="margin-top: 16px; text-align: center">
        已有账户？<router-link to="/login">直接登录</router-link>
      </p>
      <p class="note" style="margin-top: 22px">
        注册后你在图书、课程、电影三个模块的行为将汇聚为统一兴趣画像，
        实现跨领域个性化推荐（系统技术亮点）。
      </p>
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
