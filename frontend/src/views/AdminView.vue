<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

const domains = ['books', 'courses', 'movies']
const DOMAIN_LABEL = { books: '图书', courses: '课程', movies: '电影' }

const activeDomain = ref('movies')
const page = ref(0)
const rows = ref([])
const total = ref(0)
const loading = ref(false)

const missing = ref(null)
const linkResult = ref(null)
const checking = ref(false)

const edit = reactive({ visible: false, domain: '', itemId: 0, title: '', coverUrl: '', summaryText: '', recommendText: '', links: [{ label: '', url: '', type: 'info' }] })

const load = async (p = 0) => {
  loading.value = true
  page.value = p
  try {
    const r = await request.get('/admin/enrichments', { params: { domain: activeDomain.value, page: p, size: 12 } })
    rows.value = r.content || []
    total.value = r.totalElements || 0
  } finally {
    loading.value = false
  }
}

const openEdit = (row) => {
  Object.assign(edit, {
    visible: true, domain: row.domain, itemId: row.itemId, title: row.title,
    coverUrl: row.coverUrl || '', summaryText: '', recommendText: '',
    links: [{ label: '', url: '', type: 'info' }],
  })
}

const save = async () => {
  try {
    await request.put('/admin/enrichment', {
      domain: edit.domain, itemId: edit.itemId, coverUrl: edit.coverUrl,
      summaryText: edit.summaryText, recommendText: edit.recommendText,
      links: edit.links.filter(l => l.label && l.url).map(l => ({ ...l })),
    })
    ElMessage.success('已保存（manual=true，不会被自动抓取覆盖）')
    edit.visible = false
    load(page.value)
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  }
}

const remove = async (row) => {
  await request.delete(`/admin/enrichment/${row.domain}/${row.itemId}`)
  ElMessage.success('已删除，下次访问将重新抓取')
  load(page.value)
}

const runCheck = async () => {
  checking.value = true
  try {
    linkResult.value = await request.post('/admin/link-check', null, { params: { limit: 50 } })
  } finally {
    checking.value = false
  }
}

const fmt = (t) => (t || '').replace('T', ' ').slice(5, 16)

onMounted(() => {
  load(0)
  request.get('/admin/missing-covers').then(r => { missing.value = r }).catch(() => {})
})
</script>

