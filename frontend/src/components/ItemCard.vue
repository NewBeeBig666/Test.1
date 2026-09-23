<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
  badge: { type: String, default: '' },
  note: { type: String, default: '' },
})

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

const DOMAIN_META = {
  books: { grad: 'grad-books', label: '图书' },
  courses: { grad: 'grad-courses', label: '课程' },
  movies: { grad: 'grad-movies', label: '电影' },
}
const meta = computed(() => DOMAIN_META[props.item.domain] || DOMAIN_META.books)

const region = computed(() => props.badge || props.item.badge || '')

// 双语显示：主行中文名（无译名回退原标题）；中国作品仅显示中文，海外作品副行显示原语言名
const mainTitle = computed(() => props.item.titleZh || props.item.title)
const origTitle = computed(() => {
  if (!props.item.titleZh || region.value === '中国') return ''
  return props.item.origTitle || props.item.title || ''
})

// 封面来源：books.imageUrl / movies.coverUrl（IMDb 海报）/ courses.poster_url
const hasCover = computed(() => {
  const it = props.item
  return !!(it.image_url || it.imageUrl || it.cover_url || it.coverUrl)
})
const coverSrc = computed(() => {
  const it = props.item
  return it.image_url || it.imageUrl || it.cover_url || it.coverUrl || ''
})

// 课程类目图标（矢量，无限分辨率，响应式自适应）
const COURSE_ICON = {
  'Web Development': '⌘',
  'Business Finance': '¥',
  'Musical Instruments': '♫',
  'Graphic Design': '✎',
}
const courseIcon = computed(() => COURSE_ICON[props.item.extra] || '◈')

// 封面排版副标题（无图渐变卡上显示；电影类型/课程类目难度中文化）
const coverSub = computed(() => {
  const it = props.item
  if (it.domain === 'courses') {
    return `${LEVEL_ZH[it.subtitle] || it.subtitle || ''} · ${CAT_ZH[it.extra] || it.extra || ''}`
  }
  if (it.domain === 'movies') {
    return (it.genres || it.subtitle || '').split(' ').slice(0, 4)
      .map((g) => GENRE_ZH[g] || g).join(' · ')
  }
  return it.subtitle || ''
})

// 卡片副标题：区域说明 > 双语原名 > 域元数据
const subLine = computed(() => {
  if (props.note || props.item.note) return props.note || props.item.note
  if (origTitle.value) return origTitle.value
  const it = props.item
  if (it.domain === 'books') return it.subtitle
  if (it.domain === 'courses') {
    const learn = it.subscribers != null ? ` · ${Number(it.subscribers).toLocaleString()} 人已学习` : ''
    return (CAT_ZH[it.extra] || it.extra || '') + learn
  }
  return (it.genres || it.subtitle || '').split(' ').map((g) => GENRE_ZH[g] || g).join(' · ')
})

// 推荐指数（1-10 分制，全网公开数据综合评定；rec_score 优先，算法热度兜底换算）
const scoreText = computed(() => {
  const it = props.item
  const r = it.recScore ?? it.rec_score
  if (r != null) return `推荐指数 ${Number(r).toFixed(1)}`
  const s = it.score
  if (s == null) return null
  return s <= 1 ? `匹配度 ${(s * 100).toFixed(1)}%`
    : `推荐指数 ${Math.min(9.9, 5 + Math.log10(Math.max(s, 1)) * 2).toFixed(1)}`
})
</script>

<template>
  <div class="item-card card" :data-item-id="item.itemId">
    <div class="item-cover" :class="hasCover ? '' : (item.domain === 'courses' ? 'course-cover ' + meta.grad : meta.grad)">
      <img v-if="hasCover" :src="coverSrc" :alt="mainTitle" loading="lazy"
           @error="$event.target.style.display = 'none'" />
      <template v-else-if="item.domain === 'courses'">
        <div class="course-glyph">{{ courseIcon }}</div>
        <div class="cover-typo">
          <div class="t">{{ mainTitle }}</div>
          <div class="s">{{ coverSub }}</div>
        </div>
      </template>
      <div v-else class="cover-typo">
        <div class="t">{{ mainTitle }}</div>
        <div class="s">{{ coverSub }}</div>
      </div>
    </div>
    <div class="item-body">
      <div v-if="region" style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 2px">
        <span class="chip" :class="{ 中国: 'chip-d', 日本: 'chip-d', 韩国: 'chip-c' }[region] || 'chip-m'">
          {{ region }}
        </span>
      </div>
      <div class="item-title">{{ mainTitle }}</div>
      <div class="item-sub">{{ subLine }}</div>
      <div class="item-score" v-if="scoreText"><span style="color:#f5a623">★</span> {{ scoreText }}</div>
      <div v-else-if="item.price != null" class="note">${{ item.price }}</div>
    </div>
  </div>
</template>

<style scoped>
.course-cover { align-items: center; justify-content: center; text-align: center; padding-top: 26px; }
.course-glyph {
  font-size: 64px;
  color: rgba(255, 255, 255, 0.92);
  text-shadow: 0 4px 18px rgba(0, 0, 0, 0.35);
  line-height: 1;
}
.course-cover .cover-typo { align-self: stretch; text-align: left; }
@media (max-width: 560px) { .course-glyph { font-size: 48px; } }
</style>
