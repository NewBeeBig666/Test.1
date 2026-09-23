package com.recsys.service;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import com.recsys.entity.Book;
import com.recsys.entity.Course;
import com.recsys.entity.Movie;
import com.recsys.entity.WorldContent;
import com.recsys.repo.BookRepository;
import com.recsys.repo.CourseRepository;
import com.recsys.repo.MovieRepository;
import com.recsys.repo.WorldContentRepository;

/**
 * 统一物品检索：按 domain 路由三张物品表，返回统一 DTO，
 * 保证图书/课程/电影三模块一致的浏览与检索体验。
 *
 * 探索模式（默认浏览，无关键词/类目）：全球均衡展示
 *   - 均衡轮转注入：区域条目按池循环复用（用尽从头再取），与主目录按组交错
 *     （电影/图书 [区域×2+主目录×1]，课程 [中国×1+国际×5]），
 *     任意翻页深度下各地区展示比例恒定（电影/图书每页六区域各 2 条 + 主目录 6 条）
 *   - 以「日期+域」为种子随机打乱各池与主目录（当天稳定可翻页，每日轮换）
 */
@Service
public class ItemService {

    public static final Set<String> DOMAINS = Set.of("books", "courses", "movies");

    public record ItemDTO(long itemId, String domain, String title, String subtitle,
                         String extra, String imageUrl, String platform,
                         Double price, Long subscribers, String genres, String year,
                         String coverUrl, String sourceUrl, String badge, String note,
                         String titleZh, String origTitle, Double recScore) {

        public Map<String, Object> toMap() {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("itemId", itemId);
            m.put("domain", domain);
            m.put("title", title);
            if (titleZh != null) m.put("titleZh", titleZh);
            if (origTitle != null) m.put("origTitle", origTitle);
            m.put("subtitle", subtitle);
            m.put("extra", extra);
            if (imageUrl != null) m.put("imageUrl", imageUrl);
            if (platform != null) m.put("platform", platform);
            if (price != null) m.put("price", price);
            if (subscribers != null) m.put("subscribers", subscribers);
            if (genres != null) m.put("genres", genres);
            if (year != null) m.put("year", year);
            if (coverUrl != null) m.put("coverUrl", coverUrl);
            if (sourceUrl != null) m.put("sourceUrl", sourceUrl);
            if (badge != null) m.put("badge", badge);
            if (note != null) m.put("note", note);
            if (recScore != null) m.put("recScore", recScore);
            return m;
        }
    }

    /** 探索流缓存（每日重建）：顺序 + 区域电影徽章/说明 + 环球图书（负 ID 映射） */
    private record Discovery(String day, List<Long> order,
                             Map<Long, String> regionByItem,
                             Map<Long, WorldContent> worldBooks,
                             Map<Long, WorldContent> regionMovies) {}

    private final BookRepository books;
    private final CourseRepository courses;
    private final MovieRepository movies;
    private final WorldContentRepository world;
    private final Map<String, Discovery> discoCache = new HashMap<>();
    /** 中文译名词典（titles_zh.json：movies/books 热门译名 + orig 原语言名） */
    private final Map<String, Map<String, String>> zhDict;

    public ItemService(BookRepository books, CourseRepository courses, MovieRepository movies,
                       WorldContentRepository world) {
        this.books = books;
        this.courses = courses;
        this.movies = movies;
        this.world = world;
        this.zhDict = loadZhDict();
    }

    private Map<String, Map<String, String>> loadZhDict() {
        Map<String, Map<String, String>> dict = new HashMap<>();
        try (var in = new org.springframework.core.io.ClassPathResource("titles_zh.json")
                .getInputStream()) {
            Map<?, ?> root = new com.fasterxml.jackson.databind.ObjectMapper()
                    .readValue(in, Map.class);
            for (Map.Entry<?, ?> e : root.entrySet()) {
                if (!(e.getKey() instanceof String) || !(e.getValue() instanceof Map)) {
                    continue;
                }
                Map<String, String> inner = new HashMap<>();
                for (Map.Entry<?, ?> i : ((Map<?, ?>) e.getValue()).entrySet()) {
                    if (i.getKey() instanceof String k && i.getValue() instanceof String v) {
                        inner.put(k, v);
                    }
                }
                dict.put((String) e.getKey(), inner);
            }
        } catch (Exception ignored) {
            // 词典加载失败仅影响译名显示，不影响主流程
        }
        return dict;
    }

