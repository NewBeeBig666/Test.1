import { onBeforeUnmount } from 'vue'
import request from '@/api/request'

/**
 * 用户行为埋点（三域通用）：
 *   view     卡片进入视口（IntersectionObserver，每物品仅一次）
 *   click    打开物品详情
 *   rating   提交评分（1-5 星）
 *   favorite 收藏
 */
export function useTrack(domain) {
  const tracked = new Set()
  let observer = null

  const track = async (eventType, itemId, rating = null) => {
    try {
      await request.post('/event', { itemId, domain, eventType, rating })
    } catch (e) {
      /* 埋点失败静默处理，不影响主流程 */
    }
  }

  /** 观察元素进入视口 -> view 埋点（每物品一次） */
  const observeView = (el, itemId) => {
    const key = `${domain}:${itemId}`
    if (!el || tracked.has(key)) return
    observer = observer || new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const id = Number(entry.target.dataset.itemId)
            const k = `${domain}:${id}`
            if (!tracked.has(k)) {
              tracked.add(k)
              track('view', id)
            }
            observer.unobserve(entry.target)
          }
        }
      },
      { threshold: 0.5 },
    )
    observer.observe(el)
  }

  onBeforeUnmount(() => observer?.disconnect())

  return { track, observeView }
}
