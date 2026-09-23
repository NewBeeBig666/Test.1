# -*- coding: utf-8 -*-
"""
生成与 Book-Crossing 同构的合成数据（冒烟测试用，无需从天池下载）。

通过"潜在主题偏好"生成数据：物品属于某个主题，用户对主题有偏好分布，
评分由偏好强度+噪声决定，保证协同过滤/内容推荐在该数据上可学到模式。

用法：python make_fake_data.py --out_dir ./data/raw
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

TOPICS = {
    "science": ["quantum", "cosmos", "evolution", "neuron", "genome", "physics"],
    "romance": ["love", "heart", "summer", "kiss", "promise", "wedding"],
    "history": ["empire", "dynasty", "war", "revolution", "century", "kingdom"],
    "tech": ["algorithm", "compiler", "network", "database", "robot", "code"],
    "fantasy": ["dragon", "wizard", "sword", "magic", "elf", "prophecy"],
}
AUTHORS = {t: [f"{t.title()}Writer{i}" for i in range(8)] for t in TOPICS}
PUBLISHERS = {t: [f"{t.title()}Press{i}" for i in range(3)] for t in TOPICS}
CITIES = ["beijing, beijing, china", "shanghai, shanghai, china",
          "guangzhou, guangdong, china", "new york, ny, usa", "london, , uk"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", default="./data/raw")
    ap.add_argument("--n_users", type=int, default=300)
    ap.add_argument("--n_items", type=int, default=400)
    ap.add_argument("--min_ratings", type=int, default=25, help="每用户最少交互数")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    topics = list(TOPICS)

    # 物品元数据
    item_topic = rng.choice(topics, size=args.n_items)
    books = []
    for i in range(args.n_items):
        t = item_topic[i]
        word = TOPICS[t][rng.integers(len(TOPICS[t]))]
        books.append({
            "ISBN": f"ISBN{i:06d}",
            "Book-Title": f"The {word} chronicles vol {i}",
            "Book-Author": AUTHORS[t][rng.integers(len(AUTHORS[t]))],
            "Year-Of-Publication": str(rng.integers(1970, 2020)),
            "Publisher": PUBLISHERS[t][rng.integers(len(PUBLISHERS[t]))],
        })
    books_df = pd.DataFrame(books)

    # 用户：1~2 个偏好主题，交互集中于偏好主题
    ratings = []
    for u in range(args.n_users):
        likes = rng.choice(topics, size=rng.integers(1, 3), replace=False)
        n_rate = args.min_ratings + rng.integers(0, 30)
        like_items = np.where(np.isin(item_topic, likes))[0]
        other_items = np.where(~np.isin(item_topic, likes))[0]
        n_from_like = int(n_rate * 0.85)
        chosen = rng.choice(like_items, size=min(n_from_like, len(like_items)), replace=False)
        chosen = np.concatenate([
            chosen,
            rng.choice(other_items, size=max(n_rate - len(chosen), 0),
                       replace=False),
        ])
        for i in chosen:
            base = 9 if item_topic[i] in likes else 4
            r = int(np.clip(round(base + rng.normal(0, 1.2)), 1, 10))
            ratings.append({"User-ID": 1000 + u, "ISBN": books[i]["ISBN"], "Book-Rating": r})

    ratings_df = pd.DataFrame(ratings).drop_duplicates(subset=["User-ID", "ISBN"])
    users_df = pd.DataFrame({
        "User-ID": 1000 + np.arange(args.n_users),
        "Location": rng.choice(CITIES, size=args.n_users),
        "Age": rng.integers(15, 70, size=args.n_users),
    })

    # 与真实 Book-Crossing 一致的分隔符/编码
    ratings_df.to_csv(os.path.join(args.out_dir, "BX-Book-Ratings.csv"),
                      sep=";", index=False, encoding="latin-1")
    books_df.to_csv(os.path.join(args.out_dir, "BX-Books.csv"),
                    sep=";", index=False, encoding="latin-1")
    users_df.to_csv(os.path.join(args.out_dir, "BX-Users.csv"),
                    sep=";", index=False, encoding="latin-1")
    print(f">> 合成数据完成：{len(ratings_df)} 条评分，{args.n_users} 用户，"
          f"{args.n_items} 图书 -> {args.out_dir}")


if __name__ == "__main__":
    main()
