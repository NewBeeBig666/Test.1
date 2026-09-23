<script setup>
import { useRoute } from 'vue-router'
import AppNavbar from '@/components/AppNavbar.vue'

const route = useRoute()
</script>

<template>
  <AppNavbar />
  <main style="padding-top: var(--nav-h)">
    <!-- :key 强制路由复用组件重建（图书/课程/电影共用 DomainView，切换时数据/URL/状态同步刷新） -->
    <router-view v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" :key="route.path" />
      </transition>
    </router-view>
  </main>
  <footer class="section-alt" style="padding: 18px 0; border-top: 1px solid var(--border)">
    <div class="container note" style="display: flex; flex-wrap: wrap; gap: 8px 24px; justify-content: space-between">
      <span>智荐 · 基于推荐算法的个性化系统（图书 / 课程 / 电影）</span>
      <span>SpringBoot + FastAPI + MySQL + Redis · Vue 3 + Element Plus</span>
    </div>
  </footer>
</template>
