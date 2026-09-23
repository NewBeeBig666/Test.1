package com.recsys.client;

import java.util.HashMap;
import java.util.Map;

import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

/**
 * Python 算法服务（FastAPI）HTTP 客户端（三域统一接口）。
 */
@Component
public class AlgoServiceClient {

    private final RestTemplate http;
    private final String baseUrl;

    public AlgoServiceClient(RestTemplate algoRestTemplate, String algoBaseUrl) {
        this.http = algoRestTemplate;
        this.baseUrl = algoBaseUrl;
    }

    /** Top-N 推荐（domain: books|courses|movies），返回原始JSON字符串（由上层解析/透传） */
    public String getRecommend(long userId, String domain, String algo, int n) {
        String url = UriComponentsBuilder.fromHttpUrl(baseUrl + "/api/recommend")
                .queryParam("user_id", userId)
                .queryParam("domain", domain)
                .queryParam("algo", algo)
                .queryParam("n", n)
                .toUriString();
        return http.getForObject(url, String.class);
    }

    /** 单域用户画像（兴趣标签+属性标签） */
    public String getProfile(long userId, String domain) {
        String url = UriComponentsBuilder.fromHttpUrl(baseUrl + "/api/user/{id}/profile")
                .queryParam("domain", domain)
                .buildAndExpand(userId)
                .toUriString();
        return http.getForObject(url, String.class);
    }

    /** 跨域统一画像（三域兴趣融合 + 分域明细） */
    public String getGlobalProfile(long userId) {
        return http.getForObject(baseUrl + "/api/user/{id}/profile/global",
                String.class, userId);
    }

    /** 离线对比实验指标（evaluate.py 产出） */
    public String getMetrics() {
        return http.getForObject(baseUrl + "/api/metrics", String.class);
    }

    /** 可用算法列表 */
    public String getAlgorithms() {
        return http.getForObject(baseUrl + "/api/algorithms", String.class);
    }

    /** 触发算法服务合并行为日志并重训（三域 + CrossDomain，秒级） */
    public String postReload() {
        return http.postForObject(baseUrl + "/api/reload", null, String.class);
    }

    /** 资源富化（封面/简介/外链，Python 侧实时抓取 OpenLibrary/IMDb/模板合成） */
    public String getEnrich(String domain, long itemId) {
        return http.getForObject(baseUrl + "/api/enrich/{domain}/{itemId}",
                String.class, domain, itemId);
    }

    /** 行为上报：SpringBoot 落库 MySQL 后转发给算法服务做增量训练数据 */
    public void postEvent(long userId, long itemId, String domain, String eventType, Double rating) {
        Map<String, Object> body = new HashMap<>();
        body.put("user_id", userId);
        body.put("item_id", itemId);
        body.put("domain", domain);
        body.put("event_type", eventType);
        if (rating != null) {
            body.put("rating", rating);
        }
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        try {
            http.exchange(baseUrl + "/api/events", HttpMethod.POST,
                    new HttpEntity<>(body, headers), String.class);
        } catch (RestClientException e) {
            // 算法服务不可用时行为仍已落库，不阻断业务
            throw new AlgoServiceException("算法服务转发失败: " + e.getMessage(), e);
        }
    }

    /** 算法服务调用异常（对应HTTP 502） */
    public static class AlgoServiceException extends RuntimeException {
        public AlgoServiceException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
