# -*- coding: utf-8 -*-
"""
跨域统一 TF-IDF 标签空间构建（跨领域推荐的核心）。

三个域的物品文本（图书：书名+作者+出版社；电影：片名+类型+年份；课程：标题+难度+类目）
使用同一份 TF-IDF 词表向量化——英文词汇跨域共享（如 love / history / python
同时出现在图书书名、电影类型与课程标题中），从而支持：

  用户在任意域的行为 -> 统一画像 -> 推荐任意目标域物品

输出 data/processed_global/：
    items_global.csv      global_id, item_id, domain, title, subtitle, extra (+附加列)
    global_tfidf.npz      行号与 items_global.csv 行号一一对应
    global_vectorizer.joblib

global_id = 域偏移 + 域内 item_id（books+1e8 / movies+2e8 / courses+3e8，防止冲突）。

用法：python preprocess_global.py
"""
from __future__ import annotations

import argparse
import os

import joblib
import pandas as pd
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer

DOMAIN_DIRS = {
    "books": "./data/processed_real",
    "movies": "./data/processed_movies",
    "courses": "./data/processed_courses",
}
GLOBAL_OFFSET = {"books": 100_000_000, "movies": 200_000_000, "courses": 300_000_000}


def load_domain_items(domain: str, path: str) -> pd.DataFrame:
    """读取各域 items_meta 并统一列名 -> (item_id, title, subtitle, extra, 附加列)"""
    m = pd.read_csv(os.path.join(path, "items_meta.csv"))
    if domain == "books":
        m = m.rename(columns={"Book-Title": "title", "Book-Author": "subtitle",
                              "Publisher": "extra"})
        keep = ["item_id", "title", "subtitle", "extra", "image_url"]
    elif domain == "courses":
        keep = ["item_id", "title", "subtitle", "extra",
                "platform", "price", "num_subscribers"]
    else:  # movies
        keep = ["item_id", "title", "subtitle", "extra"]
    m = m[keep].copy()
    m["domain"] = domain
    m["global_id"] = GLOBAL_OFFSET[domain] + m["item_id"].astype(int)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", default="./data/processed_global")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    frames = []
    for domain, path in DOMAIN_DIRS.items():
        items = load_domain_items(domain, path)
        print(f">> {domain}: {len(items)} items")
        frames.append(items)
    all_items = pd.concat(frames, ignore_index=True)

    for col in ["title", "subtitle", "extra"]:
        all_items[col] = all_items[col].astype(str).replace({"nan": "", "None": ""})
    text = (all_items["title"] + " " + all_items["subtitle"] + " " + all_items["extra"])
    vec = TfidfVectorizer(max_features=30000, stop_words="english",
                          ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    tfidf = vec.fit_transform(text)
    print(f">> 统一 TF-IDF 空间：{tfidf.shape[0]} items x {tfidf.shape[1]} 词（跨域共享词表）")

    all_items.to_csv(os.path.join(args.out_dir, "items_global.csv"), index=False)
    save_npz(os.path.join(args.out_dir, "global_tfidf.npz"), tfidf)
    joblib.dump(vec, os.path.join(args.out_dir, "global_vectorizer.joblib"))
    print(f">> 完成！输出目录 {args.out_dir}")


if __name__ == "__main__":
    main()
