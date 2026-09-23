package com.recsys.service;

import java.net.HttpURLConnection;
import java.net.URL;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.recsys.client.AlgoServiceClient;
import com.recsys.entity.ItemEnrichment;
import com.recsys.repo.BookRepository;
import com.recsys.repo.ItemEnrichmentRepository;
import com.recsys.repo.MovieRepository;
import com.recsys.service.ItemService.ItemDTO;

/**
 * 资源富化服务：详情页首次打开时调用算法服务抓取（封面/简介/外链），
 * 结果缓存进 item_enrichment 表（后续访问零外呼）；管理后台手动编辑
 * （manual=true）不会被自动抓取覆盖；内置链接有效性定期抽查。
 */
@Service
public class EnrichmentService {

    private final AlgoServiceClient algo;
    private final ItemEnrichmentRepository repo;
    private final ItemService itemService;
    private final BookRepository books;
    private final MovieRepository movies;
    private final com.recsys.repo.CourseRepository courses;
    private final ObjectMapper mapper = new ObjectMapper();

    public EnrichmentService(AlgoServiceClient algo, ItemEnrichmentRepository repo,
                             ItemService itemService, BookRepository books,
                             MovieRepository movies, com.recsys.repo.CourseRepository courses) {
        this.algo = algo;
        this.repo = repo;
        this.itemService = itemService;
        this.books = books;
        this.movies = movies;
        this.courses = courses;
    }

    // ------------------------------------------------------------------
    // 详情富化（读）
    // ------------------------------------------------------------------
    public Map<String, Object> get(String domain, long itemId) {
        ItemEnrichment e = repo.findByDomainAndItemId(domain, itemId).orElse(null);
        boolean fromCache = e != null;
        if (e == null) {
            e = fetchAndCache(domain, itemId);
        }
        return assemble(e, fromCache);
    }

    /** 未命中缓存 -> 调算法服务抓取并落库（manual=false）；
     *  区域公版图书（books 负 ID）不走算法服务，本地合成富化 */
    private ItemEnrichment fetchAndCache(String domain, long itemId) {
        ItemEnrichment e = new ItemEnrichment(domain, itemId);
        if ("books".equals(domain) && itemId < 0) {
            ItemDTO dto = itemService.findForEnrich(domain, itemId);
            if (dto == null) {
                throw new IllegalArgumentException("物品不存在: " + domain + "/" + itemId);
            }
            e.setSummaryJson(worldSummary(dto));
            e.setLinksJson(worldLinks(dto));
            e.setSource("synthetic");
            e.setManual(false);
            e.setUpdatedAt(LocalDateTime.now());
            return repo.save(e);
        }
        try {
            JsonNode raw = mapper.readTree(algo.getEnrich(domain, itemId));
            JsonNode cover = raw.path("cover");
            if (!cover.isMissingNode() && cover.hasNonNull("url")) {
                e.setCoverUrl(cover.path("url").asText());
                e.setCoverWidth(cover.hasNonNull("width") ? cover.path("width").asInt() : null);
                e.setCoverHeight(cover.hasNonNull("height") ? cover.path("height").asInt() : null);
                e.setCoverSource(cover.path("source").asText(""));
            }
            e.setSummaryJson(mapper.writeValueAsString(Map.of(
                    "sections", raw.path("sections"),
                    "source", raw.path("source").asText("synthetic"))));
            e.setLinksJson(raw.path("links").toString());
            e.setSource(raw.path("source").asText("synthetic"));
        } catch (Exception ex) {
            // 抓取失败：仍生成一条基础记录（标题+元数据兜底），下次访问重试
            ItemDTO dto = itemService.findForEnrich(domain, itemId);
            if (dto == null) {
                throw new IllegalArgumentException("物品不存在: " + domain + "/" + itemId);
            }
            e.setSummaryJson(fallbackSummary(dto));
            e.setSource("synthetic");
        }
        e.setManual(false);
        e.setUpdatedAt(LocalDateTime.now());
        return repo.save(e);
    }

    private String fallbackSummary(ItemDTO dto) {
        try {
            ObjectNode root = mapper.createObjectNode();
            ArrayNode arr = root.putArray("sections");
            ObjectNode s1 = arr.addObject();
            s1.put("label", "基础信息");
            s1.put("text", dto.subtitle() + "｜" + dto.extra());
            ObjectNode s2 = arr.addObject();
            s2.put("label", "内容简介");
            s2.put("text", "外部数据源暂不可达，简介可在管理后台手动补充。");
            root.put("source", "synthetic");
            return mapper.writeValueAsString(root);
        } catch (Exception ex) {
            return "{\"sections\":[],\"source\":\"synthetic\"}";
        }
    }

