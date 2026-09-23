package com.recsys.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

/**
 * 资源富化缓存（封面 / 简介 / 外部链接）：
 * 首次访问详情时由算法服务抓取（OpenLibrary / IMDb suggest / 模板合成）并缓存；
 * 管理后台可手动编辑（manual=true，不会被自动抓取覆盖）。
 */
@Entity
@Table(name = "item_enrichment",
        uniqueConstraints = @UniqueConstraint(name = "uk_domain_item", columnNames = {"domain", "item_id"}))
public class ItemEnrichment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 16)
    private String domain;

    @Column(name = "item_id", nullable = false)
    private Long itemId;

    @Column(name = "cover_url", length = 512)
    private String coverUrl;

    @Column(name = "cover_width")
    private Integer coverWidth;

    @Column(name = "cover_height")
    private Integer coverHeight;

    @Column(name = "cover_source", length = 32)
    private String coverSource;

    /** {"sections":[{"label":"...","text":"..."}],"source":"openlibrary|imdb|synthetic|admin"} */
    @Column(columnDefinition = "text")
    private String summaryJson;

    /** [{"label":"...","url":"https://...","type":"read|buy|info|study"}] */
    @Column(columnDefinition = "text")
    private String linksJson;

    @Column(length = 32)
    private String source;

    @Column(nullable = false)
    private boolean manual;

    /** 链接有效性检查：最近检查时间与结果 */
    @Column(name = "checked_at")
    private LocalDateTime checkedAt;

    @Column(name = "check_ok")
    private Boolean checkOk;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt = LocalDateTime.now();

    protected ItemEnrichment() {
    }

    public ItemEnrichment(String domain, Long itemId) {
        this.domain = domain;
        this.itemId = itemId;
    }

    public Long getId() {
        return id;
    }

    public String getDomain() {
        return domain;
    }

    public Long getItemId() {
        return itemId;
    }

    public String getCoverUrl() {
        return coverUrl;
    }

    public void setCoverUrl(String coverUrl) {
        this.coverUrl = coverUrl;
    }

    public Integer getCoverWidth() {
        return coverWidth;
    }

    public void setCoverWidth(Integer coverWidth) {
        this.coverWidth = coverWidth;
    }

    public Integer getCoverHeight() {
        return coverHeight;
    }

    public void setCoverHeight(Integer coverHeight) {
        this.coverHeight = coverHeight;
    }

    public String getCoverSource() {
        return coverSource;
    }

    public void setCoverSource(String coverSource) {
        this.coverSource = coverSource;
    }

    public String getSummaryJson() {
        return summaryJson;
    }

    public void setSummaryJson(String summaryJson) {
        this.summaryJson = summaryJson;
    }

    public String getLinksJson() {
        return linksJson;
    }

    public void setLinksJson(String linksJson) {
        this.linksJson = linksJson;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public boolean isManual() {
        return manual;
    }

    public void setManual(boolean manual) {
        this.manual = manual;
    }

    public LocalDateTime getCheckedAt() {
        return checkedAt;
    }

    public void setCheckedAt(LocalDateTime checkedAt) {
        this.checkedAt = checkedAt;
    }

    public Boolean getCheckOk() {
        return checkOk;
    }

    public void setCheckOk(Boolean checkOk) {
        this.checkOk = checkOk;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
}
