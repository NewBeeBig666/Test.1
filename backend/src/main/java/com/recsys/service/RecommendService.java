package com.recsys.service;

import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.recsys.client.AlgoServiceClient;
import com.recsys.service.ItemService.ItemDTO;

/**
 * 推荐服务：查缓存 -> 未命中调用算法服务 -> 写缓存。
 * 缓存 key：rec:{domain}:{algo}:{userId}:{n}，响应附加 fromCache 便于演示缓存命中。
 */
@Service
public class RecommendService {

    private final AlgoServiceClient algo;
    private final RecCache cache;
    private final ObjectMapper mapper = new ObjectMapper();

    public RecommendService(AlgoServiceClient algo, RecCache cache) {
        this.algo = algo;
        this.cache = cache;
    }

    public JsonNode recommend(long userId, String domain, String algoName, int n) {
        String key = "rec:" + domain + ":" + algoName + ":" + userId + ":" + n;
        String raw = cache.get(key);
        boolean fromCache = raw != null;
        if (raw == null) {
            raw = algo.getRecommend(userId, domain, algoName, n);
        }
        try {
            ObjectNode node = (ObjectNode) mapper.readTree(raw);
            node.put("fromCache", fromCache);
            if (!fromCache) {
                cache.put(key, raw);
            }
            return node;
        } catch (Exception e) {
            throw new AlgoServiceClient.AlgoServiceException("算法服务响应解析失败", e);
        }
    }

    /** 物品详情富化：推荐列表 join MySQL 物品表，补全封面/元数据 */
    public JsonNode enrichWithItems(JsonNode recResp, ItemService itemService) {
        try {
            ObjectNode node = (ObjectNode) recResp;
            String domain = node.path("domain").asText();
            for (JsonNode item : node.path("items")) {
                ObjectNode o = (ObjectNode) item;
                long itemId = o.path("item_id").asLong();
                ItemDTO dto = itemService.findForEnrich(domain, itemId);
                if (dto != null) {
                    if (dto.imageUrl() != null && o.path("image_url").isMissingNode()) {
                        o.put("image_url", dto.imageUrl());
                    }
                    if (dto.coverUrl() != null && o.path("cover_url").isMissingNode()) {
                        o.put("cover_url", dto.coverUrl());
                    }
                    if (dto.sourceUrl() != null) {
                        o.put("source_url", dto.sourceUrl());
                    }
                    if (dto.badge() != null) {
                        o.put("badge", dto.badge());
                    }
                    if (dto.titleZh() != null) {
                        o.put("title_zh", dto.titleZh());
                    }
                    if (dto.origTitle() != null) {
                        o.put("orig_title", dto.origTitle());
                    }
                    if (dto.platform() != null) {
                        o.put("platform", dto.platform());
                    }
                    if (dto.price() != null) {
                        o.put("price", dto.price());
                    }
                    if (dto.subscribers() != null) {
                        o.put("subscribers", dto.subscribers());
                    }
                    if (dto.recScore() != null) {
                        o.put("rec_score", dto.recScore());
                    }
                }
            }
            return node;
        } catch (Exception e) {
            return recResp; // 富化失败不影响推荐结果
        }
    }

    public String profile(long userId, String domain) {
        return algo.getProfile(userId, domain);
    }

    public String globalProfile(long userId) {
        return algo.getGlobalProfile(userId);
    }

    public String metrics() {
        return algo.getMetrics();
    }

    public String algorithms() {
        return algo.getAlgorithms();
    }

    public String reload() {
        return algo.postReload();
    }
}
