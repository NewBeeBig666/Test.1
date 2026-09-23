# -*- coding: utf-8 -*-
"""
多域算法评估与跨域模拟实验（阶段5）

一、三域 × 4算法离线评估（books / courses / movies × UserCF / ItemCF / ContentBased / MostPopular）
    统一正反馈阈值：rating_norm >= 0.7（各域映射：图书 Book-Rating>=8、电影 >=4.0星、课程 >=3.8星）
    指标：Precision@K / Recall@K / HitRate@K / NDCG@K / Coverage

二、跨域模拟实验（CrossDomain，论文亮点）
    三个公开数据集的用户互不重叠，无真实的跨域用户测试集，故构造配对模拟：
      - 相似配对（CrossDomain-Sim）：目标域(电影)测试用户 x 源域(图书)用户，
        在统一 TF-IDF 空间中取画像余弦最相似的图书用户，"嫁接"其全部图书行为
        构造统一画像 -> 推荐电影 -> 对照该电影用户的真实测试集评估
      - 随机配对（CrossDomain-Random）：随机图书用户作负对照
      - 参照：单域 ContentBased（本人电影历史）/ MostPopular
    若 CrossDomain-Sim 显著优于随机配对并接近单域内容推荐，说明统一标签空间的
    跨域迁移携带真实偏好信号。（局限在 report.md 中如实说明）

三、跨域词表重叠度分析：三域词表两两 Jaccard + 共有高频词

输出 reports_all/：all_metrics.csv / cross_domain_metrics.csv / report.md / chart_*.png

用法：py -3 evaluate_all.py --k 10 --sample 1000
"""
from __future__ import annotations

import argparse
import os
import time

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse import load_npz

from algorithms import UserCF, ItemCF, ContentBased, MostPopular, CrossDomain
from evaluate import user_metrics

ROOT = os.path.dirname(os.path.abspath(__file__))
DOMAINS = {
    "books": os.path.join(ROOT, "data", "processed_real"),
    "movies": os.path.join(ROOT, "data", "processed_movies"),
    "courses": os.path.join(ROOT, "data", "processed_courses"),
}
GLOBAL_DIR = os.path.join(ROOT, "data", "processed_global")
THRESHOLD = 0.7          # rating_norm 正反馈阈值（三域统一）
N_NEIGHBORS = 20
SEED = 42


def evaluate_model(model, test_pos: dict, catalog_size: int, k: int):
    rows, recommended = [], set()
    t0 = time.time()
    for uid, relevant in test_pos.items():
        recs = model.recommend(uid, k)
        items = [i for i, _ in recs]
        recommended.update(items)
        hits, prec, rec, ndcg = user_metrics(items, relevant, k)
        rows.append({"hits": hits, "precision": prec, "recall": rec,
                     "ndcg": ndcg, "hit": 1 if hits > 0 else 0})
    df = pd.DataFrame(rows)
    return {
        "Precision@K": df["precision"].mean() if len(df) else 0.0,
        "Recall@K": df["recall"].mean() if len(df) else 0.0,
        "HitRate@K": df["hit"].mean() if len(df) else 0.0,
        "NDCG@K": df["ndcg"].mean() if len(df) else 0.0,
        "Coverage": len(recommended) / catalog_size if catalog_size else 0.0,
        "users_evaluated": len(df),
        "eval_time_sec": round(time.time() - t0, 1),
    }


def load_domain(domain: str):
    d = DOMAINS[domain]
    train = pd.read_csv(os.path.join(d, "ratings_train.csv"))
    test = pd.read_csv(os.path.join(d, "ratings_test.csv"))
    tfidf = load_npz(os.path.join(d, "item_tfidf.npz"))
    items = pd.read_csv(os.path.join(d, "items_meta.csv"))
    return train, test, tfidf, items


def positive_test(test: pd.DataFrame, sample: int, rng):
    pos = test[test["rating_norm"] >= THRESHOLD].groupby("user_id")["item_id"].apply(set).to_dict()
    if sample and len(pos) > sample:
        users = rng.choice(sorted(pos), size=sample, replace=False)
        pos = {u: pos[u] for u in users}
    return pos


