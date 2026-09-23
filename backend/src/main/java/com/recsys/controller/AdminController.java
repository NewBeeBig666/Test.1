package com.recsys.controller;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.recsys.service.EnrichmentService;

/**
 * 后台管理接口（/api/admin/**，需管理员账号——用户名 admin，见 AuthInterceptor）：
 *   GET    /api/admin/enrichments?domain=&page=&size=   富化记录分页列表
 *   PUT    /api/admin/enrichment                        手动编辑（manual=true，不被自动抓取覆盖）
 *   DELETE /api/admin/enrichment/{domain}/{itemId}      删除（下次访问重新抓取）
 *   GET    /api/admin/missing-covers                   缺失封面扫描报告
 *   POST   /api/admin/link-check?limit=50              链接有效性检查（另有每日 04:30 定时抽查）
 */
@RestController
@RequestMapping("/api/admin")
public class AdminController {

    private final EnrichmentService enrichment;

    public AdminController(EnrichmentService enrichment) {
        this.enrichment = enrichment;
    }

    @GetMapping("/enrichments")
    public Map<String, Object> list(@RequestParam(defaultValue = "books") String domain,
                                    @RequestParam(defaultValue = "0") int page,
                                    @RequestParam(defaultValue = "12") int size) {
        return enrichment.page(domain, page, size);
    }

    public record ManualEdit(String domain, Long itemId, String coverUrl,
                             String summaryText, String recommendText,
                             List<Map<String, String>> links) {}

    @PutMapping("/enrichment")
    public Map<String, Object> edit(@RequestBody ManualEdit req) {
        if (req.domain() == null || req.itemId() == null) {
            throw new IllegalArgumentException("domain/itemId 不能为空");
        }
        return enrichment.upsertManual(req.domain(), req.itemId(), req.coverUrl(),
                req.summaryText(), req.recommendText(), req.links());
    }

    @DeleteMapping("/enrichment/{domain}/{itemId}")
    public Map<String, Object> delete(@PathVariable String domain, @PathVariable long itemId) {
        enrichment.delete(domain, itemId);
        return Map.of("status", "deleted");
    }

    @GetMapping("/missing-covers")
    public Map<String, Object> missingCovers() {
        return enrichment.missingCovers();
    }

    @PostMapping("/link-check")
    public Map<String, Object> linkCheck(@RequestParam(defaultValue = "50") int limit) {
        return enrichment.checkLinks(Math.min(Math.max(1, limit), 200));
    }
}
