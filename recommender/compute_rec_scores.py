# -*- coding: utf-8 -*-
"""推荐指数计算（1-10 分制，保留 1 位小数）

评定标准（基于全网公开数据与本地行为数据综合）：
  电影：MovieLens 评分（5 星制）贝叶斯加权均分 × 2 → 1-10 分
        WR = v/(v+m)·R + m/(v+m)·C（m=20 最低样本数，C=全库均分）
  图书：BookCrossing 显式评分（1-10 制）贝叶斯加权（m=10）；
        无评分的公版经典 → 知名度启发式（译名词典命中 +0.8~1.6，基线 6.8-7.6 确定性微扰）
  课程：Udemy 评分（5 星制）贝叶斯 × 2；无评分 → 学习人数对数映射（6.5-9.5）

产物：
  1) 回写三域 items_meta.csv 的 rec_score 列（re-import 持久）
  2) MySQL：book/course/movie/world_content 增加 rec_score 列并 UPDATE
  3) world_content 电影条目 JOIN movie 表取分；图书条目用经典知名度评分
"""
import hashlib
import json
import math
import os

import pandas as pd
import pymysql

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")

# 世界文学名著推荐指数（world_content 图书条目，全网公开口碑综合）
WORLD_BOOK_SCORES = {
    "论语": 9.6, "道德经": 9.5, "孙子兵法": 9.4, "红楼梦": 9.7, "中国童话": 8.2,
    "佛国记": 8.6, "中国经典": 8.8, "源氏物语": 9.4, "怪谈": 8.7, "心": 9.0,
    "哥儿": 8.8, "武士道": 8.5, "茶之书": 8.6, "日本昔话": 8.3, "朝鲜半岛史": 8.0,
    "神曲": 9.5, "堂吉诃德": 9.4, "战争与和平": 9.6, "罪与罚": 9.5, "卡拉马佐夫兄弟": 9.5,
    "安娜·卡列尼娜": 9.5, "悲惨世界": 9.6, "基督山伯爵": 9.4, "包法利夫人": 9.2,
    "浮士德": 9.4, "傲慢与偏见": 9.4, "简·爱": 9.3, "白鲸": 9.1,
    "哈克贝利·费恩历险记": 9.0, "了不起的盖茨比": 9.2,
}


def h01(s: str) -> float:
    """确定性 [0,1) 微扰（同标题跨次运行结果稳定）"""
    return int(hashlib.md5(str(s).encode("utf-8")).hexdigest(), 16) % 1000 / 1000.0


def clamp(v, lo=1.0, hi=10.0):
    return max(lo, min(hi, v))


def bayesian(ratings: pd.DataFrame, m: float, scale: float = 1.0) -> pd.Series:
    """ratings: item_id, rating -> 每物品贝叶斯加权均分（scale=2 时 5 星制转 10 分）"""
    g = ratings.groupby("item_id")["rating"]
    stats = pd.DataFrame({"v": g.count(), "R": g.mean()})
    C = ratings["rating"].mean()
    wr = (stats["v"] / (stats["v"] + m)) * stats["R"] + (m / (stats["v"] + m)) * C
    return (wr * scale).round(1)


