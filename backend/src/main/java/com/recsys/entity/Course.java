package com.recsys.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** 课程（Udemy 真实课程目录；item_id 为算法服务使用的域内物品ID） */
@Entity
@Table(name = "course")
public class Course {

    @Id
    @Column(name = "item_id")
    private Long itemId;

    private String title;

    private String level;

    private String category;

    private String platform;

    private Double price;

    private Long subscribers;

    /** Udemy 官方课程页链接（外部跳转：报名学习） */
    @Column(name = "source_url", length = 512)
    private String sourceUrl;

    /** 平台设计封面（generate_course_covers.py 生成 1200×1600 PNG，经 /covers/ 提供） */
    @Column(name = "poster_url", length = 512)
    private String posterUrl;

    /** 推荐指数（1-10 分制，compute_rec_scores.py 综合评定） */
    @Column(name = "rec_score")
    private Double recScore;

    protected Course() {
    }

    public Course(Long itemId, String title, String level, String category,
                  String platform, Double price, Long subscribers) {
        this.itemId = itemId;
        this.title = title;
        this.level = level;
        this.category = category;
        this.platform = platform;
        this.price = price;
        this.subscribers = subscribers;
    }

    public Long getItemId() {
        return itemId;
    }

    public String getTitle() {
        return title;
    }

    public String getLevel() {
        return level;
    }

    public String getCategory() {
        return category;
    }

    public String getPlatform() {
        return platform;
    }

    public Double getPrice() {
        return price;
    }

    public Long getSubscribers() {
        return subscribers;
    }

    public String getSourceUrl() {
        return sourceUrl;
    }

    public String getPosterUrl() {
        return posterUrl;
    }

    public Double getRecScore() {
        return recScore;
    }
}
