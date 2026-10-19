package com.recsys.controller;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.recsys.interceptor.UserIdHolder;
import com.recsys.service.ItemService;
import com.recsys.service.RecommendService;

/**
 * 首页聚合接口：三域（图书/课程/电影）推荐内容 + 跨域画像一次返回，
 * 将首页 7 次 API 往返合并为 1 次，服务端并行聚合，显著缩短首屏内容到达时间。
 *   全部模式（无 region）：每域 = 全球发现流 6 条 + 个性化推荐 6 条（前端交错展示）
 *   区域模式（region=中国/美国/日本…）：每域 = 区域精选 12 条（复用 /world 查询路由）
 * 画像对无行为数据的匿名游客返回 null（前端隐藏画像板块，不再触发失败请求）。
 */
@RestController
@RequestMapping("/api/home")
public class HomeController {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    /** 三域固定顺序输出（与首页栏目顺序一致） */
    private static final List<String> DOMAINS = List.of("books", "courses", "movies");

    private final RecommendService recommendService;
    private final ItemService itemService;
    private final WorldController world;

    public HomeController(RecommendService recommendService, ItemService itemService,
                          WorldController world) {
        this.recommendService = recommendService;
        this.itemService = itemService;
        this.world = world;
    }

    @GetMapping
    public Map<String, Object> home(@RequestParam(required = false) String region) {
        // ThreadLocal 会话：进入异步聚合前先取 userId
        long userId = UserIdHolder.require();
        boolean hasRegion = region != null && !region.isBlank();

        // 三域 + 跨域画像并行聚合（单域失败降级为空列表，不阻塞整体）
        Map<String, CompletableFuture<Object>> futures = new LinkedHashMap<>();
        for (String domain : DOMAINS) {
            futures.put(domain, CompletableFuture.supplyAsync(
                    () -> loadDomain(userId, domain, region, hasRegion)));
        }
        CompletableFuture<Object> profile = CompletableFuture.supplyAsync(() -> {
            try {
                return (Object) MAPPER.readTree(recommendService.globalProfile(userId));
            } catch (Exception e) {
                return null;  // 匿名游客无行为数据（算法侧 404）等场景
            }
        });

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("region", hasRegion ? region : "");
        Map<String, Object> domains = new LinkedHashMap<>();
        for (Map.Entry<String, CompletableFuture<Object>> e : futures.entrySet()) {
            domains.put(e.getKey(), e.getValue().join());
        }
        result.put("domains", domains);
        result.put("profile", profile.join());
        return result;
    }

    /** 单域内容：全部模式 = 发现流 + 个性化推荐；区域模式 = 区域精选（复用 /world 逻辑） */
    private Object loadDomain(long userId, String domain, String region, boolean hasRegion) {
        if (hasRegion) {
            return world.list(domain, region, null, 0, 12);
        }
        Map<String, Object> m = new LinkedHashMap<>();
        try {
            m.put("disco", itemService.search(domain, "", null, 0, 6).get("content"));
        } catch (Exception e) {
            m.put("disco", List.of());
        }
        try {
            JsonNode rec = recommendService.recommend(userId, domain, "ItemCF", 6);
            recommendService.enrichWithItems(rec, itemService);
            m.put("rec", rec.path("items"));
            m.put("cold", rec.path("cold_start").asBoolean(false));
        } catch (Exception e) {
            m.put("rec", List.of());
            m.put("cold", true);
        }
        return m;
    }
}
