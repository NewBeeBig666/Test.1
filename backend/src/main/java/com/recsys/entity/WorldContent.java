package com.recsys.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;

/**
 * 环球精选内容（多区域内容库）：
 * 图书来自 Project Gutenberg（公版，source_url 指向官方阅读页）；
 * 电影来自 MovieLens（item_id 关联 movie 表，详情/海报/评分推荐全联动）。
 */
@Entity
@Table(name = "world_content", indexes = @Index(name = "idx_dr", columnList = "domain, region"))
public class WorldContent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** movies | books */
    @Column(nullable = false, length = 16)
    private String domain;

    /** 中国 | 日本 | 韩国 | 欧洲 | 拉美 | 世界其他 */
    @Column(nullable = false, length = 16)
    private String region;

    @Column(length = 512)
    private String title;

    /** 电影：genres；图书：作者 */
    @Column(length = 256)
    private String subtitle;

    /** 电影：年份；图书：分类（古典文学/现代文学/历史文化） */
    @Column(length = 256)
    private String extra;

    /** 中文说明（如"卧虎藏龙 · 李安武侠史诗"） */
    @Column(length = 256)
    private String note;

    /** 电影域内 item_id（关联 movie 表）；图书为空 */
    @Column(name = "item_id")
    private Long itemId;

    /** Gutenberg 官方阅读页等 */
    @Column(name = "source_url", length = 512)
    private String sourceUrl;

    /** 推荐指数（1-10 分制：电影取 movie 表联算分，图书按经典知名度评定） */
    @Column(name = "rec_score")
    private Double recScore;

    /** 典藏封面（fill_book_covers.py 程序化生成 /covers/world/{id}.png） */
    @Column(name = "image_url", length = 512)
    private String imageUrl;

    protected WorldContent() {
    }

    public Long getId() {
        return id;
    }

    public String getDomain() {
        return domain;
    }

    public String getRegion() {
        return region;
    }

    public String getTitle() {
        return title;
    }

    public String getSubtitle() {
        return subtitle;
    }

    public String getExtra() {
        return extra;
    }

    public String getNote() {
        return note;
    }

    public Long getItemId() {
        return itemId;
    }

    public String getSourceUrl() {
        return sourceUrl;
    }

    public Double getRecScore() {
        return recScore;
    }

    public String getImageUrl() {
        return imageUrl;
    }
}
