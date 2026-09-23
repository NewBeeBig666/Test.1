package com.recsys.service;

import java.util.List;
import java.util.Set;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.recsys.client.AlgoServiceClient;
import com.recsys.entity.BehaviorEvent;
import com.recsys.repo.BehaviorEventRepository;

/**
 * 用户行为采集（三域）：MySQL 落库（真实行为数据）+ 转发算法服务（增量训练数据）
 * + 淘汰该用户的推荐缓存（保证下一次推荐反映最新兴趣）。
 */
@Service
public class EventService {

    public static final Set<String> ALLOWED_TYPES = Set.of("view", "click", "rating", "favorite");
    public static final Set<String> DOMAINS = Set.of("books", "courses", "movies");

    private final BehaviorEventRepository repo;
    private final AlgoServiceClient algo;
    private final RecCache cache;

    public EventService(BehaviorEventRepository repo, AlgoServiceClient algo, RecCache cache) {
        this.repo = repo;
        this.algo = algo;
        this.cache = cache;
    }

    @Transactional
    public BehaviorEvent record(long userId, long itemId, String domain, String eventType, Double rating) {
        if (!ALLOWED_TYPES.contains(eventType)) {
            throw new IllegalArgumentException("event_type 须为 view|click|rating|favorite");
        }
        if (!DOMAINS.contains(domain)) {
            throw new IllegalArgumentException("domain 须为 books|courses|movies");
        }
        BehaviorEvent event = new BehaviorEvent(userId, itemId, domain, eventType, rating);
        event = repo.save(event);
        // 转发失败不影响已落库的行为（catch 在 client 内抛出，这里显式忽略）
        try {
            algo.postEvent(userId, itemId, domain, eventType, rating);
        } catch (AlgoServiceClient.AlgoServiceException ignored) {
        }
        // 评分（显式反馈）后异步触发算法重训，让新行为尽快反映到推荐结果
        if ("rating".equals(eventType)) {
            Thread t = new Thread(() -> {
                try {
                    algo.postReload();
                } catch (Exception ignored) {
                }
            }, "algo-reload");
            t.setDaemon(true);
            t.start();
        }
        cache.evictByUser(userId);
        return event;
    }

    public List<BehaviorEvent> history(long userId) {
        return repo.findTop50ByUserIdOrderByCreatedAtDesc(userId);
    }
}
