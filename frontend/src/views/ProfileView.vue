<script setup>
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import request from '@/api/request'

const auth = useAuthStore()
const profile = ref(null)
const history = ref([])
const loading = ref(true)

const DOMAIN_LABEL = { books: '图书', courses: '课程', movies: '电影' }
const DOMAIN_CHIP = { books: 'chip-d', courses: 'chip-c', movies: 'chip-m' }
const TYPE_LABEL = { view: '浏览', click: '点击', rating: '评分', favorite: '收藏' }

onMounted(async () => {
  try {
    profile.value = await request.get('/rec/profile/global', { params: { top_tags: 15 } })
  } catch (e) { /* 冷启动用户无画像 */ }
  try {
    history.value = await request.get('/event/history')
  } catch (e) { /* ignore */ }
  loading.value = false
})

const fmtTime = (t) => (t || '').replace('T', ' ').slice(0, 16)
</script>

<template>
  <div>
    <section class="section-alt" style="padding: clamp(38px, 5vw, 60px) 0 28px">
      <div class="container">
        <div class="section-eyebrow">User Profile</div>
        <h1 class="section-title" style="margin: 6px 0 8px">兴趣画像</h1>
        <p class="text-2">你在三个领域的行为，融合为统一的兴趣标签（统一 TF-IDF 词表，跨域共享）。</p>

        <div v-if="profile" class="card" style="margin-top: 30px; padding: 30px 34px">
          <div style="font-weight: 700; font-size: 19px; margin-bottom: 16px">统一兴趣标签</div>
          <div class="tag-cloud">
            <span v-for="t in profile.interest_tags" :key="t.tag" class="chip chip-lg"
                  :style="{ background: `rgba(0,113,227,${0.05 + t.weight * 0.4})`, color: 'var(--text)' }">
              {{ t.tag }}<span class="text-3" style="margin-left: 6px">{{ t.weight.toFixed(2) }}</span>
            </span>
          </div>
        </div>
        <el-alert v-else-if="!loading" type="info" :closable="false" style="margin-top: 30px; border-radius: 14px">
          暂无画像：去图书 / 课程 / 电影馆浏览、评分或收藏，系统将立即为你构建跨域兴趣画像。
        </el-alert>
      </div>
    </section>

    <section class="section" style="padding-top: 34px" v-if="profile">
      <div class="container">
        <h2 class="section-title" style="font-size: 30px">分域画像</h2>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 22px; margin-top: 24px">
          <div v-for="(v, d) in profile.domains" :key="d" class="card" style="padding: 26px">
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span class="chip chip-lg" :class="DOMAIN_CHIP[d]">{{ DOMAIN_LABEL[d] }}</span>
              <span class="note">{{ v.interactions }} 条行为</span>
            </div>
            <div v-if="v.interest_tags.length" class="tag-cloud" style="margin-top: 18px">
              <span v-for="t in v.interest_tags.slice(0, 10)" :key="t.tag" class="chip">{{ t.tag }}</span>
            </div>
            <p v-else class="note" style="margin-top: 16px">暂无该领域行为，去逛逛 →</p>
          </div>
        </div>
      </div>
    </section>

    <section class="section section-alt" style="padding-top: 34px">
      <div class="container">
        <h2 class="section-title" style="font-size: 30px">最近行为</h2>
        <p class="note" style="margin: 6px 0 22px">浏览 / 点击 / 评分 / 收藏均被采集，评分后自动触发模型增量重训。</p>
        <div v-if="history.length" class="card" style="overflow: hidden">
          <table class="data-table">
            <thead>
              <tr><th>时间</th><th>领域</th><th>行为</th><th>物品</th><th>评分</th></tr>
            </thead>
            <tbody>
              <tr v-for="e in history" :key="e.id">
                <td class="text-3">{{ fmtTime(e.createdAt) }}</td>
                <td><span class="chip" :class="DOMAIN_CHIP[e.domain]">{{ DOMAIN_LABEL[e.domain] }}</span></td>
                <td><span class="chip">{{ TYPE_LABEL[e.eventType] }}</span></td>
                <td style="max-width: 420px; overflow: hidden; text-overflow: ellipsis">{{ e.title }}</td>
                <td>{{ e.rating ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="text-3">暂无行为记录</p>
      </div>
    </section>
  </div>
</template>