    /** 标题归一化：去年份/外文括注 + 冠词前移 + 清理未闭合括号，lowercase（词典匹配键） */
    private String titleKey(String title) {
        String t = title == null ? "" : title;
        t = t.replaceAll("\\s*\\([^)]*\\)", "").trim().toLowerCase();
        var m = java.util.regex.Pattern
                .compile("^(.*),\\s+(the|a|an|les|la|le|los|das|der|il|el)$").matcher(t);
        if (m.matches()) {
            t = m.group(2) + " " + m.group(1);
        }
        return t.replaceAll("[()]", " ").replaceAll("\\s+", " ").trim();
    }

    /** 中文译名：区域精选说明提取 > 词典（含冠词前缀双查） */
    private String zhOf(String domain, String title) {
        Map<String, String> dict = zhDict.get(domain);
        if (dict == null) {
            return null;
        }
        String key = titleKey(title);
        String v = dict.get(key);
        if (v == null) {
            v = dict.get("the " + key);
        }
        if (v == null) {
            v = dict.get("a " + key);
        }
        if (v == null) {
            // 副标题系列（"Star Wars: Episode IV - ..."）用主标题前缀再试一次
            int c = key.indexOf(':');
            if (c > 0) {
                String head = key.substring(0, c).trim();
                v = dict.get(head);
                if (v == null) {
                    v = dict.get("the " + head);
                }
            }
        }
        return v;
    }

    /** 原语言名（日/韩/中区域作品），无则 null（欧美原名即英文标题） */
    private String origOf(String titleZh) {
        if (titleZh == null) {
            return null;
        }
        Map<String, String> orig = zhDict.get("orig");
        return orig != null ? orig.get(titleZh) : null;
    }

    /** 区域精选中文说明 -> 作品中文名（"卧虎藏龙 · 李安武侠史诗" / "孔子《论语》英译本"） */
    public String zhFromNote(String note) {
        if (note == null || note.isBlank()) {
            return null;
        }
        var book = java.util.regex.Pattern.compile("《([^》]+)》").matcher(note);
        if (book.find()) {
            return book.group(1);
        }
        int i = note.indexOf(" · ");
        if (i > 0) {
            return note.substring(0, i).trim();
        }
        return null;
    }

    public Map<String, Object> search(String domain, String q, String category,
                                      int page, int size) {
        checkDomain(domain);
        page = Math.max(0, page);
        size = Math.min(Math.max(1, size), 48);
        String kw = q == null ? "" : q.trim();
        boolean hasCat = category != null && !category.isBlank();

        // 探索模式：默认浏览（无关键词、无类目）-> 全球多样 + 随机排列
        if (kw.isEmpty() && !hasCat) {
            return discoveryPage(domain, page, size);
        }

        var sort = Sort.by("itemId").ascending();
        Page<?> result = switch (domain) {
            case "books" -> books.findByTitleContainingOrAuthorContainingIgnoreCase(
                    kw, kw, PageRequest.of(page, size, sort));
            case "courses" -> searchCourses(kw, category, page, size, sort);
            default -> movies.findByTitleContainingIgnoreCase(
                    kw, PageRequest.of(page, size, sort));
        };
        return Map.of(
                "domain", domain,
                "content", result.map(this::toDTO).getContent(),
                "page", page,
                "totalPages", result.getTotalPages(),
                "totalElements", result.getTotalElements());
    }