<template>
  <div>
    <section class="section-alt" style="padding: clamp(38px, 5vw, 60px) 0 24px">
      <div class="container">
        <div class="section-eyebrow">Admin Console</div>
        <h1 class="section-title" style="margin: 6px 0 8px">后台管理</h1>
        <p class="text-2">封面图片、内容简介与外部链接的手动编辑与更新；数据质量与链接有效性监控。</p>

        <!-- 缺失封面 / 链接检查 -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 18px; margin-top: 24px">
          <div class="card" style="padding: 22px">
            <div style="font-weight: 700; margin-bottom: 10px">封面覆盖扫描</div>
            <template v-if="missing">
              <div v-for="(v, d) in missing" :key="d" v-show="d !== 'report'" style="display: flex; justify-content: space-between; padding: 6px 0; align-items: center">
                <span>{{ DOMAIN_LABEL[d] || d }}</span>
                <span class="text-2">{{ v.missing }} / {{ v.total }} 缺失</span>
              </div>
              <p class="note" style="margin-top: 8px">电影海报可运行 recommender/fetch_covers.py 自动补充（IMDb 源，含分辨率审核）。</p>
            </template>
          </div>
          <div class="card" style="padding: 22px">
            <div style="font-weight: 700; margin-bottom: 10px">链接有效性检查</div>
            <button class="btn" :disabled="checking" @click="runCheck">{{ checking ? '检查中…' : '立即抽查 50 条' }}</button>
            <template v-if="linkResult">
              <p style="margin-top: 12px">
                可访问 <strong style="color: var(--courses)">{{ linkResult.ok }}</strong> /
                {{ linkResult.checked }} 条
              </p>
              <p class="note" style="margin-top: 6px">{{ linkResult.note }}</p>
              <div v-if="linkResult.failures.length" class="note" style="margin-top: 6px; max-height: 90px; overflow: auto">
                <div v-for="f in linkResult.failures" :key="f">⚠ {{ f }}</div>
              </div>
            </template>
            <p class="note" style="margin-top: 10px">系统每日 04:30 自动抽查（记录 checked_at / check_ok），结果标注在下方列表。</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 富化记录管理 -->
    <section class="section" style="padding-top: 20px">
      <div class="container">
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
          <button v-for="d in domains" :key="d" class="chip chip-lg" :class="{ active: activeDomain === d }"
                  style="cursor: pointer; border: none" @click="activeDomain = d; load(0)">
            {{ DOMAIN_LABEL[d] }}
          </button>
          <span class="note" style="margin-left: auto">共 {{ total }} 条富化记录（详情页首次访问自动生成）</span>
        </div>

        <div v-loading="loading" class="card" style="margin-top: 18px; overflow-x: auto">
          <table class="data-table">
            <thead>
              <tr><th>物品</th><th>封面</th><th>来源</th><th>人工</th><th>链接检查</th><th>更新时间</th><th>操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in rows" :key="r.domain + r.itemId">
                <td>
                  <div style="font-weight: 600">{{ r.title }}</div>
                  <div class="note">#{{ r.itemId }}</div>
                </td>
                <td>
                  <span v-if="r.coverUrl" class="chip chip-c">有</span>
                  <span v-else class="chip">缺</span>
                </td>
                <td>{{ { openlibrary: 'OpenLibrary', imdb: 'IMDb', synthetic: '系统生成', admin: '管理员' }[r.source] || r.source || '—' }}</td>
                <td>{{ r.manual ? '✔' : '—' }}</td>
                <td>
                  <span v-if="r.checkOk === 'true'" class="chip chip-c">正常</span>
                  <span v-else-if="r.checkOk === 'false'" class="chip">异常</span>
                  <span v-else class="chip">未检查</span>
                </td>
                <td class="text-3">{{ fmt(r.updatedAt) }}</td>
                <td>
                  <a href="#" @click.prevent="openEdit(r)" style="margin-right: 12px">编辑</a>
                  <a href="#" style="color: #c00" @click.prevent="remove(r)">删除</a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="display: flex; justify-content: center; margin-top: 22px">
          <el-pagination v-if="total > 12" background layout="prev, pager, next" :total="total"
                         :page-size="12" :current-page="page + 1" @current-change="(p) => load(p - 1)" />
        </div>
      </div>
    </section>

    <!-- 编辑对话框 -->
    <el-dialog v-model="edit.visible" :title="`编辑 · ${DOMAIN_LABEL[edit.domain] || ''} #${edit.itemId} ${edit.title}`" width="560px">
      <div style="display: flex; flex-direction: column; gap: 16px">
        <div>
          <div style="font-weight: 600; margin-bottom: 6px">封面图片 URL</div>
          <el-input v-model="edit.coverUrl" placeholder="https://... （留空保持现有封面）" />
        </div>
        <div>
          <div style="font-weight: 600; margin-bottom: 6px">内容简介</div>
          <el-input v-model="edit.summaryText" type="textarea" :rows="4" placeholder="详细内容简介（覆盖「内容简介」段落）" />
        </div>
        <div>
          <div style="font-weight: 600; margin-bottom: 6px">推荐理由</div>
          <el-input v-model="edit.recommendText" type="textarea" :rows="2" placeholder="推荐给用户的理由（覆盖「推荐理由」段落）" />
        </div>
        <div>
          <div style="font-weight: 600; margin-bottom: 6px">外部链接</div>
          <div v-for="(l, i) in edit.links" :key="i" style="display: flex; gap: 8px; margin-bottom: 8px">
            <el-input v-model="l.label" placeholder="名称（如 官方详情页）" style="flex: 1" />
            <el-input v-model="l.url" placeholder="https://..." style="flex: 1.6" />
            <el-button @click="edit.links.splice(i, 1)">删</el-button>
          </div>
          <el-button size="small" @click="edit.links.push({ label: '', url: '', type: 'info' })">+ 添加链接</el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="edit.visible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
