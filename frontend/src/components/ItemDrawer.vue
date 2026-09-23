<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

const props = defineProps({
  domain: { type: String, required: true },
  item: { type: Object, default: null },
})
const emit = defineEmits(['close', 'rated'])
const router = useRouter()

const visible = computed({
  get: () => !!props.item,
  set: (v) => !v && emit('close'),
})
const rating = ref(0)
const favorited = ref(false)
const submitting = ref(false)

/** 详情富化：封面 / 结构化简介 / 外部链接（首次抓取缓存，cached 标记） */
const enrich = ref(null)
const enrichLoading = ref(false)

const DOMAIN_LABEL = { books: '图书', courses: '课程', movies: '电影' }
const TYPE_LABEL = { read: '阅读', buy: '购买', info: '详情', study: '学习' }

const GENRE_ZH = {
  Action: '动作', Adventure: '冒险', Animation: '动画', Children: '儿童', Comedy: '喜剧',
  Crime: '犯罪', Documentary: '纪录片', Drama: '剧情', Fantasy: '奇幻', 'Film-Noir': '黑色',
  Horror: '恐怖', IMAX: 'IMAX', Musical: '音乐剧', Mystery: '悬疑', Romance: '爱情',
  'Sci-Fi': '科幻', Thriller: '惊悚', War: '战争', Western: '西部',
}
const CAT_ZH = {
  'Web Development': '网页开发', 'Business Finance': '商业金融',
  'Musical Instruments': '乐器演奏', 'Graphic Design': '平面设计',
}
const LEVEL_ZH = {
  'All Levels': '通用', 'Beginner Level': '入门', 'Intermediate Level': '进阶', 'Expert Level': '高级',
}

/** 副标题行：电影类型 / 课程难度 中文化；图书显示作者 */
const subHead = computed(() => {
  const it = props.item
  if (!it) return ''
  if (props.domain === 'movies') {
    return (it.genres || it.subtitle || '').split(/[ |·]+/).filter(Boolean)
      .map((g) => GENRE_ZH[g] || g).join(' · ')
  }
  if (props.domain === 'courses') {
    return [LEVEL_ZH[it.subtitle] || it.subtitle, CAT_ZH[it.extra] || it.extra]
      .filter(Boolean).join(' · ')
  }
  return it.subtitle || ''
})

/** extra 语义随域变化：图书=出版社（区域公版为分类）、课程=类目；电影 extra 为年份（已有年份行，跳过） */
const extraRow = computed(() => {
  const it = props.item
  if (!it || !it.extra || props.domain === 'movies') return null
  const label = props.domain === 'courses' ? '类别'
    : (typeof it.itemId === 'number' && it.itemId < 0 ? '分类' : '出版社')
  return { label, value: props.domain === 'courses' ? (CAT_ZH[it.extra] || it.extra) : it.extra }
})

/** 区域公版图书（负 ID）：不参与行为采集（评分/收藏区隐藏） */
const isWorldBook = computed(() =>
  props.domain === 'books' && typeof props.item?.itemId === 'number' && props.item.itemId < 0)

/** 推荐指数（1-10 分制，全网公开数据综合评定；rec_score 优先，算法热度兜底换算） */
const scoreRow = computed(() => {
  const it = props.item
  const r = it?.recScore ?? it?.rec_score
  if (r != null) {
    return { label: '推荐指数', value: `${Number(r).toFixed(1)} / 10`, pct: Number(r) * 10 }
  }
  const s = it?.score
  if (s == null) return null
  return s <= 1
    ? { label: '推荐匹配度', value: `${(s * 100).toFixed(1)}%`, pct: s * 100 }
    : { label: '推荐指数', value: `${Math.min(9.9, 5 + Math.log10(Math.max(s, 1)) * 2).toFixed(1)} / 10`,
        pct: Math.min(100, 50 + Math.log10(Math.max(s, 1)) * 20) }
})

