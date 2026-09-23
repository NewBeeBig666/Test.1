package com.recsys.controller;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.recsys.entity.WorldContent;
import com.recsys.repo.WorldContentRepository;
import com.recsys.service.ItemService;
import com.recsys.service.ItemService.ItemDTO;

/**
 * 环球精选（多区域内容库）：中国 / 日本 / 韩国 / 欧洲及其他世界区域。
 * 电影行关联 movie 表（详情抽屉/海报/评分推荐全联动）；图书为 Gutenberg 公版书。
 */
@RestController
@RequestMapping("/api/world")
public class WorldController {

    private static final Set<String> REGIONS = Set.of("中国", "日本", "韩国", "欧洲", "拉美", "世界其他");

    private final WorldContentRepository repo;
    private final ItemService itemService;

    public WorldController(WorldContentRepository repo, ItemService itemService) {
        this.repo = repo;
        this.itemService = itemService;
    }

    @GetMapping
    public Map<String, Object> list(@RequestParam(defaultValue = "movies") String domain,
                                    @RequestParam(required = false) String region,
                                    @RequestParam(defaultValue = "0") int page,
                                    @RequestParam(defaultValue = "12") int size) {
        if (region != null && !REGIONS.contains(region)) {
            throw new IllegalArgumentException("region 须为 " + REGIONS);
        }
        // 课程域：中国课程（course 表国内平台）；其他区域暂未收录
        if ("courses".equals(domain)) {
            return itemService.cnCourses(region, Math.max(0, page), size);
        }
        if (!Set.of("movies", "books").contains(domain)) {
            throw new IllegalArgumentException("domain 须为 movies|books|courses");
        }
        int p = Math.max(0, page), s = Math.min(Math.max(1, size), 48);
        Page<WorldContent> result = region == null || region.isBlank()
                ? repo.findByDomain(domain, PageRequest.of(p, s))
                : repo.findByDomainAndRegion(domain, region, PageRequest.of(p, s));

        List<Map<String, Object>> content = new ArrayList<>();
        for (WorldContent w : result.getContent()) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", w.getId());
            m.put("domain", w.getDomain());
            m.put("region", w.getRegion());
            m.put("title", w.getTitle());
            m.put("subtitle", w.getSubtitle());
            m.put("extra", w.getExtra());
            m.put("note", w.getNote());
            m.put("itemId", w.getItemId());
            m.put("sourceUrl", w.getSourceUrl());
            m.put("badge", w.getRegion());
            m.put("recScore", w.getRecScore());
            // 电影：关联 movie 表补充海报与中文名（详情抽屉与推荐系统联动）
            if ("movies".equals(w.getDomain()) && w.getItemId() != null) {
                ItemDTO dto = itemService.findForEnrich("movies", w.getItemId());
                if (dto != null) {
                    m.put("coverUrl", dto.coverUrl());
                    if (dto.titleZh() != null) m.put("titleZh", dto.titleZh());
                    if (dto.origTitle() != null) m.put("origTitle", dto.origTitle());
                    if (w.getRecScore() == null && dto.recScore() != null) {
                        m.put("recScore", dto.recScore());
                    }
                }
            } else {
                // 图书：从中文说明提取中文名 + 典藏封面
                if (w.getImageUrl() != null) {
                    m.put("imageUrl", w.getImageUrl());
                }
                String zh = itemService.zhFromNote(w.getNote());
                if (zh != null) {
                    m.put("titleZh", zh);
                }
            }
            content.add(m);
        }
        return Map.of("domain", domain, "region", region == null ? "" : region,
                "content", content, "page", p,
                "totalPages", result.getTotalPages(), "totalElements", result.getTotalElements());
    }

    /** 各区域内容计数（页面区域徽章） */
    @GetMapping("/stats")
    public Map<String, Object> stats() {
        Map<String, Object> r = new LinkedHashMap<>();
        for (String d : List.of("movies", "books")) {
            Map<String, Object> byRegion = new LinkedHashMap<>();
            for (String region : REGIONS) {
                long c = repo.countByDomainAndRegion(d, region);
                if (c > 0) {
                    byRegion.put(region, c);
                }
            }
            r.put(d, byRegion);
        }
        return r;
    }
}