    // ------------------------------------------------------------------
    // 探索模式：区域多样 + 随机排列（日种子）
    // ------------------------------------------------------------------
    private Discovery discovery(String domain) {
        String day = LocalDate.now().toString();
        Discovery cached = discoCache.get(domain);
        if (cached != null && cached.day().equals(day)) {
            return cached;
        }
        Random rnd = new Random((domain + "#" + day).hashCode());
        List<WorldContent> worldItems = world.findByDomainOrderById(domain);

        List<Long> region = new ArrayList<>();
        Map<Long, String> regionByItem = new HashMap<>();
        Map<Long, WorldContent> worldBooks = new HashMap<>();
        Map<Long, WorldContent> regionMovies = new HashMap<>();
        // 区域池：region -> 条目 ID 列表（电影=movie 表正 ID；图书=world_content 负 ID）
        Map<String, List<Long>> pools = new LinkedHashMap<>();
        if ("movies".equals(domain)) {
            for (WorldContent w : worldItems) {
                if (w.getItemId() != null) {
                    region.add(w.getItemId());
                    regionByItem.put(w.getItemId(), w.getRegion());
                    regionMovies.put(w.getItemId(), w);
                    pools.computeIfAbsent(w.getRegion(), k -> new ArrayList<>()).add(w.getItemId());
                }
            }
        } else if ("books".equals(domain)) {
            for (WorldContent w : worldItems) {
                region.add(-w.getId());  // 环球图书用负 ID（指向 world_content）
                worldBooks.put(w.getId(), w);
                pools.computeIfAbsent(w.getRegion(), k -> new ArrayList<>()).add(-w.getId());
            }
        } else {
            // 课程域：中国课程池（course 表国内平台条目）
            for (Course c : courses.findAll()) {
                if (isCnPlatform(c.getPlatform())) {
                    region.add(c.getItemId());
                    pools.computeIfAbsent("中国", k -> new ArrayList<>()).add(c.getItemId());
                }
            }
        }

        List<Long> main = switch (domain) {
            case "books" -> books.findAll().stream().map(Book::getItemId).collect(Collectors.toCollection(ArrayList::new));
            case "courses" -> courses.findAll().stream().map(Course::getItemId).collect(Collectors.toCollection(ArrayList::new));
            default -> movies.findAll().stream().map(Movie::getItemId).collect(Collectors.toCollection(ArrayList::new));
        };
        List<Long> regionSet = new ArrayList<>(region);
        main.removeAll(regionSet);  // 区域电影去重（图书负 ID 本就不冲突）
        Collections.shuffle(main, rnd);
        for (List<Long> p : pools.values()) {
            Collections.shuffle(p, rnd);
        }
        // 区域轮转次序（当日稳定、每日轮换，如 中国-欧洲-日本-拉美-韩国-世界其他）
        List<String> cycle = new ArrayList<>(pools.keySet());
        Collections.shuffle(cycle, rnd);

        // ------------------------------------------------------------------
        // 均衡轮转注入：每组 [区域×r, 主目录×u]，区域池循环复用（用尽从头再取），
        // 保证任意页、任意翻页深度下各地区展示比例恒定：
        //   电影/图书  [R R U]  -> 每页 12 区域（六区域各 2）+ 6 主目录
        //   课程      [R U×5]  -> 每页 3 中国课程 + 15 国际课程
        // ------------------------------------------------------------------
        int rPer = "courses".equals(domain) ? 1 : 2;
        int uPer = "courses".equals(domain) ? 5 : 1;
        List<Long> order = new ArrayList<>(main.size() / Math.max(uPer, 1) * (rPer + uPer) + rPer + 16);
        if (cycle.isEmpty()) {
            order.addAll(main);  // 防御：无区域数据时退化为纯主目录
        } else {
            int g = 0, u = 0;
            while (u < main.size()) {
                for (int k = 0; k < rPer; k++) {
                    String rg = cycle.get(g % cycle.size());
                    List<Long> pool = pools.get(rg);
                    order.add(pool.get((g / cycle.size()) % pool.size()));
                    g++;
                }
                for (int k = 0; k < uPer && u < main.size(); k++) {
                    order.add(main.get(u++));
                }
            }
        }
        Discovery d = new Discovery(day, order, regionByItem, worldBooks, regionMovies);
        discoCache.put(domain, d);
        return d;
    }

    private Map<String, Object> discoveryPage(String domain, int page, int size) {
        Discovery d = discovery(domain);
        List<Long> order = d.order();
        int from = Math.min(page * size, order.size());
        int to = Math.min(from + size, order.size());
        List<Object> content = new ArrayList<>();
        for (Long id : order.subList(from, to)) {
            ItemDTO dto = id < 0 ? worldBookDTO(d.worldBooks().get(-id))
                    : catalogDTO(domain, id, d.regionByItem().get(id));
            if (dto != null) {
                content.add(dto.toMap());
            }
        }
        return Map.of(
                "domain", domain,
                "content", content,
                "page", page,
                "totalPages", (order.size() + size - 1) / size,
                "totalElements", order.size());
    }

