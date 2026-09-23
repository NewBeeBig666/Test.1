<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import request from '@/api/request'
import ItemCard from '@/components/ItemCard.vue'
import ItemDrawer from '@/components/ItemDrawer.vue'
import { useTrack } from '@/composables/useTrack'

const props = defineProps({ domain: { type: String, required: true } })
const route = useRoute()

const META = {
  books: {
    title: '图书', eyebrow: '图书天地', grad: 'grad-books',
    desc: '经典书库 9085 本 · 协同过滤 + 内容推荐',
    placeholder: '搜索书名或作者…', categories: null,
  },
  courses: {
    title: '课程', eyebrow: '课程学堂', grad: 'grad-courses',
    desc: '全球课程目录 2258 门（Udemy + 中国六大教育平台）· 跨域兴趣融合',
    placeholder: '搜索课程名称…',
    categories: [
      { en: 'Web Development', zh: '网页开发' },
      { en: 'Business Finance', zh: '商业金融' },
      { en: 'Musical Instruments', zh: '乐器演奏' },
      { en: 'Graphic Design', zh: '平面设计' },
      { en: '计算机', zh: '计算机' },
      { en: '经济管理', zh: '经济管理' },
      { en: '人文历史', zh: '人文历史' },
      { en: '基础科学', zh: '基础科学' },
      { en: '考研升学', zh: '考研升学' },
      { en: 'K12教育', zh: 'K12教育' },
      { en: '生活技能', zh: '生活技能' },
    ],
  },
  movies: {
    title: '电影', eyebrow: '光影世界', grad: 'grad-movies',
    desc: 'MovieLens 影库 3650 部 · 余弦相似度推荐',
    placeholder: '搜索电影名称…',
    categories: [
      { en: 'Action', zh: '动作' }, { en: 'Comedy', zh: '喜剧' }, { en: 'Drama', zh: '剧情' },
      { en: 'Sci-Fi', zh: '科幻' }, { en: 'Romance', zh: '爱情' }, { en: 'Thriller', zh: '惊悚' },
      { en: 'Children', zh: '儿童' }, { en: 'Documentary', zh: '纪录片' },
    ],
  },
}
const meta = META[props.domain]
const track = useTrack(props.domain)

/** 区域浏览：中国/日本/韩国/欧洲/拉美及世界其他（图书=公版世界文学，电影=国际佳作；
 *  课程域暂无版权合规的多国课程数据，保持类目筛选） */
const REGIONS = ['中国', '日本', '韩国', '欧洲', '拉美', '世界其他']
const hasRegions = computed(() => props.domain !== 'courses')

const q = ref('')
const activeCat = ref('')
const region = ref('')
const page = ref(0)
const size = 18
const total = ref(0)
const items = ref([])
const loading = ref(false)
const drawerItem = ref(null)

const search = () => { region.value = ''; load(0) }

/** 区域精选数据（world_content）-> 卡片数据（统一抽屉详情：图书负 ID） */
const mapWorld = (w) => props.domain === 'movies'
  ? { itemId: w.itemId, domain: 'movies', title: w.title, titleZh: w.titleZh,
      origTitle: w.origTitle, subtitle: w.subtitle,
      genres: w.subtitle, coverUrl: w.coverUrl, badge: w.region, note: w.note,
      recScore: w.recScore ?? w.rec_score }
  : { itemId: -w.id, domain: 'books', title: w.title, titleZh: w.titleZh,
      origTitle: w.origTitle, subtitle: w.subtitle,
      badge: w.region, note: `${w.note} · ${w.extra}`, sourceUrl: w.sourceUrl,
      recScore: w.recScore ?? w.rec_score }