/** 价格：0 显示"免费"（中国 MOOC 免费学习为主） */
const priceText = computed(() => {
  const p = props.item?.price
  if (p == null) return null
  return Number(p) === 0 ? '免费' : `$${p}`
})

const bigCover = computed(() => {
  const it = props.item
  if (!it) return null
  return it.imageUrl || it.image_url || enrich.value?.cover?.url || it.coverUrl || null
})

const sections = computed(() => enrich.value?.summary?.sections || [])
const links = computed(() => enrich.value?.links || [])

watch(() => props.item, async (it) => {
  rating.value = 0
  favorited.value = false
  enrich.value = null
  if (!it) return
  enrichLoading.value = true
  try {
    request.get(`/items/${props.domain}/${it.itemId}`).then(d => Object.assign(it, d)).catch(() => {})
    enrich.value = await request.get(`/enrichment/${props.domain}/${it.itemId}`)
  } catch (e) {
    /* 富化失败不影响详情基础展示 */
  } finally {
    enrichLoading.value = false
  }
}, { immediate: true })

/** 外链安全跳转：统一过渡页（/away）——国内优先、倒计时选择、返回平台导航 */
const openExternal = (link) => {
  router.push({ name: 'away', query: { url: link.url, title: props.item?.titleZh || props.item?.title || link.label || '',
                                       domain: props.domain } })
}

const submitRating = async () => {
  if (!rating.value) return
  submitting.value = true
  try {
    await request.post('/event', { itemId: props.item.itemId, domain: props.domain, eventType: 'rating', rating: rating.value })
    ElMessage.success('评分已记录，推荐结果将实时更新')
    emit('rated')
  } finally {
    submitting.value = false
  }
}

const toggleFavorite = async () => {
  if (favorited.value) return
  try {
    await request.post('/event', { itemId: props.item.itemId, domain: props.domain, eventType: 'favorite' })
    favorited.value = true
    ElMessage.success('已收藏')
    emit('rated')
  } catch (e) { /* ignore */ }
}
</script>