# ---------------------------------------------------------------------------
# 一、三域 × 4算法
# ---------------------------------------------------------------------------
def run_domain_eval(domain: str, k: int, sample: int, rng) -> list[dict]:
    print(f"\n===== 域内评估 [{domain}] =====")
    train, test, tfidf, items = load_domain(domain)
    test_pos = positive_test(test, sample, rng)
    catalog = int(max(train["item_id"].max(), test["item_id"].max())) + 1
    print(f"训练交互 {len(train)}，正反馈测试用户 {len(test_pos)}，K={k}，阈值 rating_norm>={THRESHOLD}")

    models = [UserCF(N_NEIGHBORS), ItemCF(N_NEIGHBORS),
              ContentBased(tfidf, items["item_id"].values), MostPopular()]
    results = []
    for m in models:
        t0 = time.time()
        m.fit(train)
        r = evaluate_model(m, test_pos, catalog, k)
        r.update({"domain": domain, "algorithm": m.name, "fit_time_sec": round(time.time() - t0, 1)})
        print("  {:<13} P@{}={:.4f} R={:.4f} HR={:.4f} NDCG={:.4f} Cov={:.4f}".format(
            m.name, k, r["Precision@K"], r["Recall@K"], r["HitRate@K"], r["NDCG@K"], r["Coverage"]))
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# 二、跨域模拟实验（目标域 movies / 源域 books）
# ---------------------------------------------------------------------------
def build_profiles(ratings: pd.DataFrame, cross: CrossDomain):
    """ratings(user_id,item_id,rating_norm) -> 稀疏画像矩阵（行对应用户顺序）+ 用户列表"""
    by_user = ratings.groupby("user_id")[["item_id", "rating_norm"]]
    users, rows_arr, ws_arr, lens = [], [], [], []
    for uid, g in by_user:
        users.append(int(uid))
        for i, w in zip(g["item_id"].values, g["rating_norm"].values):
            rows_arr.append(("books", int(i), float(w)))
        lens.append(len(g))
    # 用 cross.profile 的行映射：逐用户构建
    profs = []
    start = 0
    for n in lens:
        inter = rows_arr[start:start + n]
        p = cross.profile(inter)
        profs.append(p if p is not None else sparse.csr_matrix((1, cross.tfidf.shape[1])))
        start += n
    return users, sparse.vstack(profs).tocsr()


def run_cross_experiment(k: int, sample: int, rng) -> list[dict]:
    print("\n===== 跨域模拟实验 [books -> movies] =====")
    cross = CrossDomain(load_npz(os.path.join(GLOBAL_DIR, "global_tfidf.npz")),
                        pd.read_csv(os.path.join(GLOBAL_DIR, "items_global.csv")))
    train_m, test_m, tfidf_m, items_m = load_domain("movies")
    train_b, _, _, _ = load_domain("books")

    test_pos = positive_test(test_m, sample, rng)
    eval_users = sorted(test_pos)

    # 电影用户画像（本人电影训练行为）与图书用户画像（全部图书行为）
    movie_train = train_m[train_m["user_id"].isin(eval_users)]
    mu, P_movie = build_profiles(movie_train, cross)
    bu, P_book = build_profiles(train_b, cross)
    mu_idx = {u: r for r, u in enumerate(mu)}
    bu_idx = {u: r for r, u in enumerate(bu)}

    # 相似度矩阵：eval电影用户 x 全体图书用户（稀疏点积）
    S = (P_movie @ P_book.T).tocsc()
    book_user_ids = np.array(bu)

    def evaluate(fn, name):
        rows = []
        t0 = time.time()
        for uid in eval_users:
            recs = cross.recommend(fn(uid), "movies", k)
            items = [i for i, _ in recs]
            hits, prec, rec, ndcg = user_metrics(items, test_pos[uid], k)
            rows.append({"hits": hits, "precision": prec, "recall": rec,
                         "ndcg": ndcg, "hit": 1 if hits > 0 else 0})
        df = pd.DataFrame(rows)
        print("  {:<22} P@{}={:.4f} HR={:.4f} NDCG={:.4f}".format(
            name, k, df["precision"].mean(), df["hit"].mean(), df["ndcg"].mean()))
        return {"algorithm": name,
                "Precision@K": df["precision"].mean() if len(df) else 0.0,
                "Recall@K": df["recall"].mean() if len(df) else 0.0,
                "HitRate@K": df["hit"].mean() if len(df) else 0.0,
                "NDCG@K": df["ndcg"].mean() if len(df) else 0.0,
                "users_evaluated": len(df), "eval_time_sec": round(time.time() - t0, 1)}

    results = []

    # 相似配对：画像余弦最大的图书用户，嫁接其全部图书行为
    def sim_source(uid):
        row = S[:, mu_idx[uid]]
        best = int(row.indices[np.argmax(row.data)]) if row.nnz else int(rng.integers(len(bu)))
        return [("books", int(i), float(w))
                for i, w in zip(train_b[train_b["user_id"] == bu[best]]["item_id"].values,
                               train_b[train_b["user_id"] == bu[best]]["rating_norm"].values)]
    results.append(evaluate(sim_source, "CrossDomain-Sim"))

    # 随机配对（负对照）
    def random_source(uid):
        j = int(rng.integers(len(bu)))
        g = train_b[train_b["user_id"] == bu[j]]
        return [("books", int(i), float(w)) for i, w in zip(g["item_id"].values, g["rating_norm"].values)]
    results.append(evaluate(random_source, "CrossDomain-Random"))

    # 参照：单域内容推荐（本人电影历史）
    cb = ContentBased(tfidf_m, items_m["item_id"].values).fit(train_m)
    rows = []
    for uid in eval_users:
        recs = cb.recommend(uid, k)
        hits, prec, rec, ndcg = user_metrics([i for i, _ in recs], test_pos[uid], k)
        rows.append({"hits": hits, "precision": prec, "recall": rec,
                     "ndcg": ndcg, "hit": 1 if hits > 0 else 0})
    df = pd.DataFrame(rows)
    results.append({"algorithm": "ContentBased(单域参照)",
                    "Precision@K": df["precision"].mean() if len(df) else 0.0,
                    "Recall@K": df["recall"].mean() if len(df) else 0.0,
                    "HitRate@K": df["hit"].mean() if len(df) else 0.0,
                    "NDCG@K": df["ndcg"].mean() if len(df) else 0.0,
                    "users_evaluated": len(df), "eval_time_sec": 0})
    print("  {:<22} P@{}={:.4f} HR={:.4f} NDCG={:.4f}".format(
        "ContentBased(单域参照)", k, df["precision"].mean(), df["hit"].mean(), df["ndcg"].mean()))
    return results


