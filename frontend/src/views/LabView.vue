<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

const ALGOS = ['UserCF', 'ItemCF', 'ContentBased', 'CrossDomain', 'MostPopular']
const ALGO_DESC = {
  UserCF: '基于用户的协同过滤：Top-K 余弦近邻用户的行为加权推荐',
  ItemCF: '基于物品的协同过滤：与你交互过的物品最相似的物品',
  ContentBased: '基于内容推荐：物品 TF-IDF 向量与用户兴趣画像的余弦匹配',
  CrossDomain: '跨域推荐（亮点）：三域统一 TF-IDF 空间，用你在其他领域的行为推荐本域',
  MostPopular: '热门基线：全局交互量排序（冷启动兜底 / 实验下界参照）',
}

/* ---------------- 离线对比实验 ---------------- */
const metricsRows = ref([])
const metricsFile = ref('')
const showMetric = ref('NDCG@K')
/* CSV 列名为字面 "Precision@K" 等（K=10），key 为数据列名，label 为展示名 */
const METRICS = [
  { key: 'Precision@K', label: 'Precision@10' },
  { key: 'Recall@K', label: 'Recall@10' },
  { key: 'HitRate@K', label: 'HitRate@10' },
  { key: 'NDCG@K', label: 'NDCG@10' },
]
const DOMAIN_LABEL = { books: '图书', courses: '课程', movies: '电影' }

const bestOf = (metric) => {
  if (!metricsRows.value.length) return null
  return Math.max(...metricsRows.value.map((r) => Number(r[metric]) || 0))
}

const barData = computed(() => ({
  metric: showMetric.value,
  rows: metricsRows.value.map((r) => ({
    label: `${DOMAIN_LABEL[r.domain] || r.domain} · ${r.algorithm}`,
    value: Number(r[showMetric.value]) || 0,
  })),
}))
const barMax = computed(() => Math.max(0.0001, ...barData.value.rows.map((r) => r.value)))

/* ---------------- 在线 A/B 实验 ---------------- */
const ab = reactive({
  domain: 'books',
  algoA: 'ItemCF',
  algoB: 'UserCF',
  n: 10,
  loading: false,
  resultA: null,
  resultB: null,
})

const runAb = async () => {
  ab.loading = true
  const fetch = (algo) => request.get('/rec/recommend', { params: { domain: ab.domain, algo, n: ab.n } })
    .catch(() => null)
  ;[ab.resultA, ab.resultB] = await Promise.all([fetch(ab.algoA), fetch(ab.algoB)])
  ab.loading = false
}

/* ---------------- 跨域演示 ---------------- */
const xd = reactive({ target: 'movies', loading: false, result: null })
const runCross = async () => {
  xd.loading = true
  try {
    xd.result = await request.get('/rec/recommend', { params: { domain: xd.target, algo: 'CrossDomain', n: 10 } })
  } finally {
    xd.loading = false
  }
}

const retraining = ref(false)
const retrain = async () => {
  retraining.value = true
  try {
    await request.post('/rec/reload')
    ElMessage.success('三域模型已重训完成')
  } catch (e) {
    ElMessage.error('重训失败：' + (e.response?.data?.error || '算法服务不可用'))
  } finally {
    retraining.value = false
  }
}

onMounted(async () => {
  try {
    const r = await request.get('/rec/metrics')
    metricsRows.value = r.rows || []
    metricsFile.value = r.metrics_file || ''
  } catch (e) { /* 尚未生成评估报告 */ }
  runAb()
  runCross()
})
</script>

