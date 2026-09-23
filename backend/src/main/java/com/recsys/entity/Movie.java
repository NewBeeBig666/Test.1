package com.recsys.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** 电影（MovieLens ml-latest-small；item_id 为算法服务使用的域内物品ID） */
@Entity
@Table(name = "movie")
public class Movie {

    @Id
    @Column(name = "item_id")
    private Long itemId;

    private String title;

    private String genres;

    @Column(name = "year")
    private String year;

    /** IMDb 海报 CDN URL（fetch_covers.py 经免 key suggest API 预取，含分辨率审核） */
    @Column(name = "poster_url", length = 512)
    private String posterUrl;

    /** 推荐指数（1-10 分制，compute_rec_scores.py 综合评定） */
    @Column(name = "rec_score")
    private Double recScore;

    protected Movie() {
    }

    public Movie(Long itemId, String title, String genres, String year) {
        this.itemId = itemId;
        this.title = title;
        this.genres = genres;
        this.year = year;
    }

    public Long getItemId() {
        return itemId;
    }

    public String getTitle() {
        return title;
    }

    public String getGenres() {
        return genres;
    }

    public String getYear() {
        return year;
    }

    public String getPosterUrl() {
        return posterUrl;
    }

    public Double getRecScore() {
        return recScore;
    }
}