    // ------------------------------------------------------------------
    // 区域公版图书（world_content 负 ID）本地合成富化
    // ------------------------------------------------------------------
    private String worldSummary(ItemDTO dto) {
        try {
            ObjectNode root = mapper.createObjectNode();
            ArrayNode arr = root.putArray("sections");
            ObjectNode s1 = arr.addObject();
            s1.put("label", "名著信息");
            s1.put("text", "区域：" + dto.badge() + "｜分类：" + dto.extra()
                    + (dto.recScore() != null ? "｜推荐指数：" + dto.recScore() + " / 10" : ""));
            ObjectNode s2 = arr.addObject();
            s2.put("label", "内容简介");
            s2.put("text", dto.note() == null || dto.note().isBlank()
                    ? "区域精选公版经典，完整简介可在管理后台补充。"
                    : dto.note());
            ObjectNode s3 = arr.addObject();
            s3.put("label", "推荐理由");
            s3.put("text", "该作为多区域内容库精选，其题材特征已进入系统统一兴趣画像，"
                    + "与你的跨域兴趣标签匹配时会被优先推荐。");
            root.put("source", "synthetic");
            return mapper.writeValueAsString(root);
        } catch (Exception ex) {
            return "{\"sections\":[],\"source\":\"synthetic\"}";
        }
    }

    /** 区域图书外链：国内站点优先（中文书名检索）+ 原始来源（Gutenberg 等，海外保留） */
    private String worldLinks(ItemDTO dto) {
        try {
            ArrayNode links = mapper.createArrayNode();
            String zh = dto.titleZh() != null ? dto.titleZh() : dto.title();
            String enc = java.net.URLEncoder.encode(zh,
                    java.nio.charset.StandardCharsets.UTF_8);
            ObjectNode d1 = links.addObject();
            d1.put("label", "豆瓣读书"); d1.put("type", "info");
            d1.put("url", "https://book.douban.com/subject_search?search_text=" + enc);
            ObjectNode d2 = links.addObject();
            d2.put("label", "微信读书 · 直达书页"); d2.put("type", "read");
            d2.put("url", "/api/weread?q=" + enc);
            ObjectNode d3 = links.addObject();
            d3.put("label", "京东图书"); d3.put("type", "buy");
            d3.put("url", "https://search.jd.com/Search?keyword=" + enc + "&enc=utf-8");
            ObjectNode d4 = links.addObject();
            d4.put("label", "当当图书"); d4.put("type", "buy");
            d4.put("url", "http://search.dangdang.com/?key=" + enc);
            if (dto.sourceUrl() != null && !dto.sourceUrl().isBlank()) {
                ObjectNode d5 = links.addObject();
                d5.put("label", "官方阅读页（海外）"); d5.put("type", "read");
                d5.put("url", dto.sourceUrl());
            }
            return mapper.writeValueAsString(links);
        } catch (Exception ex) {
            return "[]";
        }
    }

