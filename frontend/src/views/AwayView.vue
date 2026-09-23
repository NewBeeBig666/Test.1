<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const url = computed(() => String(route.query.url || ''))
const title = computed(() => decodeURIComponent(String(route.query.title || '')) || '外部内容')
const domain = computed(() => String(route.query.domain || ''))
const COUNTDOWN = 4
const left = ref(COUNTDOWN)
let timer = null
let opened = false

/** 国内站点清单（全网主流资源平台，按域分组；国内优先原则） */
const CN_DOMAINS = ['douban.com', 'bilibili.com', 'v.qq.com', 'iqiyi.com', 'youku.com',
  'mgtv.com', 'weread.qq.com', 'jd.com', 'dangdang.com', 'icourse163.org', 'xuetangx.com',
  'open.163.com', 'smartedu.cn', 'ouchn.cn', 'sciencenet.cn', 'cnki.net']

const q = (s) => encodeURIComponent(s)
const cleanTitle = computed(() => title.value.replace(/\s*[（(]\d{4}[）)]\s*$/, '').trim())

const CN_SITES = {
  movies: [
    { name: '豆瓣电影', desc: '评分 / 评论 / 影片资料', url: (t) => `https://search.douban.com/movie/subject_search?search_text=${q(t)}` },
    { name: '哔哩哔哩', desc: '影视剪辑 / 弹幕讨论', url: (t) => `https://search.bilibili.com/all?keyword=${q(t)}` },
    { name: '腾讯视频', desc: '正版在线观看', url: (t) => `https://v.qq.com/x/search/?q=${q(t)}` },
    { name: '爱奇艺', desc: '正版在线观看', url: (t) => `https://so.iqiyi.com/so/q_${q(t)}` },
    { name: '优酷', desc: '正版在线观看', url: (t) => `https://so.youku.com/search_video/q_${q(t)}` },
    { name: '芒果TV', desc: '正版在线观看', url: (t) => `https://so.mgtv.com/so/k-${q(t)}` },
  ],
  books: [
    { name: '豆瓣读书', desc: '评分 / 书评 / 资料页', url: (t) => `https://book.douban.com/subject_search?search_text=${q(t)}` },
    { name: '微信读书', desc: '在线阅读 / 听书（直达书页）', url: (t) => `/api/weread?q=${q(t)}` },
    { name: '京东图书', desc: '购买正版纸质书', url: (t) => `https://search.jd.com/Search?keyword=${q(t)}&enc=utf-8` },
    { name: '当当图书', desc: '购买正版纸质书', url: (t) => `http://search.dangdang.com/?key=${q(t)}` },
  ],
  courses: [
    { name: '中国大学MOOC', desc: '清华北大等名校课程', url: (t) => `https://www.icourse163.org/search.htm?search=${q(t)}` },
    { name: '学堂在线', desc: '清华大学发起的慕课平台', url: (t) => `https://www.xuetangx.com/search?query=${q(t)}` },
    { name: '国家高等教育智慧教育平台', desc: '教育部官方出品', url: () => 'https://higher.smartedu.cn/' },
    { name: '国家中小学智慧教育平台', desc: 'K12 同步课与素质教育', url: () => 'https://basic.smartedu.cn/' },
    { name: '终身教育平台', desc: '国家开放大学主办', url: () => 'https://le.ouchn.cn/' },
    { name: '网易公开课', desc: '名校公开课 / TED / 可汗学院', url: () => 'https://open.163.com/' },
    { name: '哔哩哔哩课堂', desc: '视频课程检索', url: (t) => `https://search.bilibili.com/all?keyword=${q(t)}` },
  ],
}

const isCnUrl = (u) => {
  // 平台自有的微信读书跳转代理（相对路径，服务端检索后 302 直达书页）
  if (String(u).startsWith('/api/weread')) return true
  try {
    const h = new URL(u).hostname
    return CN_DOMAINS.some((d) => h === d || h.endsWith(`.${d}`))
  } catch (e) {
    return false
  }
}

/** 国内选项：原始链接若为国内域名则置顶（最精确直达），否则按域生成国内站点搜索 */
const cnOptions = computed(() => {
  const list = (CN_SITES[domain.value] || []).map((s) => ({
    name: s.name, desc: s.desc, url: s.url(cleanTitle.value || title.value),
  }))
  if (url.value && isCnUrl(url.value)) {
    let host = url.value
    try { host = new URL(url.value).hostname } catch (e) { /* 相对路径代理 */ }
    const isProxy = String(url.value).startsWith('/api/weread')
    list.unshift({ name: isProxy ? '微信读书 · 直达书页' : '官方页面',
                   desc: isProxy ? '服务端检索后直达书籍详情' : host, url: url.value })
  }
  return list
})

/** 海外选项：原始链接（当前保留供用户选择） */
const overseaOption = computed(() => {
  if (!url.value || isCnUrl(url.value)) return null
  let host = url.value
  try { host = new URL(url.value).hostname } catch (e) { /* ignore */ }
  return { name: '海外原始来源', desc: host, url: url.value }
})

const go = (u) => {
  if (timer) { clearInterval(timer); timer = null }
  if (u) window.open(u, '_blank', 'noopener,noreferrer')
  opened = true
  router.back()
}

