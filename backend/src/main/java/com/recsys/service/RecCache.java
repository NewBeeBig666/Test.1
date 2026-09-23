package com.recsys.service;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

/**
 * 推荐结果缓存：Redis 优先，Redis 不可用时降级为本地内存缓存。
 *
 * key 规则：rec:{algo}:{userId}:{n}
 * 用户产生新行为时按 userId 淘汰（见 evictByUser）。
 */
@Component
public class RecCache {

    private final StringRedisTemplate redis;
    private final Duration ttl;

    private record Entry(String value, long expireAtMs) {}

    private final Map<String, Entry> local = new ConcurrentHashMap<>();
    /** Redis 健康标记：失败后 60s 内不再尝试，避免每次请求都等待超时 */
    private volatile long redisRetryAfterMs = 0;

    public RecCache(StringRedisTemplate redisTemplate,
                    @Value("${algo.cache-ttl-minutes:30}") long ttlMinutes) {
        this.redis = redisTemplate;
        this.ttl = Duration.ofMinutes(ttlMinutes);
    }

    public String get(String key) {
        if (tryRedis()) {
            try {
                String v = redis.opsForValue().get(key);
                if (v != null) {
                    return v;
                }
            } catch (Exception e) {
                markRedisDown();
            }
        }
        Entry entry = local.get(key);
        if (entry == null) {
            return null;
        }
        if (System.currentTimeMillis() > entry.expireAtMs()) {
            local.remove(key);
            return null;
        }
        return entry.value();
    }

    public void put(String key, String value) {
        if (tryRedis()) {
            try {
                redis.opsForValue().set(key, value, ttl);
                return;
            } catch (Exception e) {
                markRedisDown();
            }
        }
        local.put(key, new Entry(value, System.currentTimeMillis() + ttl.toMillis()));
    }

    /** 淘汰某用户全部推荐缓存（Redis keys 扫描 + 本地过滤） */
    public void evictByUser(long userId) {
        String userPart = ":" + userId + ":";
        if (tryRedis()) {
            try {
                var keys = redis.keys("rec:*" + userPart + "*");
                if (keys != null && !keys.isEmpty()) {
                    redis.delete(keys);
                }
            } catch (Exception e) {
                markRedisDown();
            }
        }
        local.keySet().removeIf(k -> k.contains(userPart));
    }

    private boolean tryRedis() {
        return System.currentTimeMillis() >= redisRetryAfterMs;
    }

    private void markRedisDown() {
        redisRetryAfterMs = System.currentTimeMillis() + 60_000;
    }
}
