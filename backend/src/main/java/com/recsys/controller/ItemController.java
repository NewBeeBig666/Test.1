package com.recsys.controller;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.recsys.service.ItemService;

/**
 * 统一物品检索接口（图书/课程/电影三模块一致的浏览检索体验）：
 *   GET /api/items?domain=books|courses|movies&q=&category=&page=&size=
 *   GET /api/items/{domain}/{itemId}
 */
@RestController
@RequestMapping("/api/items")
public class ItemController {

    private final ItemService itemService;

    public ItemController(ItemService itemService) {
        this.itemService = itemService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam String domain,
            @RequestParam(defaultValue = "") String q,
            @RequestParam(required = false) String category,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "12") int size) {
        return itemService.search(domain, q, category, page, size);
    }

    @GetMapping("/{domain}/{itemId}")
    public Map<String, Object> detail(@PathVariable String domain, @PathVariable long itemId) {
        return itemService.detail(domain, itemId);
    }
}