<template>
  <div>
    <!-- ================= 离线对比实验 ================= -->
    <section class="section-alt" style="padding: clamp(38px, 5vw, 60px) 0 28px">
      <div class="container">
        <div class="section-eyebrow">Evaluation</div>
        <h1 class="section-title" style="margin: 6px 0 8px">算法对比实验</h1>
        <p class="text-2">三域 × 多算法的离线评估（evaluate.py 产出，测试集 20%，正反馈 rating_norm ≥ 0.7）。</p>
        <p class="note" style="margin-top: 6px">指标文件：{{ metricsFile || '未找到（先运行 recommender/evaluate_all.py）' }}</p>

        <div v-if="metricsRows.length" style="margin-top: 26px; overflow-x: auto">
          <table class="data-table">
            <thead>
              <tr>
                <th>领域</th><th>算法</th>
                <th v-for="m in METRICS" :key="m.key">{{ m.label }}</th><th>Coverage</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in metricsRows" :key="r.domain + r.algorithm">
                <td><span class="chip" :class="{ books: 'chip-d', courses: 'chip-c', movies: 'chip-m' }[r.domain]">{{ DOMAIN_LABEL[r.domain] }}</span></td>
                <td style="font-weight: 600">{{ r.algorithm }}</td>
                <td v-for="m in METRICS" :key="m.key" :class="{ best: Number(r[m.key]) === bestOf(m.key) }">
                  {{ (Number(r[m.key]) || 0).toFixed(4) }}
                </td>
                <td>{{ ((Number(r['Coverage']) || 0) * 100).toFixed(1) }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
        <el-alert v-else type="warning" :closable="false" style="margin-top: 26px; border-radius: 14px">
          尚未生成评估报告：在 recommender 目录运行 <code>py -3 evaluate_all.py</code> 后刷新本页。
        </el-alert>

        <div v-if="metricsRows.length" style="margin-top: 34px">
          <div style="display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap">
            <button v-for="m in METRICS" :key="m.key" class="chip chip-lg" :class="{ active: showMetric === m.key }"
                    style="cursor: pointer; border: none" @click="showMetric = m.key">{{ m.label }}</button>
          </div>
          <div class="card" style="padding: 26px 30px">
            <div v-for="row in barData.rows" :key="row.label" style="margin-bottom: 12px">
              <div style="display: flex; justify-content: space-between; font-size: 13.5px; margin-bottom: 4px">
                <span>{{ row.label }}</span>
                <span class="text-3">{{ row.value.toFixed(4) }}</span>
              </div>
              <div style="height: 8px; background: var(--bg-alt); border-radius: 4px; overflow: hidden">
                <div :style="{
                  width: (row.value / barMax * 100) + '%',
                  height: '100%',
                  background: 'var(--accent)',
                  borderRadius: '4px',
                  transition: 'width 0.6s var(--ease)',
                }" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ================= 在线 A/B ================= -->
    <section class="section" style="padding-top: 40px">
      <div class="container">
        <div class="section-eyebrow">Live A/B</div>
        <h2 class="section-title" style="font-size: 34px; margin: 6px 0 8px">在线双算法对比</h2>
        <p class="text-2">同一用户、同一领域，两种算法的实时推荐对比（含缓存命中与延迟观测）。</p>

        <div style="display: flex; gap: 12px; margin-top: 24px; flex-wrap: wrap; align-items: center">
          <el-select v-model="ab.domain" style="width: 110px" size="large">
            <el-option v-for="(l, d) in DOMAIN_LABEL" :key="d" :label="l" :value="d" />
          </el-select>
          <el-select v-model="ab.algoA" style="width: 180px" size="large">
            <el-option v-for="a in ALGOS" :key="a" :label="'A: ' + a" :value="a" />
          </el-select>
          <span class="text-3" style="font-weight: 600">VS</span>
          <el-select v-model="ab.algoB" style="width: 180px" size="large">
            <el-option v-for="a in ALGOS" :key="a" :label="'B: ' + a" :value="a" />
          </el-select>
          <el-select v-model="ab.n" style="width: 100px" size="large">
            <el-option :value="5" label="Top 5" /><el-option :value="10" label="Top 10" /><el-option :value="20" label="Top 20" />
          </el-select>
          <button class="btn" :disabled="ab.loading" @click="runAb">{{ ab.loading ? '对比中…' : '开始对比' }}</button>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 22px; margin-top: 26px">
          <div v-for="(res, idx) in [ab.resultA, ab.resultB]" :key="idx" class="card" style="padding: 22px 24px">
            <template v-if="res">
              <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px">
                <strong style="font-size: 17px">{{ idx === 0 ? ab.algoA : ab.algoB }}</strong>
                <span style="display: flex; gap: 6px; flex-wrap: wrap">
                  <span class="chip">{{ res.latency_ms }} ms</span>
                  <span class="chip" :class="{ 'chip-c': res.fromCache }">{{ res.fromCache ? '缓存命中' : '实时计算' }}</span>
                  <span v-if="res.cold_start" class="chip">冷启动</span>
                </span>
              </div>
              <p class="note" style="margin: 6px 0 14px">{{ ALGO_DESC[idx === 0 ? ab.algoA : ab.algoB] }}</p>
              <div style="display: flex; flex-direction: column; gap: 9px">
                <div v-for="(it, i) in (res.items || []).slice(0, 10)" :key="it.item_id"
                     style="display: flex; gap: 10px; align-items: baseline">
                  <span class="text-3" style="font-variant-numeric: tabular-nums; width: 20px">{{ i + 1 }}</span>
                  <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14.5px">{{ it.title }}</span>
                  <span class="item-score">{{ it.score.toFixed(3) }}</span>
                </div>
              </div>
            </template>
            <p v-else class="text-3">点击「开始对比」</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ================= 跨域演示 ================= -->
    <section class="section section-alt" style="padding-top: 40px">
      <div class="container">
        <div class="section-eyebrow" style="color: var(--books)">Highlight</div>
        <h2 class="section-title" style="font-size: 34px; margin: 6px 0 8px">跨域推荐演示</h2>
        <p class="text-2">
          系统把三个领域的物品投影到<strong>统一 TF-IDF 标签空间</strong>——你在图书/课程领域的行为，
          可以直接用来推荐电影（反之亦然）。这是本系统区别于普通单域推荐系统的核心亮点。
        </p>

        <div style="display: flex; gap: 12px; margin-top: 24px; flex-wrap: wrap; align-items: center">
          <span class="text-2">用我在所有领域的行为，推荐</span>
          <el-select v-model="xd.target" style="width: 110px" size="large">
            <el-option v-for="(l, d) in DOMAIN_LABEL" :key="d" :label="l" :value="d" />
          </el-select>
          <button class="btn" :disabled="xd.loading" @click="runCross">{{ xd.loading ? '推荐中…' : '生成跨域推荐' }}</button>
          <button class="btn btn-ghost" :disabled="retraining" @click="retrain" style="margin-left: auto">
            {{ retraining ? '模型重训中…' : '手动重训模型' }}
          </button>
        </div>

        <div v-if="xd.result" class="card" style="margin-top: 22px; padding: 24px 28px">
          <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 14px">
            <span class="chip chip-m">CrossDomain → {{ DOMAIN_LABEL[xd.target] }}</span>
            <span class="chip">{{ xd.result.latency_ms }} ms</span>
            <span v-if="xd.result.cold_start" class="chip">冷启动（暂用热门兜底）</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 9px">
            <div v-for="(it, i) in (xd.result.items || []).slice(0, 10)" :key="it.item_id"
                 style="display: flex; gap: 10px; align-items: baseline">
              <span class="text-3" style="font-variant-numeric: tabular-nums; width: 20px">{{ i + 1 }}</span>
              <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ it.title }}</span>
              <span class="note">{{ it.subtitle }}</span>
              <span class="item-score">{{ it.score.toFixed(3) }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