# ---------------------------------------------------------------------------
# 三、跨域词表重叠度
# ---------------------------------------------------------------------------
def vocab_overlap() -> tuple[dict, list]:
    vocabs, dfs = {}, {}
    for domain, d in DOMAINS.items():
        vec = joblib.load(os.path.join(d, "item_vectorizer.joblib"))
        vocabs[domain] = set(vec.vocabulary_.keys())
        dfs[domain] = np.asarray(vec.idf_ if hasattr(vec, "idf_") else np.ones(len(vec.vocabulary_)))
    pairs = {}
    domains = sorted(vocabs)
    for i in range(len(domains)):
        for j in range(i + 1, len(domains)):
            a, b = domains[i], domains[j]
            inter = vocabs[a] & vocabs[b]
            pairs[f"{a}∩{b}"] = {
                "jaccard": round(len(inter) / len(vocabs[a] | vocabs[b]), 4),
                "shared": len(inter),
            }
    # 全域共有高频词（存在于全部三域词表且在全局词表中的词，按全局 IDF 升序 = 跨域信号最强）
    gvec = joblib.load(os.path.join(GLOBAL_DIR, "global_vectorizer.joblib"))
    gdf = np.asarray(gvec.idf_)
    gvocab = gvec.vocabulary_  # word -> index
    common = set.intersection(*vocabs.values()) & set(gvocab.keys())
    common_sorted = sorted(common, key=lambda w: gdf[gvocab[w]])[:24]
    return pairs, common_sorted


