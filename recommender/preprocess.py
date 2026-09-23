# -*- coding: utf-8 -*-
"""
数据获取与预处理：Book-Crossing 数据集（天池 https://tianchi.aliyun.com/dataset/31828）
功能：
  1. 数据清洗（编码、去重、过滤低频用户/物品）
  2. 评分归一化（Min-Max 到 0~1）
  3. 内容特征工程（书名+作者+出版社 TF-IDF 向量化）
  4. 训练/测试集划分（按时间留一法）
输出到 data/processed/ 目录，供 UserCF/ItemCF/ContentBased 算法直接读取。

依赖: pip install pandas numpy scikit-learn
用法: python preprocess.py --data_dir ./data/raw
"""
import os
import argparse
import joblib
import numpy as np
import pandas as pd
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split

MIN_USER_INTERACTIONS = 5   # 过滤交互次数少于5的用户（冷启动噪声）
MIN_ITEM_INTERACTIONS = 5   # 过滤交互次数少于5的图书
RANDOM_STATE = 42


def load_raw(data_dir):
    """Book-Crossing 原始文件为 latin-1 编码、分号分隔"""
    ratings = pd.read_csv(
        os.path.join(data_dir, "BX-Book-Ratings.csv"),
        sep=";", encoding="latin-1", escapechar="\\",
    )
    books = pd.read_csv(
        os.path.join(data_dir, "BX-Books.csv"),
        sep=";", encoding="latin-1", escapechar="\\",
        usecols=["ISBN", "Book-Title", "Book-Author",
                 "Year-Of-Publication", "Publisher", "Image-URL-M"],
        dtype=str,
    )
    users = pd.read_csv(
        os.path.join(data_dir, "BX-Users.csv"),
        sep=";", encoding="latin-1", escapechar="\\",
    )
    ratings.columns = [c.strip() for c in ratings.columns]
    books.columns = [c.strip() for c in books.columns]
    users.columns = [c.strip() for c in users.columns]
    return ratings, books, users


def clean_ratings(ratings, books):
    """去重、剔除无效评分、只保留在图书表中有元数据的记录，并做ID编码"""
    df = ratings[ratings["Book-Rating"] > 0].copy()   # 0 表示隐式浏览，显式算法先剔除
    df = df.drop_duplicates(subset=["User-ID", "ISBN"])
    df = df.merge(books[["ISBN"]], on="ISBN", how="inner")

    # 迭代过滤低频用户/物品直到收敛，缓解稀疏
    while True:
        user_cnt = df["User-ID"].value_counts()
        df = df[df["User-ID"].isin(user_cnt[user_cnt >= MIN_USER_INTERACTIONS].index)]
        item_cnt = df["ISBN"].value_counts()
        new_df = df[df["ISBN"].isin(item_cnt[item_cnt >= MIN_ITEM_INTERACTIONS].index)]
        if len(new_df) == len(df) or len(new_df) == 0:
            df = new_df
            break
        df = new_df
    # 末轮物品过滤可能使用户数再次降到阈值下，仅过滤用户一次，
    # 保证分层抽样时每个用户至少 MIN_USER_INTERACTIONS 条交互
    user_cnt = df["User-ID"].value_counts()
    df = df[df["User-ID"].isin(user_cnt[user_cnt >= MIN_USER_INTERACTIONS].index)]

    # 重编码为连续整数ID，便于构建矩阵
    df["user_id"] = df["User-ID"].astype("category").cat.codes
    df["item_id"] = df["ISBN"].astype("category").cat.codes
    return df


def normalize_rating(df):
    """评分 Min-Max 归一化到 0~1，保留原始列用于评估"""
    lo, hi = df["Book-Rating"].min(), df["Book-Rating"].max()
    df["rating_norm"] = (df["Book-Rating"] - lo) / (hi - lo)
    return df