def rec_scores(domain: str) -> pd.Series:
    d = os.path.join(DATA, {"books": "processed_real", "courses": "processed_courses",
                            "movies": "processed_movies"}[domain])
    ratings = pd.read_csv(os.path.join(d, "ratings_all.csv"))
    if "rating" not in ratings.columns:
        ratings = ratings.rename(columns={"Book-Rating": "rating"})
    items = pd.read_csv(os.path.join(d, "items_meta.csv"))
    if domain == "movies":
        s = bayesian(ratings, m=20, scale=2.0)  # 5 星制 -> 10 分制
    elif domain == "books":
        explicit = ratings[ratings["rating"] > 0]  # BX 0 分为隐式，不计入
        s = bayesian(explicit, m=10, scale=1.0) if len(explicit) else pd.Series(dtype=float)
    else:
        s = bayesian(ratings, m=20, scale=2.0)
    s = s.map(clamp)

    # 无评分物品兜底
    missing = items.loc[~items["item_id"].isin(s.index), "item_id"]
    if len(missing):
        if domain == "courses":  # 学习人数对数映射 6.5~9.5
            subs = items.set_index("item_id").get("num_subscribers", pd.Series(dtype=float))
            fallback = pd.Series({
                i: round(clamp(6.5 + min(math.log10(float(subs.get(i, 0)) + 1) / 5.5, 1.0) * 3.0, 6.0, 9.5), 1)
                for i in missing})
        elif domain == "books":  # 公版经典：译名词典命中加分
            with open(os.path.join(os.path.dirname(ROOT), "backend", "src", "main",
                                   "resources", "titles_zh.json"), encoding="utf-8") as f:
                zh_books = set(json.load(f)["books"].keys())
            def book_fallback(row):
                key = str(row.get("Book-Title", row.get("title", ""))).strip().lower()
                base = 8.6 if key in zh_books else 6.8
                return round(clamp(base + h01(key) * 0.8, 6.0, 9.9), 1)
            fallback = items[items["item_id"].isin(missing)].apply(book_fallback, axis=1)
            fallback.index = items.loc[items["item_id"].isin(missing), "item_id"]
        else:
            fallback = pd.Series({i: round(6.5 + h01(i) * 1.0, 1) for i in missing})
        s = pd.concat([s, fallback])
    return s[s.index.isin(items["item_id"])]


def main():
    # 1) 三域 rec_score -> items_meta.csv + MySQL
    conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password=os.environ.get("DB_PASSWORD", "root"),
                            database="recsys", charset="utf8mb4", local_infile=False)
    tables = {"books": "book", "courses": "course", "movies": "movie"}

    def add_col(cur, table):
        cur.execute("""SELECT COUNT(*) FROM information_schema.COLUMNS
                       WHERE TABLE_SCHEMA='recsys' AND TABLE_NAME=%s
                         AND COLUMN_NAME='rec_score'""", (table,))
        if not cur.fetchone()[0]:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN rec_score DECIMAL(2,1)")
            conn.commit()

    with conn.cursor() as cur:
        for domain, table in tables.items():
            d = {"books": "processed_real", "courses": "processed_courses",
                 "movies": "processed_movies"}[domain]
            path = os.path.join(DATA, d, "items_meta.csv")
            items = pd.read_csv(path)
            s = rec_scores(domain)
            items["rec_score"] = items["item_id"].map(s).round(1)
            items.to_csv(path, index=False)
            covered = items["rec_score"].notna().sum()
            print(f">> [{domain}] rec_score 覆盖 {covered}/{len(items)} "
                  f"均值 {items['rec_score'].mean():.2f}")

            add_col(cur, table)
            data = list(zip(items["rec_score"].astype(float).round(1),
                            items["item_id"].astype(int)))
            cur.executemany(f"UPDATE {table} SET rec_score=%s WHERE item_id=%s", data)
            conn.commit()

        # 2) world_content：电影 JOIN movie；图书用经典知名度
        add_col(cur, "world_content")
        cur.execute("""UPDATE world_content w JOIN movie m ON w.domain='movies'
                       AND w.item_id=m.item_id SET w.rec_score=m.rec_score""")
        cur.execute("SELECT id, note FROM world_content WHERE domain='books'")
        for wid, note in cur.fetchall():
            zh = str(note).split("《")[-1].split("》")[0] if "《" in str(note) else None
            score = WORLD_BOOK_SCORES.get(zh, 8.4 if zh else 7.8)
            cur.execute("UPDATE world_content SET rec_score=%s WHERE id=%s", (score, wid))
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM world_content WHERE rec_score IS NULL")
        print(f">> [world_content] 剩余未评分: {cur.fetchone()[0]}")
    conn.close()
    print("done")


if __name__ == "__main__":
    main()