# ---------------------------------------------------------------------------
# 图表
# ---------------------------------------------------------------------------
def make_charts(df: pd.DataFrame, out_dir: str, k: int):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("!! 未安装 matplotlib，跳过图表生成")
        return
    metrics = ["Precision@K", "Recall@K", "HitRate@K", "NDCG@K"]
    for metric in metrics:
        piv = df.pivot(index="algorithm", columns="domain", values=metric)
        order = [a for a in ["UserCF", "ItemCF", "ContentBased", "MostPopular"] if a in piv.index]
        piv = piv.loc[order]
        ax = piv.plot.bar(rot=0, figsize=(9, 4.5), width=0.78,
                          color=["#a06a3b", "#3a4a9f", "#00713d"])
        ax.set_title(f"{metric.replace('@K', f'@{k}')} across domains")
        ax.set_ylabel(metric.replace("@K", f"@{k}"))
        for c in ax.containers:
            ax.bar_label(c, fmt="%.3f", fontsize=8)
        ax.legend(title="domain")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f"chart_{metric.split('@')[0].lower()}.png"), dpi=150)
        plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--sample", type=int, default=1000)
    ap.add_argument("--out_dir", default=os.path.join(ROOT, "reports_all"))
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    rng = np.random.default_rng(SEED)
    k = args.k

    all_rows = []
    for domain in DOMAINS:
        all_rows.extend(run_domain_eval(domain, k, args.sample, rng))
    res_df = pd.DataFrame(all_rows)
    res_df.to_csv(os.path.join(args.out_dir, "all_metrics.csv"), index=False, encoding="utf-8-sig")

    cross_rows = run_cross_experiment(k, args.sample, rng)
    cross_df = pd.DataFrame(cross_rows)
    cross_df.to_csv(os.path.join(args.out_dir, "cross_domain_metrics.csv"), index=False, encoding="utf-8-sig")

    pairs, common_words = vocab_overlap()

    # ---------------- report.md ----------------
    md = [f"# 三域算法效果对比实验报告（K={k}）", "",
          f"- 正反馈阈值：rating_norm >= {THRESHOLD}（三域统一；对应图书评分>=8/10、电影>=4.0/5、课程>=3.8/5）",
          f"- 协同过滤近邻数 KNN = {N_NEIGHBORS}；每域抽样评估用户数 <= {args.sample}",
          f"- 数据：Book-Crossing（图书，真实）/ MovieLens ml-latest-small（电影，真实）/ Udemy 目录（课程，真实物品+模拟评分）",
          "", "## 一、各域算法对比", ""]
    for domain in DOMAINS:
        md.append(f"### {domain}")
        md.append("| 算法 | Precision@K | Recall@K | HitRate@K | NDCG@K | Coverage |")
        md.append("|---|---|---|---|---|---|")
        sub = res_df[res_df["domain"] == domain]
        for r in sub.to_dict("records"):
            md.append("| {} | {:.4f} | {:.4f} | {:.4f} | {:.4f} | {:.4f} |".format(
                r["algorithm"], r["Precision@K"], r["Recall@K"],
                r["HitRate@K"], r["NDCG@K"], r["Coverage"]))
        best = sub.loc[sub["NDCG@K"].idxmax(), "algorithm"]
        md += ["", f"**{domain} 域最优（NDCG@{k}）：{best}**", ""]
    md += ["## 二、跨域模拟实验（books → movies）", "",
           "| 实验 | Precision@K | Recall@K | HitRate@K | NDCG@K |", "|---|---|---|---|---|"]
    for r in cross_rows:
        md.append("| {} | {:.4f} | {:.4f} | {:.4f} | {:.4f} |".format(
            r["algorithm"], r["Precision@K"], r["Recall@K"], r["HitRate@K"], r["NDCG@K"]))
    md += ["",
           "实验设计：三域数据集用户互不重叠，无法获得真实跨域用户测试集。本实验将电影测试用户"
           "与统一 TF-IDF 空间中画像最相似的图书用户配对（相似配对），嫁接其全部图书行为构造统一画像后"
           "推荐电影，并与随机配对（负对照）、单域内容推荐（参照）比较。",
           "",
           "**解读**：若 CrossDomain-Sim 显著优于 CrossDomain-Random 并接近单域 ContentBased，"
           "说明统一标签空间中的跨域兴趣迁移携带真实偏好信号；线上注册用户在三个模块的真实行为"
           "（跨域画像）是本机制的实际应用场景。",
           "", "## 三、跨域词表重叠度（统一空间可行性）", ""]
    for key, v in pairs.items():
        md.append(f"- {key}：共有词 {v['shared']} 个，Jaccard = {v['jaccard']}")
    md += ["", f"三域共有高频词（按全局 IDF 升序，跨域信号最强的词）：",
           "`" + "`, `".join(common_words) + "`", ""]
    with open(os.path.join(args.out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    make_charts(res_df, args.out_dir, k)
    print(f"\n>> 完成！报告输出到 {args.out_dir}/")


if __name__ == "__main__":
    main()
