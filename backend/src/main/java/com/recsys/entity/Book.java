package com.recsys.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** 图书（item_id 为算法服务使用的内部物品ID，与推荐结果直接对应） */
@Entity
@Table(name = "book")
public class Book {

    @Id
    @Column(name = "item_id")
    private Long itemId;

    private String isbn;
    private String title;
    private String author;
    private String publisher;

    /** 封面图 URL（BX 数据集 Image-URL-M，前端加载失败回退排版卡片） */
    @Column(name = "image_url", length = 512)
    private String imageUrl;

    /** 推荐指数（1-10 分制，compute_rec_scores.py 综合评定） */
    @Column(name = "rec_score")
    private Double recScore;

    protected Book() {
    }

    public Book(Long itemId, String isbn, String title, String author, String publisher) {
        this.itemId = itemId;
        this.isbn = isbn;
        this.title = title;
        this.author = author;
        this.publisher = publisher;
    }

    public Long getItemId() {
        return itemId;
    }

    public String getIsbn() {
        return isbn;
    }

    public String getTitle() {
        return title;
    }

    public String getAuthor() {
        return author;
    }

    public String getPublisher() {
        return publisher;
    }

    public String getImageUrl() {
        return imageUrl;
    }

    public Double getRecScore() {
        return recScore;
    }
}