    /** 区域标注：区域精选按实际来源；主目录（英语图书/好莱坞/Udemy 平台）统一标注「美国」 */
    public String regionOf(String domain, long itemId) {
        if (domain == null || !DOMAINS.contains(domain) || itemId <= 0) {
            return null;
        }
        if ("courses".equals(domain)) {
            return "美国";  // Udemy 美国平台课程
        }
        Discovery d = discovery(domain);
        return d.regionByItem().getOrDefault(itemId, "美国");
    }

    /** 中国课程精选（course 表内国内平台课程；/world?domain=courses 联动） */
    public Map<String, Object> cnCourses(String region, int page, int size) {
        int p = Math.max(0, page), s = Math.min(Math.max(1, size), 48);
        if (!"中国".equals(region)) {
            return Map.of("domain", "courses", "region", region == null ? "" : region,
                    "content", List.of(), "page", p, "totalPages", 0, "totalElements", 0);
        }
        Page<Course> result = courses.findByPlatformNotIgnoreCase("Udemy",
                PageRequest.of(p, s, Sort.by("itemId").ascending()));
        return Map.of("domain", "courses", "region", "中国",
                "content", result.map(this::toDTO).getContent().stream()
                        .map(ItemDTO::toMap).collect(Collectors.toList()),
                "page", p, "totalPages", result.getTotalPages(),
                "totalElements", result.getTotalElements());
    }

    /** 中国课程平台（regionOf 判定：非 Udemy 平台均视为中国课程） */
    private static final Set<String> CN_COURSE_PLATFORMS = Set.of(
            "中国大学MOOC", "学堂在线", "网易公开课", "国家高等教育智慧教育平台",
            "国家中小学智慧教育平台", "终身教育平台");

    private boolean isCnPlatform(String platform) {
        return platform != null && (CN_COURSE_PLATFORMS.contains(platform)
                || !platform.equalsIgnoreCase("Udemy") && platform.codePoints().anyMatch(
                        cp -> Character.UnicodeScript.of(cp) == Character.UnicodeScript.HAN));
    }

    private ItemDTO worldBookDTO(WorldContent w) {
        if (w == null) {
            return null;
        }
        String titleZh = zhFromNote(w.getNote());
        return new ItemDTO(-w.getId(), "books", w.getTitle(), w.getSubtitle(),
                w.getExtra(), w.getImageUrl(), null, null, null, null, null, null,
                w.getSourceUrl(), w.getRegion(), w.getNote(), titleZh, origOf(titleZh),
                w.getRecScore());
    }

    private ItemDTO catalogDTO(String domain, long id, String badge) {
        // badge 已由 toDTO 统一注入（区域精选按来源，主目录标注「美国」）
        return findForEnrich(domain, id);
    }

