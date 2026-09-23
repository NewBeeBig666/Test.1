package com.recsys.controller;

import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.recsys.service.EnrichmentService;

/**
 * 资源富化接口：详情页打开时获取封面/简介/外部链接
 * （首次访问抓取并缓存 item_enrichment 表，响应含 cached 标记）。
 */
@RestController
@RequestMapping("/api/enrichment")
public class EnrichmentController {

    private final EnrichmentService enrichmentService;

    public EnrichmentController(EnrichmentService enrichmentService) {
        this.enrichmentService = enrichmentService;
    }

    @GetMapping("/{domain}/{itemId}")
    public ResponseEntity<Map<String, Object>> get(@PathVariable String domain,
                                                   @PathVariable long itemId) {
        return ResponseEntity.ok(enrichmentService.get(domain, itemId));
    }
}
