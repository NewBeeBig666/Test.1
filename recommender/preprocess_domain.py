# -*- coding: utf-8 -*-
"""
多域数据预处理：电影（MovieLens ml-latest-small）与课程（Udemy 真实课程目录）。

电影域：MovieLens ml-latest-small（GroupLens 公开数据集，天池有镜像）
    ratings.csv / movies.csv -> 统一格式，真实用户评分。

课程域：Udemy Courses Dataset（Kaggle 公开数据集，3678 门真实课程元数据）。
    由于公开渠道无个体级课程评分数据（MOOCCube 等需在天池申请），
    用户-课程评分基于真实课程目录模拟生成（文档与论文中需如实说明）：
      - 用户偏好 1~2 个类目（按类目课程量加权抽取）
      - 选课概率 ∝ 课程订阅数（热门课更可能被学习）
      - 偏好类目评分 ~ N(4.3, 0.55)，非偏好 ~ N(2.6, 0.70)，截断到 [1,5]

输出统一的 processed 格式（供 api.py / evaluate.py 多域使用）：
    ratings_all.csv / ratings_train.csv / ratings_test.csv
        列: orig_user_id, user_id, item_id, rating, rating_norm
    items_meta.csv        列: item_id, title, subtitle, extra (+ 域附加列)
    item_tfidf.npz / item_vectorizer.joblib
    users_meta.csv        列: User-ID, age_group, country（域无公开属性则省略）

用法：
    python preprocess_domain.py --domain movies
    python preprocess_domain.py --domain courses --seed 42
"""
from __future__ import annotations

import argparse
import os

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split

MIN_USER_INTERACTIONS = 5
MIN_ITEM_INTERACTIONS = 5
RANDOM_STATE = 42


# ---------------------------------------------------------------------------
# 课程域：Udemy 真实课程目录 -> 统一物品表 + 模拟评分
# ---------------------------------------------------------------------------
def load_courses_raw(csv_path: str):
    """读取 Kaggle Udemy Courses Dataset（真实课程元数据）。

    统一列：item_orig=course_id, title=course_title,
            subtitle=level, extra=subject（类目），附加 platform/price/num_subscribers
    """
    df = pd.read_csv(csv_path)
    items = pd.DataFrame({
        "item_orig": df["course_id"],
        "title": df["course_title"].str.strip(),
        "subtitle": df["level"].fillna("All Levels"),
        "extra": df["subject"],
        "platform": "Udemy",
        "price": df["price"],
        "num_subscribers": df["num_subscribers"],
        "source_url": df["url"].fillna(""),
    })
    items = items.dropna(subset=["title", "extra"]).drop_duplicates("item_orig")
    return items


