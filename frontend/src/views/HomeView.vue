<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import ItemCard from '@/components/ItemCard.vue'
import ItemDrawer from '@/components/ItemDrawer.vue'
import { useTrack } from '@/composables/useTrack'

const router = useRouter()
const auth = useAuthStore()

const DOMAINS = [
  { key: 'books', label: '图书', eyebrow: '图书天地', grad: 'grad-books', desc: '经典书库 9085 本' },
  { key: 'courses', label: '课程', eyebrow: '课程学堂', grad: 'grad-courses', desc: '全球课程 2258 门（Udemy + 中国六大教育平台）' },
  { key: 'movies', label: '电影', eyebrow: '光影世界', grad: 'grad-movies', desc: 'MovieLens 影库 3650 部' },
]

/** 首页区域筛选：全部（全球混排）/ 指定区域精选 */
const REGIONS = ['中国', '日本', '韩国', '欧洲', '拉美', '世界其他']
const region = ref('')

const recs = reactive({ books: [], courses: [], movies: [] })
const cold = reactive({ books: true, courses: true, movies: true })
const loading = ref(true)
const globalProfile = ref(null)
const drawerItem = ref(null)
const drawerDomain = ref('books')

const useTrackDomains = {
  books: useTrack('books'),
  courses: useTrack('courses'),
  movies: useTrack('movies'),
}

/** 区域精选条目 -> 卡片数据（统一抽屉详情：图书负 ID 指向 world_content，
 *  外部站点入口保留在抽屉内的外链按钮） */
const mapWorldItem = (w, dkey) => dkey === 'movies'
  ? { itemId: w.itemId, domain: 'movies', title: w.title, titleZh: w.titleZh,
      origTitle: w.origTitle, subtitle: w.subtitle,
      genres: w.subtitle, coverUrl: w.coverUrl, badge: w.region, note: w.note,
      recScore: w.recScore ?? w.rec_score }
  : { itemId: -w.id, domain: dkey, title: w.title, titleZh: w.titleZh,
      origTitle: w.origTitle, subtitle: w.subtitle,
      badge: w.region, note: w.note, sourceUrl: w.sourceUrl,
      recScore: w.recScore ?? w.rec_score }

const openItem = (item, domain) => {
  // 统一交互：全部作品点击后在右侧打开详情抽屉（外部站点经抽屉内按钮 /away 选择）
  if (typeof item.itemId === 'number' && item.itemId > 0) {
    useTrackDomains[domain].track('click', item.itemId)
  }
  drawerDomain.value = domain
  drawerItem.value = item
}

const loadAll = async () => {
  loading.value = true
  await Promise.all(DOMAINS.map(async (d) => {
    try {
      if (region.value) {
        // 区域模式：课程域支持中国课程（国内六大平台）；其他区域暂未收录
        if (d.key === 'courses') {
          if (region.value === '中国') {
            const rc = await request.get('/world', {
              params: { domain: 'courses', region: '中国', size: 12 },
            }).catch(() => null)
            recs[d.key] = (rc?.content || []).map((c) => ({ ...c, domain: 'courses' }))
          } else {
            recs[d.key] = []
          }
          return
        }
        const r = await request.get('/world', {
          params: { domain: d.key, region: region.value, size: 12 },
        })
        recs[d.key] = (r.content || []).map((w) => mapWorldItem(w, d.key))
        cold[d.key] = false
        return
      }
      // 全部模式：全球发现流 6 条 + 个性化推荐 6 条交错（区域多样 + 个性兼顾）
      const [rec, disco] = await Promise.all([
        request.get('/rec/recommend', { params: { domain: d.key, algo: 'ItemCF', n: 6 } }).catch(() => null),
        request.get('/items', { params: { domain: d.key, size: 6 } }).catch(() => null),
      ])
      // 推荐响应为下划线字段，统一映射为 ItemCard 读取的驼峰字段
      const recItems = (rec?.items || []).map((it) => ({
        ...it,
        itemId: it.item_id ?? it.itemId,
        titleZh: it.title_zh ?? it.titleZh,
        origTitle: it.orig_title ?? it.origTitle,
        recScore: it.rec_score ?? it.recScore,
        coverUrl: it.cover_url ?? it.coverUrl,
        imageUrl: it.image_url ?? it.imageUrl,
        sourceUrl: it.source_url ?? it.sourceUrl,
      }))
      const discoItems = disco?.content || []
      const mixed = []
      for (let i = 0; i < Math.max(recItems.length, discoItems.length); i++) {
        if (discoItems[i]) mixed.push(discoItems[i])
        if (recItems[i]) mixed.push(recItems[i])
      }
      recs[d.key] = mixed
      cold[d.key] = !!rec?.cold_start
    } catch (e) { /* 单域失败不阻塞页面 */ }
  }))
  loading.value = false
  request.get('/rec/profile/global').then(p => { globalProfile.value = p }).catch(() => {})
  requestTick()
}

/** 渐入动画 + view 曝光埋点（仅目录内物品：正数 itemId） */
const requestTick = () => {
  requestAnimationFrame(() => {
    document.querySelectorAll('.reveal:not(.in)').forEach((el) => io.observe(el))
    document.querySelectorAll('.hscroll .item-card[data-item-id]').forEach((el) => {
      const id = Number(el.dataset.itemId)
      if (!(id > 0)) return
      const domain = el.closest('[data-domain]')?.dataset.domain
      if (domain) useTrackDomains[domain].observeView(el, id)
    })
  })
}
const io = new IntersectionObserver((entries) => {
  entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target) } })
}, { threshold: 0.12 })

