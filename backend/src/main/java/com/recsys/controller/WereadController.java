package com.recsys.controller;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 微信读书搜索跳转代理（乱码修复）。
 *
 * 背景：微信读书网页版没有公开的搜索结果页路由，其
 * /web/search/global?keyword= 是 XHR 数据接口——直接在浏览器打开会
 * 渲染原始 JSON，且接口无 charset 声明，国产双核浏览器默认 GBK 解码
 * UTF-8 字节产生中文乱码。
 *
 * 修复：本端点在服务端完成检索（UTF-8 显式解码，与浏览器编码无关），
 * 解析首个结果的 deepLink（书籍详情页，正常 HTML 页面），302 重定向直达。
 * 无结果/网络异常时回退微信读书主页。关键词经标准 RFC 3986 percent-encoding
 * 传递，对 Chrome/Firefox/Safari/国产浏览器行为一致。
 */
@RestController
@RequestMapping("/api/weread")
public class WereadController {

    private static final String SEARCH = "https://weread.qq.com/web/search/global?keyword=";
    private static final String HOME = "https://weread.qq.com/";
    /** 书名 -> deepLink 结果缓存（当日会话内避免重复外呼） */
    private static final Map<String, String> CACHE = new ConcurrentHashMap<>();

    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(4))
            .followRedirects(HttpClient.Redirect.NORMAL)
            .build();
    private final ObjectMapper mapper = new ObjectMapper();

    @GetMapping
    public ResponseEntity<Void> search(@RequestParam(defaultValue = "") String q) {
        String kw = q == null ? "" : q.trim();
        if (kw.isEmpty()) {
            return redirect(HOME);
        }
        String deep = CACHE.computeIfAbsent(kw, this::lookup);
        if (CACHE.size() > 4096) {
            CACHE.clear();  // 毕设规模简单容量控制
        }
        return redirect(deep);
    }

    /** 服务端检索书籍详情页链接（UTF-8 显式解码）；失败/无结果回退主页 */
    private String lookup(String kw) {
        try {
            String url = SEARCH + URLEncoder.encode(kw, StandardCharsets.UTF_8);
            HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                    .header("User-Agent", "Mozilla/5.0 (recsys-thesis; contact: student)")
                    .header("Referer", "https://weread.qq.com/")
                    .timeout(Duration.ofSeconds(5))
                    .GET().build();
            HttpResponse<String> resp = http.send(req,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            var root = mapper.readTree(resp.body());
            for (var b : root.path("books")) {
                String link = b.path("bookInfo").path("deepLink").asText("");
                if (!link.isBlank()) {
                    return link;
                }
            }
        } catch (Exception ignored) {
            // 网络受限等：回退微信读书主页
        }
        return HOME;
    }

    private ResponseEntity<Void> redirect(String location) {
        return ResponseEntity.status(302).location(URI.create(location)).build();
    }
}