    public Map<String, Object> detail(String domain, long itemId) {
        checkDomain(domain);
        // 区域公版图书（负 ID -> world_content）：统一抽屉详情（与其他作品交互一致）
        if ("books".equals(domain) && itemId < 0) {
            return world.findById(-itemId).map(w -> worldBookDTO(w).toMap())
                    .orElseThrow(() -> new ResponseStatusException(
                            HttpStatus.NOT_FOUND, "物品不存在"));
        }
        return switch (domain) {
            case "books" -> books.findById(itemId).map(b -> {
                        Map<String, Object> m = detailMap("books", b.getItemId(),
                                b.getTitle(), b.getAuthor(), b.getPublisher(), b.getImageUrl());
                        m.put("recScore", b.getRecScore());
                        return m;
                    })
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "物品不存在"));
            case "courses" -> courses.findById(itemId).map(c -> {
                        Map<String, Object> m = detailMap("courses", c.getItemId(), c.getTitle(),
                                c.getLevel(), c.getCategory(), null);
                        m.put("platform", c.getPlatform());
                        m.put("price", c.getPrice());
                        m.put("subscribers", c.getSubscribers());
                        m.put("sourceUrl", c.getSourceUrl());
                        m.put("recScore", c.getRecScore());
                        m.put("badge", isCnPlatform(c.getPlatform()) ? "中国" : "美国");
                        return m;
                    }).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "物品不存在"));
            default -> movies.findById(itemId).map(mv -> {
                        Map<String, Object> m = detailMap("movies", mv.getItemId(), mv.getTitle(),
                                mv.getGenres(), mv.getYear(), null);
                        m.put("genres", mv.getGenres());
                        m.put("year", mv.getYear());
                        m.put("coverUrl", mv.getPosterUrl());
                        m.put("recScore", mv.getRecScore());
                        return m;
                    }).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "物品不存在"));
        };
    }

    /** 推荐结果富化用：查询单个物品（不存在返回 null，不抛异常）；
     *  负 ID 为区域公版图书（world_content 条目，统一抽屉详情） */
    public ItemDTO findForEnrich(String domain, long itemId) {
        if (domain == null || !DOMAINS.contains(domain)) {
            return null;
        }
        if ("books".equals(domain) && itemId < 0) {
            return world.findById(-itemId).map(this::worldBookDTO).orElse(null);
        }
        return switch (domain) {
            case "books" -> books.findById(itemId).map(this::toDTO).orElse(null);
            case "courses" -> courses.findById(itemId).map(this::toDTO).orElse(null);
            default -> movies.findById(itemId).map(this::toDTO).orElse(null);
        };
    }

    private Page<Course> searchCourses(String kw, String category, int page, int size, Sort sort) {
        var pageable = PageRequest.of(page, size, sort);
        boolean hasCat = category != null && !category.isBlank();
        if (!kw.isEmpty() && hasCat) {
            return courses.findByTitleContainingIgnoreCaseAndCategoryIgnoreCase(kw, category, pageable);
        }
        if (hasCat) {
            return courses.findByCategoryIgnoreCase(category, pageable);
        }
        return courses.findByTitleContainingIgnoreCase(kw, pageable);
    }

    /** 统一构造 DTO：全部物品携带区域标签、中文名与推荐指数（区域精选按来源，主目录标注「美国」；
     *  双语显示：titleZh=中文名，origTitle=原语言名（日韩中区域作品）） */
    private ItemDTO toDTO(Object entity) {
        if (entity instanceof Book b) {
            String zh = zhOf("books", b.getTitle());
            return new ItemDTO(b.getItemId(), "books", b.getTitle(), b.getAuthor(),
                    b.getPublisher(), b.getImageUrl(), null, null, null, null, null, null, null,
                    regionOf("books", b.getItemId()), null, zh, origOf(zh), b.getRecScore());
        }
        if (entity instanceof Course c) {
            return new ItemDTO(c.getItemId(), "courses", c.getTitle(), c.getLevel(),
                    c.getCategory(), null, c.getPlatform(), c.getPrice(),
                    c.getSubscribers(), null, null, c.getPosterUrl(), c.getSourceUrl(),
                    isCnPlatform(c.getPlatform()) ? "中国" : "美国", null, null, null,
                    c.getRecScore());
        }
        Movie m = (Movie) entity;
        // 区域电影优先取精选中文说明，其次词典译名
        WorldContent wc = discovery("movies").regionMovies().get(m.getItemId());
        String zh = wc != null ? zhFromNote(wc.getNote()) : zhOf("movies", m.getTitle());
        return new ItemDTO(m.getItemId(), "movies", m.getTitle(), m.getGenres(),
                m.getYear(), null, null, null, null, m.getGenres(), m.getYear(),
                m.getPosterUrl(), null, regionOf("movies", m.getItemId()), null, zh,
                origOf(zh), m.getRecScore());
    }

    private Map<String, Object> detailMap(String domain, long itemId, String title,
                                          String subtitle, String extra, String imageUrl) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("itemId", itemId);
        m.put("domain", domain);
        m.put("title", title);
        m.put("subtitle", subtitle);
        m.put("extra", extra);
        if (imageUrl != null) {
            m.put("imageUrl", imageUrl);
        }
        return m;
    }

    private void checkDomain(String domain) {
        if (domain == null || !DOMAINS.contains(domain)) {
            throw new IllegalArgumentException("domain 须为 books|courses|movies");
        }
    }
}