def simulate_course_ratings(rng: np.random.Generator, items: pd.DataFrame,
                            n_users: int = 2500):
    """基于真实课程目录模拟用户-课程评分（构造方法见模块 docstring）。"""
    subjects = items["extra"].values
    subj_cats = sorted(set(subjects))
    subj_weight = np.array([(subjects == s).sum() for s in subj_cats], float)
    # 选课概率 ∝ 订阅数（热度）
    pop = items["num_subscribers"].fillna(0).values.astype(float) + 50.0

    rows = []
    for u in range(n_users):
        likes = rng.choice(subj_cats, size=int(rng.integers(1, 3)), replace=False,
                           p=subj_weight / subj_weight.sum())
        n_rate = int(rng.integers(20, 46))
        is_like = np.isin(subjects, likes)
        like_idx, other_idx = np.where(is_like)[0], np.where(~is_like)[0]
        n_like = min(int(n_rate * 0.85), len(like_idx))
        chosen = rng.choice(like_idx, size=n_like, replace=False,
                            p=pop[like_idx] / pop[like_idx].sum())
        n_other = max(n_rate - n_like, 0)
        if n_other:
            chosen = np.concatenate([chosen, rng.choice(
                other_idx, size=min(n_other, len(other_idx)), replace=False,
                p=pop[other_idx] / pop[other_idx].sum())])
        for i in chosen:
            base, sd = (4.3, 0.55) if is_like[i] else (2.6, 0.70)
            r = np.clip(round((base + rng.normal(0, sd)) * 2) / 2, 1, 5)
            rows.append({"orig_user_id": 10000 + u,
                         "item_orig": int(items["item_orig"].values[i]),
                         "rating": float(r)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 电影域：MovieLens -> 统一格式
# ---------------------------------------------------------------------------
def load_movies_raw(ml_dir: str):
    ratings = pd.read_csv(os.path.join(ml_dir, "ratings.csv"))
    movies = pd.read_csv(os.path.join(ml_dir, "movies.csv"))
    movies["title"] = movies["title"].str.strip()
    movies["year"] = movies["title"].str.extract(r"\((\d{4})\)$")[0]
    movies["genres"] = movies["genres"].str.replace("|", " ", regex=False)
    items = pd.DataFrame({
        "item_orig": movies["movieId"],
        "title": movies["title"],
        "subtitle": movies["genres"],
        "extra": movies["year"].fillna(""),
    })
    ratings = ratings.rename(columns={"userId": "orig_user_id", "movieId": "item_orig"})
    return ratings[["orig_user_id", "item_orig", "rating"]], items


# ---------------------------------------------------------------------------
# 清洗 / 划分 / 特征（与 preprocess.py 同一套流程，输出统一列名）
# ---------------------------------------------------------------------------
def clean_and_split(ratings: pd.DataFrame):
    df = ratings.drop_duplicates(subset=["orig_user_id", "item_orig"]).copy()
    while True:
        uc = df["orig_user_id"].value_counts()
        df = df[df["orig_user_id"].isin(uc[uc >= MIN_USER_INTERACTIONS].index)]
        ic = df["item_orig"].value_counts()
        nd = df[df["item_orig"].isin(ic[ic >= MIN_ITEM_INTERACTIONS].index)]
        if len(nd) == len(df) or len(nd) == 0:
            df = nd
            break
        df = nd
    uc = df["orig_user_id"].value_counts()
    df = df[df["orig_user_id"].isin(uc[uc >= MIN_USER_INTERACTIONS].index)]

    df["user_id"] = df["orig_user_id"].astype("category").cat.codes
    df["item_id"] = df["item_orig"].astype("category").cat.codes
    lo, hi = df["rating"].min(), df["rating"].max()
    df["rating_norm"] = (df["rating"] - lo) / (hi - lo)
    train, test = train_test_split(df, test_size=0.2, random_state=RANDOM_STATE,
                                   stratify=df["user_id"])
    return df, train, test


def build_features(items: pd.DataFrame, df: pd.DataFrame):
    """TF-IDF（title+subtitle+extra）并按 item_id 重排，行号即 item_id。
    meta 保留物品表的全部附加列（如课程的 platform/price/num_subscribers）。"""
    orig2iid = df.drop_duplicates("item_orig").set_index("item_orig")["item_id"].to_dict()
    items = items[items["item_orig"].isin(orig2iid)].copy()
    items["item_id"] = items["item_orig"].map(orig2iid).astype(int)
    items = items.sort_values("item_id")
    text = (items["title"].fillna("") + " " + items["subtitle"].fillna("")
            + " " + items["extra"].fillna(""))
    vec = TfidfVectorizer(max_features=20000, stop_words="english",
                          ngram_range=(1, 2), min_df=2)
    tfidf = vec.fit_transform(text)
    meta = items.drop(columns=["item_orig"]).reset_index(drop=True)
    return tfidf, meta, vec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["movies", "courses"], required=True)
    ap.add_argument("--ml_dir", default="./data/ml-latest-small")
    ap.add_argument("--courses_csv", default="./data/udemy_courses.csv")
    ap.add_argument("--n_users", type=int, default=2500, help="课程域模拟用户数")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out_dir", default="")
    args = ap.parse_args()
    out_dir = args.out_dir or f"./data/processed_{args.domain}"
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    if args.domain == "movies":
        print(">> 读取 MovieLens ml-latest-small ...")
        ratings, items = load_movies_raw(args.ml_dir)
    else:
        print(f">> 读取 Udemy 真实课程目录 {args.courses_csv} ...")
        items = load_courses_raw(args.courses_csv)
        print(f"   {len(items)} 门课程；模拟 {args.n_users} 名用户评分 ...")
        ratings = simulate_course_ratings(rng, items, args.n_users)

    df, train, test = clean_and_split(ratings)
    print(f">> 清洗后评分 {len(df)} 条，用户 {df['user_id'].nunique()}，"
          f"物品 {df['item_id'].nunique()}")
    train.to_csv(os.path.join(out_dir, "ratings_train.csv"), index=False)
    test.to_csv(os.path.join(out_dir, "ratings_test.csv"), index=False)
    df.to_csv(os.path.join(out_dir, "ratings_all.csv"), index=False)

    tfidf, meta, vec = build_features(items, df)
    save_npz(os.path.join(out_dir, "item_tfidf.npz"), tfidf)
    joblib.dump(vec, os.path.join(out_dir, "item_vectorizer.joblib"))
    meta.to_csv(os.path.join(out_dir, "items_meta.csv"), index=False)

    print(f">> 完成！输出目录 {out_dir}")


if __name__ == "__main__":
    main()