<template>
  <el-drawer v-model="visible" :size="460" :title="DOMAIN_LABEL[domain] + ' · 详情'">
    <div v-if="item" style="display: flex; flex-direction: column; gap: 18px">
      <!-- 高清封面 -->
      <div class="big-cover">
        <img v-if="bigCover" :src="bigCover" :alt="item.title"
             @error="$event.target.style.display = 'none'" />
        <div v-else class="big-cover-fallback" :class="{ books: 'grad-books', courses: 'grad-courses', movies: 'grad-movies' }[domain]">
          <span style="font-size: 44px; opacity: 0.9">{{ { books: '📖', courses: '🎓', movies: '🎬' }[domain] }}</span>
        </div>
        <span v-if="enrich?.cover?.width" class="chip res-badge">
          {{ enrich.cover.width }}×{{ enrich.cover.height }}px
        </span>
      </div>

      <div>
        <h2 style="font-size: 24px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.2">
          {{ item.titleZh || item.title }}
        </h2>
        <p v-if="item.titleZh && item.badge !== '中国' && (item.origTitle || item.title)"
           class="text-3" style="margin-top: 4px; font-size: 14px">
          {{ item.origTitle || item.title }}
        </p>
        <p v-if="subHead" class="text-2" style="margin-top: 8px; font-size: 15px">{{ subHead }}</p>
      </div>

      <!-- 外部链接（安全跳转） -->
      <div v-if="links.length" style="display: flex; gap: 10px; flex-wrap: wrap">
        <button v-for="l in links" :key="l.url" class="btn btn-ghost" style="padding: 8px 16px"
                @click="openExternal(l)">
          {{ TYPE_LABEL[l.type] || '访问' }} ↗ {{ l.label }}
        </button>
      </div>

      <!-- 内容简介（格式化模块） -->
      <div v-loading="enrichLoading" style="min-height: 60px">
        <template v-if="sections.length">
          <div v-for="s in sections" :key="s.label" class="summary-block">
            <div class="summary-label">{{ s.label }}</div>
            <p class="summary-text">{{ s.text }}</p>
          </div>
          <div class="note" style="margin-top: 4px">
            简介来源：{{ { openlibrary: 'OpenLibrary', imdb: 'IMDb', synthetic: '系统生成', admin: '管理员编辑' }[enrich?.summary?.source] || enrich?.summary?.source || '—' }}
            <el-tag v-if="enrich?.manual" size="small" style="margin-left: 6px">人工编辑</el-tag>
            <el-tag v-else-if="enrich?.cached" size="small" type="info" style="margin-left: 6px">已缓存</el-tag>
          </div>
        </template>
        <p v-else-if="!enrichLoading" class="note">暂无简介（外部数据源受限，可在管理后台补充）</p>
      </div>

      <el-descriptions :column="1" border size="small">
        <el-descriptions-item v-if="extraRow" :label="extraRow.label">{{ extraRow.value }}</el-descriptions-item>
        <el-descriptions-item v-if="item.platform" label="平台">{{ item.platform }}</el-descriptions-item>
        <el-descriptions-item v-if="priceText" label="价格">{{ priceText }}</el-descriptions-item>
        <el-descriptions-item v-if="item.subscribers != null" label="学习人数">{{ Number(item.subscribers).toLocaleString() }}</el-descriptions-item>
        <el-descriptions-item v-if="item.year" label="年份">{{ item.year }}</el-descriptions-item>
        <el-descriptions-item v-if="scoreRow" :label="scoreRow.label">
          <span style="display: inline-flex; align-items: center; gap: 8px">
            <span style="color: #f5a623; font-weight: 700; font-size: 15px">{{ scoreRow.value }}</span>
            <span class="score-track"><span class="score-fill" :style="{ width: scoreRow.pct + '%' }"></span></span>
          </span>
        </el-descriptions-item>
      </el-descriptions>

      <div style="padding: 18px; background: var(--bg-alt); border-radius: 14px">
        <template v-if="isWorldBook">
          <div style="font-weight: 600; margin-bottom: 8px">区域公版经典</div>
          <p class="note" style="margin: 0; line-height: 1.6">
            该作品为多区域内容库精选（不参与个性化行为采集）。可通过上方链接前往
            豆瓣读书、微信读书等站点阅读或购买。
          </p>
        </template>
        <template v-else>
        <div style="font-weight: 600; margin-bottom: 12px">你的评分</div>
        <div style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap">
          <el-rate v-model="rating" size="large" />
          <button class="btn" style="padding: 8px 18px" :disabled="!rating || submitting" @click="submitRating">
            {{ submitting ? '提交中…' : '提交评分' }}
          </button>
          <button class="btn btn-ghost" style="padding: 8px 18px" :disabled="favorited" @click="toggleFavorite">
            {{ favorited ? '♥ 已收藏' : '♡ 收藏' }}
          </button>
        </div>
        <p class="note" style="margin-top: 10px">评分与收藏会即时进入推荐模型（评分后自动重训），影响三个模块的个性化结果。</p>
        </template>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.big-cover { position: relative; border-radius: 14px; overflow: hidden; aspect-ratio: 3 / 4; max-height: 340px; }
.big-cover img { width: 100%; height: 100%; object-fit: contain; background: var(--bg-alt); }
.big-cover-fallback { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
.res-badge { position: absolute; right: 10px; bottom: 10px; background: rgba(0,0,0,0.55); color: #fff; }
.summary-block { padding: 14px 16px; background: var(--bg-alt); border-radius: 14px; margin-bottom: 10px; }
.summary-label { font-weight: 700; font-size: 14px; margin-bottom: 6px; color: var(--accent); }
.summary-text { font-size: 14.5px; line-height: 1.65; color: var(--text); white-space: pre-line; }
.score-track { display: inline-block; width: 90px; height: 6px; border-radius: 3px; background: var(--bg-alt); overflow: hidden; }
.score-fill { display: block; height: 100%; border-radius: 3px; background: linear-gradient(90deg, #f5a623, #f7c948); }
</style>