def build_item_tfidf(books, df):
    """对书名+作者+出版社做 TF-IDF，得到物品内容向量（基于内容推荐用）"""
    meta = books.dropna(subset=["Book-Title", "Book-Author", "Publisher"]).copy()
    meta["text"] = (meta["Book-Title"].fillna("") + " "
                    + meta["Book-Author"].fillna("") + " "
                    + meta["Publisher"].fillna(""))
    vec = TfidfVectorizer(
        max_features=20000, stop_words="english",
        ngram_range=(1, 2), min_df=2,
    )
    tfidf = vec.fit_transform(meta["text"])
    meta = meta.reset_index(drop=True)
    # 只保留清洗后在交互表中出现的图书，并映射到 item_id
    isbn2iid = df.drop_duplicates("ISBN").set_index("ISBN")["item_id"].to_dict()
    keep = meta["ISBN"].map(isbn2iid)
    mask = keep.notna()
    item_meta = meta[mask].assign(item_id=keep[mask].astype(int))
    return tfidf[mask.values], item_meta, vec


def build_user_profile(df, tfidf, item_meta):
    """用户画像：其交互图书内容向量的加权平均（行为 x 内容 => 兴趣标签向量）"""
    from scipy.sparse import csr_matrix, vstack
    iid2row = {iid: r for r, iid in enumerate(item_meta["item_id"].values)}
    profiles = {}
    for uid, grp in df.groupby("user_id"):
        rows, ws = [], []
        for iid, w in zip(grp["item_id"], grp["rating_norm"]):
            r = iid2row.get(iid)
            if r is not None:
                rows.append(r)
                ws.append(w)
        if rows:
            profiles[uid] = csr_matrix(np.asarray(ws)) @ tfidf[rows]
    return profiles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_dir", default="./data/raw", help="原始CSV目录")
    ap.add_argument("--out_dir", default="./data/processed")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    print(">> 读取原始数据 ...")
    ratings, books, users = load_raw(args.data_dir)
    print(f"   原始评分 {len(ratings)} 条")

    print(">> 清洗与过滤 ...")
    df = clean_ratings(ratings, books)
    df = normalize_rating(df)
    print(f"   清洗后评分 {len(df)} 条，用户 {df['user_id'].nunique()}，"
          f"图书 {df['item_id'].nunique()}")

    print(">> 划分训练/测试集 ...")
    train, test = train_test_split(
        df, test_size=0.2, random_state=RANDOM_STATE, stratify=df["user_id"],
    )
    train.to_csv(os.path.join(args.out_dir, "ratings_train.csv"), index=False)
    test.to_csv(os.path.join(args.out_dir, "ratings_test.csv"), index=False)
    df.to_csv(os.path.join(args.out_dir, "ratings_all.csv"), index=False)

    print(">> 物品 TF-IDF 内容特征 ...")
    tfidf, item_meta, vec = build_item_tfidf(books, df)
    save_npz(os.path.join(args.out_dir, "item_tfidf.npz"), tfidf)
    joblib.dump(vec, os.path.join(args.out_dir, "item_vectorizer.joblib"))
    item_meta["image_url"] = item_meta["Image-URL-M"].fillna("")
    item_meta[["item_id", "ISBN", "Book-Title", "Book-Author", "Publisher",
               "image_url"]] \
        .to_csv(os.path.join(args.out_dir, "items_meta.csv"), index=False)

    print(">> 用户画像（兴趣向量） ...")
    profiles = build_user_profile(df, tfidf, item_meta)
    prof_mat = vstack(list(profiles.values()))
    pd.DataFrame({"user_id": list(profiles.keys())}) \
        .to_csv(os.path.join(args.out_dir, "user_profile_ids.csv"), index=False)
    save_npz(os.path.join(args.out_dir, "user_profiles.npz"), prof_mat)

    print(">> 用户属性画像标签 ...")
    users = users.copy()
    users["Age"] = pd.to_numeric(users["Age"], errors="coerce")
    users["age_group"] = pd.cut(
        users["Age"], bins=[0, 18, 25, 35, 50, 100],
        labels=["未成年", "18-25", "26-35", "36-50", "50+"],
    )
    users["country"] = users["Location"].str.split(",").str[-1].str.strip()
    users.to_csv(os.path.join(args.out_dir, "users_meta.csv"), index=False)

    print("完成！输出目录:", args.out_dir)


if __name__ == "__main__":
    from scipy.sparse import vstack  # noqa: F401
    main()
