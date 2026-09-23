package com.recsys.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;

/** 用户行为：浏览/点击/评分/收藏（三域：books|courses|movies） */
@Entity
@Table(name = "behavior_event", indexes = @Index(name = "idx_user", columnList = "user_id"))
public class BehaviorEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "item_id", nullable = false)
    private Long itemId;

    /** 行为所属域（books|courses|movies），历史数据默认 books */
    @Column(name = "domain", nullable = false, length = 16,
            columnDefinition = "varchar(16) not null default 'books'")
    private String domain = "books";

    @Column(name = "event_type", nullable = false, length = 16)
    private String eventType;

    private Double rating;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt = LocalDateTime.now();

    protected BehaviorEvent() {
    }

    public BehaviorEvent(Long userId, Long itemId, String domain, String eventType, Double rating) {
        this.userId = userId;
        this.itemId = itemId;
        this.domain = domain;
        this.eventType = eventType;
        this.rating = rating;
    }

    public Long getId() {
        return id;
    }

    public Long getUserId() {
        return userId;
    }

    public Long getItemId() {
        return itemId;
    }

    public String getDomain() {
        return domain;
    }

    public String getEventType() {
        return eventType;
    }

    public Double getRating() {
        return rating;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}