const load = async (p = 0) => {
  loading.value = true
  page.value = p
  try {
    if (region.value) {
      // 区域模式：浏览该区域的精选内容（电影在 movie 表内联动详情，图书为公版经典）
      const r = await request.get('/world', {
        params: { domain: props.domain, region: region.value, page: p, size },
      })
      items.value = (r.content || []).map(mapWorld)
      total.value = r.totalElements || 0
    } else {
      const params = { domain: props.domain, q: q.value, page: p, size }
      if (activeCat.value) {
        if (props.domain === 'courses') params.category = activeCat.value
        else if (props.domain === 'movies') params.q = activeCat.value.toLowerCase()
      }
      const r = await request.get('/items', { params })
      items.value = r.content || []
      total.value = r.totalElements || 0
    }
  } finally {
    loading.value = false
    requestAnimationFrame(() => {
      items.value.forEach((it) => {
        // 仅对目录内物品埋点（区域公版图书为负 ID，不进入行为采集）
        if (typeof it.itemId === 'number' && it.itemId > 0) {
          const el = document.querySelector(`[data-item-id="${it.itemId}"]`)
          if (el) track.observeView(el, it.itemId)
        }
      })
    })
  }
}

const openItem = (item) => {
  // 统一交互：全部作品点击后在右侧打开详情抽屉（外部站点经抽屉内按钮 /away 选择）
  if (typeof item.itemId === 'number' && item.itemId > 0) {
    track.track('click', item.itemId)
  }
  drawerItem.value = item
}

watch(activeCat, () => { if (!region.value) load(0) })
watch(region, () => load(0))
onMounted(() => {
  load(0)
  // 区域精选跳转：?open={itemId} 自动打开详情抽屉
  const openId = Number(route.query.open)
  if (openId > 0) {
    request.get(`/items/${props.domain}/${openId}`)
      .then((d) => { track.track('click', openId); drawerItem.value = d })
      .catch(() => {})
  }
})
</script>

<template>
  <div>
    <section class="section-alt" style="padding: clamp(38px, 5vw, 60px) 0 24px">
      <div class="container">
        <div class="section-eyebrow">{{ meta.eyebrow }}</div>
        <h1 class="section-title" style="margin: 6px 0 8px">{{ meta.title }}馆</h1>
        <p class="text-2">{{ meta.desc }}</p>

        <div style="display: flex; gap: 12px; margin-top: 26px; max-width: 560px">
          <el-input v-model="q" :placeholder="meta.placeholder" size="large" clearable
                    :disabled="!!region"
                    @keyup.enter="search" @clear="() => { q = ''; load(0) }" />
          <button class="btn" style="padding: 0 26px" :disabled="!!region" @click="search">搜索</button>
        </div>

        <div v-if="meta.categories" style="display: flex; gap: 8px; margin-top: 18px; flex-wrap: wrap">
          <button v-for="c in meta.categories" :key="c.en" class="chip chip-lg"
                  :class="{ active: activeCat === c.en }" style="cursor: pointer; border: none"
                  @click="activeCat = activeCat === c.en ? '' : c.en">
            {{ c.zh }}
          </button>
        </div>

        <!-- 区域筛选：各栏目内便捷浏览不同地区资源 -->
        <div v-if="hasRegions" style="display: flex; gap: 8px; margin-top: 18px; flex-wrap: wrap; align-items: center">
          <span class="note" style="margin-right: 2px">按地区浏览</span>
          <button v-for="r in REGIONS" :key="r" class="chip" :class="{ active: region === r }"
                  style="cursor: pointer; border: none; padding: 6px 14px"
                  @click="region = region === r ? '' : r">
            {{ r }}
          </button>
        </div>
      </div>
    </section>

    <section class="section" style="padding-top: 20px">
      <div class="container">
        <div v-loading="loading" class="item-grid grid-6" style="min-height: 400px">
          <ItemCard v-for="item in items" :key="item.itemId" :item="item" @click="openItem(item)" />
        </div>
        <div v-if="!loading && !items.length" style="text-align: center; padding: 60px 0" class="text-3">
          没有找到匹配的内容，换个关键词试试
        </div>
        <div style="display: flex; justify-content: center; margin-top: 36px">
          <el-pagination v-if="total > size" background layout="prev, pager, next" :total="total"
                         :page-size="size" :current-page="page + 1"
                         @current-change="(p) => load(p - 1)" />
        </div>
      </div>
    </section>

    <ItemDrawer :domain="props.domain" :item="drawerItem" @close="drawerItem = null" @rated="() => {}" />
  </div>
</template>