watch(region, loadAll)
onMounted(loadAll)
</script>

<template>
  <div>
    <!-- ================= Hero ================= -->
    <section class="section-alt" style="text-align: center; padding-top: clamp(44px, 6vw, 84px); padding-bottom: clamp(36px, 5vw, 56px)">
      <div class="container">
        <div class="reveal">
          <div class="section-eyebrow" style="margin-bottom: 14px">个性化推荐系统</div>
          <h1 class="hero-title">为你而荐。<br /><span class="text-2">三个领域，一份兴趣。</span></h1>
          <p class="text-2" style="max-width: 640px; margin: 22px auto 0; font-size: 19px">
            基于协同过滤与内容理解的推荐引擎，融合你在<strong>图书、课程、电影</strong>
            三个领域的行为，构建统一兴趣画像。
          </p>
          <div style="display: flex; gap: 14px; justify-content: center; margin-top: 32px; flex-wrap: wrap">
            <button class="btn btn-lg" @click="router.push('/books')">开始探索</button>
            <button class="btn btn-lg btn-ghost" @click="router.push('/lab')">算法实验室</button>
          </div>
        </div>
      </div>

      <!-- 区域筛选：首页三栏目统一的全球内容过滤 -->
      <div class="container reveal" style="margin-top: 34px">
        <div style="display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; align-items: center">
          <span class="note" style="margin-right: 4px">按地区浏览全球内容</span>
          <button class="chip chip-lg" :class="{ active: !region }" style="cursor: pointer; border: none"
                  @click="region = ''">全部地区</button>
          <button v-for="r in REGIONS" :key="r" class="chip chip-lg" :class="{ active: region === r }"
                  style="cursor: pointer; border: none" @click="region = r">{{ r }}</button>
        </div>
      </div>
    </section>

    <!-- ================= 跨域画像速览 ================= -->
    <section v-if="globalProfile" class="section" style="padding-top: 30px; padding-bottom: 0">
      <div class="container reveal">
        <div class="card" style="padding: 30px 34px; background: linear-gradient(135deg, #fbfbfd 0%, #f0f4fa 100%)">
          <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px">
            <div>
              <div class="section-eyebrow">Cross-Domain Profile</div>
              <h2 class="section-title" style="font-size: 30px; margin-top: 4px">你的跨域兴趣画像</h2>
            </div>
            <router-link to="/profile" style="font-size: 15px">查看完整画像 →</router-link>
          </div>
          <div class="tag-cloud" style="margin-top: 18px">
            <span v-for="t in (globalProfile.interest_tags || []).slice(0, 12)" :key="t.tag"
                  class="chip chip-lg" :style="{ background: `rgba(0,113,227,${0.06 + t.weight * 0.35})`, color: 'var(--text)' }">
              {{ t.tag }}
            </span>
          </div>
          <div style="display: flex; gap: 26px; margin-top: 20px; flex-wrap: wrap">
            <div v-for="(v, d) in globalProfile.domains" :key="d" style="display: flex; align-items: center; gap: 8px">
              <span class="chip" :class="{ books: 'chip-d', courses: 'chip-c', movies: 'chip-m' }[d]"
                    :style="{ background: 'rgba(0,0,0,0.05)' }">{{ { books: '图书', courses: '课程', movies: '电影' }[d] }}</span>
              <span class="note">{{ v.interactions }} 条行为</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ================= 三域推荐（全球多样 + 个性化交错） ================= -->
    <section v-for="d in DOMAINS" :key="d.key" class="section" :class="d.key !== 'courses' ? 'section-alt' : ''"
             style="padding-top: 28px; padding-bottom: 28px" :data-domain="d.key">
      <div class="container reveal">
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px">
          <div>
            <div class="section-eyebrow">{{ d.eyebrow }}</div>
            <h2 class="section-title" style="font-size: 34px; margin-top: 4px">
              {{ region ? region + '·' : '' }}{{ d.label }}{{ region ? '精选' : ' · 全球精选 × 为你推荐' }}
            </h2>
            <p class="note" style="margin-top: 4px">{{ region ? '版权合规的该区域精选内容' : d.desc + ' · 区域标签全覆盖' }}</p>
          </div>
          <router-link :to="'/' + d.key" style="font-size: 15px">浏览全部 →</router-link>
        </div>

        <el-alert v-if="cold[d.key] && !loading && !region" type="info" :closable="false" style="margin-top: 18px; border-radius: 14px">
          你在该领域还没有足够的行为数据，个性化部分暂以热门内容补充。去
          <router-link :to="'/' + d.key">{{ d.label }}馆</router-link>
          浏览、评分或收藏，即刻获得个性化推荐。
        </el-alert>
        <el-alert v-if="region && region !== '中国' && d.key === 'courses' && !loading" type="info" :closable="false"
                  style="margin-top: 18px; border-radius: 14px">
          该地区课程内容暂未收录（国际课程以美国平台为主），可切换"中国"查看国内六大平台课程。
        </el-alert>

        <div v-loading="loading" class="hscroll" style="margin-top: 22px; min-height: 330px">
          <ItemCard v-for="item in recs[d.key]" :key="item.itemId"
                    :item="{ ...item, itemId: item.itemId ?? item.item_id }"
                    @click="openItem({ ...item, itemId: item.itemId ?? item.item_id }, d.key)" />
        </div>
      </div>
    </section>

    <ItemDrawer :domain="drawerDomain" :item="drawerItem" @close="drawerItem = null" @rated="loadAll" />
  </div>
</template>
