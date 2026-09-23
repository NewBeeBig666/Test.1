package com.recsys.controller;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.recsys.interceptor.UserIdHolder;
import com.recsys.service.ItemService;
import com.recsys.service.RecommendService;

/**
 * 推荐相关接口：统一代理算法服务，推荐结果走 Redis 缓存。
 * 用户ID取自会话（注册用户或体验用户），不可伪造。
 */
@RestController
@RequestMapping("/api/rec")
public class RecommendController {

    private final RecommendService recommendService;
    private final ItemService itemService;

    public RecommendController(RecommendService recommendService, ItemService itemService) {
        this.recommendService = recommendService;
        this.itemService = itemService;
    }

    /**
     * Top-N 个性化推荐
     * algo: UserCF|ItemCF|ContentBased|CrossDomain|MostPopular
     * domain: books|courses|movies
     */
    @GetMapping(value = "/recommend", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> recommend(
            @RequestParam String domain,
            @RequestParam(defaultValue = "ItemCF") String algo,
            @RequestParam(defaultValue = "10", required = false) int n) {
        if (n < 1 || n > 50) {
            return ResponseEntity.badRequest().body("{\"error\":\"n 须在 1~50 之间\"}");
        }
        long userId = UserIdHolder.require();
        var resp = recommendService.recommend(userId, domain, algo, n);
        resp = recommendService.enrichWithItems(resp, itemService);
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_JSON)
                .body(resp.toString());
    }

    /** 单域用户画像（兴趣标签 + 属性标签） */
    @GetMapping("/profile")
    public ResponseEntity<String> profile(@RequestParam String domain) {
        long userId = UserIdHolder.require();
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_JSON)
                .body(recommendService.profile(userId, domain));
    }

    /** 跨域统一画像（三域兴趣融合，论文亮点） */
    @GetMapping("/profile/global")
    public ResponseEntity<String> globalProfile() {
        long userId = UserIdHolder.require();
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_JSON)
                .body(recommendService.globalProfile(userId));
    }

    /** 离线算法对比指标 */
    @GetMapping("/metrics")
    public ResponseEntity<String> metrics() {
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_JSON)
                .body(recommendService.metrics());
    }

    /** 可用算法列表 */
    @GetMapping("/algorithms")
    public ResponseEntity<String> algorithms() {
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_JSON)
                .body(recommendService.algorithms());
    }

    /** 手动触发算法服务重训（合并最新行为日志；评分事件后也会自动异步触发） */
    @org.springframework.web.bind.annotation.PostMapping("/reload")
    public ResponseEntity<String> reload() {
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_JSON)
                .body(recommendService.reload());
    }
}