onMounted(() => {
  timer = setInterval(() => {
    left.value -= 1
    if (left.value <= 0 && !opened) {
      go(cnOptions.value[0]?.url)
    }
  }, 1000)
})
onBeforeUnmount(() => timer && clearInterval(timer))
</script>

<template>
  <div class="away-wrap">
    <div class="away-card reveal in">
      <div class="away-glyph"><span class="spin"></span></div>
      <h1 style="font-size: 25px; font-weight: 700; letter-spacing: -0.02em; margin-top: 6px">
        即将前往外部内容
      </h1>
      <p class="text-2" style="margin-top: 8px; word-break: break-all; font-size: 15px; text-align: center">
        {{ title }}
      </p>

      <div class="away-progress">
        <div class="away-bar" :style="{ animationDuration: COUNTDOWN + 's' }"></div>
      </div>
      <p class="note" style="margin-top: 10px">
        {{ left }} 秒后自动打开 <strong>国内推荐站点</strong>（蓝色高亮项）；点击下方任一站点可立即切换，
        访问海外站点请展开海外选项。
      </p>

      <!-- 国内资源（默认优先） -->
      <div class="away-group">
        <div class="away-group-title">
          <span class="chip chip-lg" style="background: rgba(0,113,227,.08)">国内资源 · 推荐</span>
        </div>
        <div class="away-links">
          <button v-for="(s, i) in cnOptions" :key="s.url" class="away-link"
                  :class="{ primary: i === 0 }" @click="go(s.url)">
            <div style="min-width: 0; text-align: left">
              <div class="away-link-name">{{ s.name }}<span v-if="i === 0" class="away-default">默认</span></div>
              <div class="away-link-desc">{{ s.desc }}</div>
            </div>
            <span class="away-go">打开 ↗</span>
          </button>
        </div>
      </div>

      <!-- 海外资源（保留可选） -->
      <div v-if="overseaOption" class="away-group">
        <div class="away-group-title">
          <span class="chip" style="background: rgba(0,0,0,.05)">海外资源 · 可选</span>
        </div>
        <div class="away-links">
          <button class="away-link oversea" @click="go(overseaOption.url)">
            <div style="min-width: 0; text-align: left">
              <div class="away-link-name">{{ overseaOption.name }}</div>
              <div class="away-link-desc">{{ overseaOption.desc }} · 需国际网络环境</div>
            </div>
            <span class="away-go">打开 ↗</span>
          </button>
        </div>
      </div>

      <div style="display: flex; gap: 12px; margin-top: 24px; flex-wrap: wrap">
        <button class="btn btn-lg" @click="go(cnOptions[0]?.url)">立即前往国内站点 ↗</button>
        <button class="btn btn-lg btn-ghost" @click="router.back()">返回平台</button>
      </div>
      <p class="note" style="margin-top: 14px">
        安全提示：以上站点均为第三方平台，内容由对应平台提供；新窗口打开，可随时返回本站。
      </p>
    </div>
  </div>
</template>

<style scoped>
.away-wrap {
  min-height: calc(100vh - var(--nav-h));
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(1100px 560px at 50% -8%, #eef3fb 0%, var(--bg-alt) 62%);
  padding: 40px 22px;
}
.away-card {
  background: #fff;
  border-radius: 24px;
  box-shadow: var(--card-shadow-hover);
  padding: 42px 40px;
  max-width: 560px;
  width: 100%;
  text-align: center;
}
.away-glyph {
  width: 60px; height: 60px; margin: 0 auto;
  border-radius: 50%; background: var(--bg-alt);
  display: flex; align-items: center; justify-content: center;
}
.spin {
  width: 24px; height: 24px;
  border: 3px solid rgba(0, 113, 227, 0.25);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: away-rotate 0.9s linear infinite;
}
@keyframes away-rotate { to { transform: rotate(360deg); } }
.away-progress {
  height: 5px; background: var(--bg-alt); border-radius: 3px;
  overflow: hidden; margin-top: 22px;
}
.away-bar {
  height: 100%; background: var(--accent); border-radius: 3px;
  animation: away-shrink linear forwards;
}
@keyframes away-shrink { from { width: 100%; } to { width: 0%; } }
.away-group { margin-top: 22px; text-align: left; }
.away-group-title { margin-bottom: 10px; }
.away-links { display: flex; flex-direction: column; gap: 8px; }
.away-link {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  width: 100%; padding: 11px 16px;
  border: 1px solid var(--border);
  border-radius: 14px; background: var(--bg);
  cursor: pointer; font: inherit; transition: all .18s ease;
}
.away-link:hover { border-color: var(--accent); background: #f5f9ff; transform: translateY(-1px); }
.away-link.primary { border-color: rgba(0,113,227,.45); background: rgba(0,113,227,.06); }
.away-link.oversea { background: var(--bg-alt); }
.away-link-name { font-weight: 600; font-size: 14.5px; color: var(--text); }
.away-default {
  margin-left: 8px; font-size: 11px; font-weight: 700; color: #fff;
  background: var(--accent); border-radius: 8px; padding: 2px 8px; vertical-align: 1px;
}
.away-link-desc { font-size: 12.5px; color: var(--text-3); margin-top: 2px; }
.away-go { font-size: 13px; color: var(--accent); white-space: nowrap; font-weight: 600; }
@media (max-width: 560px) { .away-card { padding: 30px 20px; } }
</style>
