package com.recsys.controller;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.recsys.entity.BehaviorEvent;
import com.recsys.interceptor.UserIdHolder;
import com.recsys.service.EventService;

/**
 * 用户行为采集接口（前端埋点 -> 本接口 -> MySQL + 算法服务）
 * 用户ID取自会话，body 只需传物品与域信息。
 */
@RestController
@RequestMapping("/api/event")
public class EventController {

    private final EventService eventService;
    private final com.recsys.service.ItemService itemService;

    public EventController(EventService eventService,
                           com.recsys.service.ItemService itemService) {
        this.eventService = eventService;
        this.itemService = itemService;
    }

    public record EventRequest(Long itemId, String domain, String eventType, Double rating) {}

    @PostMapping
    public Map<String, Object> record(@RequestBody EventRequest req) {
        if (req.itemId() == null || req.domain() == null || req.eventType() == null) {
            throw new IllegalArgumentException("itemId/domain/eventType 不能为空");
        }
        long userId = UserIdHolder.require();
        BehaviorEvent saved = eventService.record(
                userId, req.itemId(), req.domain(), req.eventType(), req.rating());
        return Map.of("status", "recorded", "id", saved.getId());
    }

    /** 当前用户最近 50 条行为（三域，附物品标题） */
    @GetMapping("/history")
    public List<Map<String, Object>> history() {
        long userId = UserIdHolder.require();
        return eventService.history(userId).stream().<Map<String, Object>>map(e -> {
            Map<String, Object> m = new java.util.LinkedHashMap<>();
            m.put("id", e.getId());
            m.put("itemId", e.getItemId());
            m.put("domain", e.getDomain());
            m.put("eventType", e.getEventType());
            m.put("rating", e.getRating());
            m.put("createdAt", e.getCreatedAt().toString());
            var dto = itemService.findForEnrich(e.getDomain(), e.getItemId());
            m.put("title", dto == null ? ("物品 #" + e.getItemId()) : dto.title());
            if (dto != null) {
                m.put("subtitle", dto.subtitle());
            }
            return m;
        }).toList();
    }
}