    private Map<String, Object> assemble(ItemEnrichment e, boolean fromCache) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("domain", e.getDomain());
        m.put("itemId", e.getItemId());
        if (e.getCoverUrl() != null) {
            Map<String, Object> c = new LinkedHashMap<>();
            c.put("url", e.getCoverUrl());
            c.put("width", e.getCoverWidth());
            c.put("height", e.getCoverHeight());
            c.put("source", e.getCoverSource());
            m.put("cover", c);
        } else {
            m.put("cover", null);
        }
        try {
            m.put("summary", mapper.readTree(e.getSummaryJson()));
        } catch (Exception ex) {
            m.put("summary", Map.of("sections", List.of(), "source", "synthetic"));
        }
        try {
            m.put("links", mapper.readTree(e.getLinksJson()));
        } catch (Exception ex) {
            m.put("links", List.of());
        }
        m.put("manual", e.isManual());
        m.put("cached", fromCache);
        m.put("updatedAt", e.getUpdatedAt() != null ? e.getUpdatedAt().toString() : null);
        return m;
    }

    // ------------------------------------------------------------------
    // 管理后台（手动编辑 / 列表 / 删除）
    // ------------------------------------------------------------------
    public Map<String, Object> page(String domain, int page, int size) {
        Page<ItemEnrichment> p = repo.findByDomainOrderByIdDesc(
                domain, PageRequest.of(Math.max(0, page), Math.min(Math.max(1, size), 50)));
        List<Map<String, Object>> rows = new ArrayList<>();
        p.getContent().forEach(e -> rows.add(Map.of(
                "domain", e.getDomain(), "itemId", e.getItemId(),
                "title", titleOf(e.getDomain(), e.getItemId()),
                "coverUrl", e.getCoverUrl() == null ? "" : e.getCoverUrl(),
                "source", e.getSource() == null ? "" : e.getSource(),
                "manual", e.isManual(),
                "checkOk", e.getCheckOk() == null ? "未检查" : String.valueOf(e.getCheckOk()),
                "updatedAt", e.getUpdatedAt() == null ? "" : e.getUpdatedAt().toString())));
        return Map.of("content", rows, "page", page, "totalElements", p.getTotalElements(),
                "totalPages", p.getTotalPages());
    }

    private String titleOf(String domain, long itemId) {
        ItemDTO dto = itemService.findForEnrich(domain, itemId);
        return dto == null ? ("#" + itemId) : dto.title();
    }

    /** 手动编辑（manual=true，不会被自动抓取覆盖） */
    public Map<String, Object> upsertManual(String domain, long itemId, String coverUrl,
                                            String summaryText, String recommendText,
                                            List<Map<String, String>> links) {
        ItemEnrichment e = repo.findByDomainAndItemId(domain, itemId).orElse(new ItemEnrichment(domain, itemId));
        if (coverUrl != null && !coverUrl.isBlank()) {
            e.setCoverUrl(coverUrl.trim());
            e.setCoverSource("admin");
        } else if (e.getCoverUrl() != null && e.getCoverSource() != null && "admin".equals(e.getCoverSource())) {
            e.setCoverUrl(null);
        }
        // 简介结构：保留原有其它段落，覆盖「内容简介」「推荐理由」两段
        try {
            ObjectNode root = (ObjectNode) mapper.readTree(
                    e.getSummaryJson() == null ? "{\"sections\":[]}" : e.getSummaryJson());
            ArrayNode sections = root.withArray("sections");
            for (int i = sections.size() - 1; i >= 0; i--) {
                String label = sections.get(i).path("label").asText();
                if ("内容简介".equals(label) || "推荐理由".equals(label)) {
                    sections.remove(i);
                }
            }
            if (summaryText != null && !summaryText.isBlank()) {
                ObjectNode s = sections.addObject();
                s.put("label", "内容简介");
                s.put("text", summaryText.trim());
            }
            if (recommendText != null && !recommendText.isBlank()) {
                ObjectNode s = sections.addObject();
                s.put("label", "推荐理由");
                s.put("text", recommendText.trim());
            }
            e.setSummaryJson(mapper.writeValueAsString(root));
        } catch (Exception ex) {
            e.setSummaryJson("{\"sections\":[],\"source\":\"admin\"}");
        }
        try {
            e.setLinksJson(mapper.writeValueAsString(links == null ? List.of() : links));
        } catch (Exception ex) {
            e.setLinksJson("[]");
        }
        e.setSource("admin");
        e.setManual(true);
        e.setUpdatedAt(LocalDateTime.now());
        repo.save(e);
        return assemble(e, false);
    }

    public void delete(String domain, long itemId) {
        repo.findByDomainAndItemId(domain, itemId).ifPresent(repo::delete);
    }

    // ------------------------------------------------------------------
    // 缺失封面报告
    // ------------------------------------------------------------------
    public Map<String, Object> missingCovers() {
        return Map.of(
                "books", Map.of("total", books.count(),
                        "missing", books.countMissingCovers(),
                        "note", "缺失/失效封面可在管理后台补充 URL"),
                "movies", Map.of("total", movies.count(),
                        "missing", movies.countMissingCovers(),
                        "note", "可运行 recommender/fetch_covers.py 批量预取 IMDb 海报"),
                "courses", Map.of("total", courses.count(), "missing", 0,
                        "note", "课程域使用类目矢量设计封面（平台无公开封面 API）"),
                "report", "recommender/reports_all/cover_audit.md");
    }

    // ------------------------------------------------------------------
    // 链接有效性定期检查（每日 04:30 抽查 + 管理端手动触发）
    // ------------------------------------------------------------------
    @Scheduled(cron = "0 30 4 * * *")
    public void scheduledCheck() {
        checkLinks(50);
    }

    /** 抽查 enrichment 记录的外部链接与图书封面 URL（HEAD，3s 超时） */
    public Map<String, Object> checkLinks(int limit) {
        int checked = 0, ok = 0;
        List<String> failures = new ArrayList<>();
        List<ItemEnrichment> all = repo.findAll();
        for (ItemEnrichment e : all) {
            if (checked >= limit) {
                break;
            }
            String url = null;
            if (e.getCoverUrl() != null && !e.getCoverUrl().isBlank()) {
                url = e.getCoverUrl();
            } else if (e.getLinksJson() != null && e.getLinksJson().length() > 4) {
                try {
                    JsonNode links = mapper.readTree(e.getLinksJson());
                    if (links.isArray() && links.size() > 0) {
                        url = links.get(0).path("url").asText(null);
                    }
                } catch (Exception ignored) {
                }
            }
            if (url == null) {
                continue;
            }
            checked++;
            boolean good = headOk(url);
            if (good) {
                ok++;
            } else {
                failures.add(e.getDomain() + "/" + e.getItemId() + " " + url);
            }
            e.setCheckedAt(LocalDateTime.now());
            e.setCheckOk(good);
            repo.save(e);
        }
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("checked", checked);
        r.put("ok", ok);
        r.put("failures", failures);
        r.put("note", "服务器网络受限（外网不可达）会误报失败；用户浏览器侧通常可正常访问。");
        return r;
    }

    private boolean headOk(String url) {
        try {
            HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setInstanceFollowRedirects(true);
            conn.setConnectTimeout(3000);
            conn.setReadTimeout(3000);
            conn.setRequestMethod("HEAD");
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (recsys-thesis-linkcheck)");
            int code = conn.getResponseCode();
            conn.disconnect();
            return code >= 200 && code < 400;
        } catch (Exception e) {
            return false;
        }
    }
}
