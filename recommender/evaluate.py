# -*- coding: utf-8 -*-
"""
算法效果评估与对比（任务4）

指标：
    Precision@K   推荐列表中命中的比例
    Recall@K      用户测试集中正反馈物品被覆盖的比例
    HitRate@K     推荐列表至少命中一次的用户比例
    NDCG@K        考虑排序位置的归一化折损累计增益（二值相关性）
    Coverage      推荐结果覆盖物品目录的比例（多样性/长尾能力）

用法：
    python evaluate.py --processed_dir ./data/processed --k 10 --sample 1000 --out_dir ./reports

输出：
    reports/metrics.csv    各算法指标明细
    reports/report.md      对比报告（可直接贴进论文）
    reports/chart_*.png    对比图
"""
from __future__ import annotations

import argparse
import os
import time

import numpy as np
import pandas as pd
from scipy import sparse

from algorithms import UserCF, ItemCF, ContentBased, MostPopular


# ---------------------------------------------------------------------------
# 指标计算（对单个用户）
# ---------------------------------------------------------------------------
def user_metrics(rec_items: list[int], relevant: set[int], k: int):
    """返回 (hits, precision, recall, ndcg)；rec_items 为推荐列表的 item_id"""
    rec_k = rec_items[:k]
    hits = len(set(rec_k) & relevant)
    precision = hits / k if k else 0.0
    recall = hits / len(relevant) if relevant else 0.0
    dcg = sum(1.0 / np.log2(r + 2) for r, i in enumerate(rec_k) if i in relevant)
    idcg = sum(1.0 / np.log2(r + 2) for r in range(min(len(relevant), k)))
    ndcg = dcg / idcg if idcg > 0 else 0.0
    return hits, precision, recall, ndcg


# ---------------------------------------------------------------------------
# 评估主流程
# ---------------------------------------------------------------------------
def evaluate_model(model, test_pos: dict[int, set[int]], catalog_size: int, k: int):
    rows = []
    recommended_items = set()
    t0 = time.time()
    for uid, relevant in test_pos.items():
        recs = model.recommend(uid, k)
        items = [i for i, _ in recs]
        recommended_items.update(items)
        hits, prec, rec, ndcg = user_metrics(items, relevant, k)
        rows.append({"user_id": uid, "hits": hits, "precision": prec,
                     "recall": rec, "ndcg": ndcg, "hit": 1 if hits > 0 else 0})
    df = pd.DataFrame(rows)
    return {
        "algorithm": model.name,
        "Precision@K": df["precision"].mean() if len(df) else 0.0,
        "Recall@K": df["recall"].mean() if len(df) else 0.0,
        "HitRate@K": df["hit"].mean() if len(df) else 0.0,
        "NDCG@K": df["ndcg"].mean() if len(df) else 0.0,
        "Coverage": len(recommended_items) / catalog_size if catalog_size else 0.0,
        "users_evaluated": len(df),
        "eval_time_sec": round(time.time() - t0, 1),
    }


def make_charts(metrics_df: pd.DataFrame, out_dir: str, k: int):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("!! 未安装 matplotlib，跳过图表生成")
        return
    for metric in ["Precision@K", "Recall@K", "HitRate@K", "NDCG@K"]:
        ax = metrics_df.set_index("algorithm")[metric].plot.bar(
            rot=0, figsize=(7, 4), legend=False,
            title=f"{metric.replace('@K', f'@{k}')} comparison",
        )
        ax.set_ylabel(metric.replace("@K", f"@{k}"))
        ax.bar_label(ax.containers[0], fmt="%.3f")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f"chart_{metric.split('@')[0].lower()}.png"), dpi=150)
        plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed_dir", default="./data/processed")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--sample", type=int, default=1000, help="抽样评估的用户数，0=全部")
    ap.add_argument("--threshold", type=float, default=7, help="评分>=该值视为正反馈")
    ap.add_argument("--n_neighbors", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out_dir", default="./reports")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    # 1) 加载离线数据
    train = pd.read_csv(os.path.join(args.processed_dir, "ratings_train.csv"))
    test = pd.read_csv(os.path.join(args.processed_dir, "ratings_test.csv"))
    tfidf = sparse.load_npz(os.path.join(args.processed_dir, "item_tfidf.npz"))
    items_meta = pd.read_csv(os.path.join(args.processed_dir, "items_meta.csv"))

    # 2) 测试集正反馈（ground truth）：评分列名兼容 books(Book-Rating) 与通用域(rating)
    rating_col = "rating" if "rating" in test.columns else "Book-Rating"
    test_pos_df = test[test[rating_col] >= args.threshold]
    test_pos = test_pos_df.groupby("user_id")["item_id"].apply(set).to_dict()
    if args.sample and len(test_pos) > args.sample:
        rng = np.random.default_rng(args.seed)
        users = rng.choice(sorted(test_pos), size=args.sample, replace=False)
        test_pos = {u: test_pos[u] for u in users}
    print(f">> 评估用户数: {len(test_pos)}，K={args.k}，正反馈阈值>={args.threshold}")

    # 3) 训练四个算法
    models = [
        UserCF(n_neighbors=args.n_neighbors),
        ItemCF(n_neighbors=args.n_neighbors),
        ContentBased(tfidf, items_meta["item_id"].values),
        MostPopular(),
    ]
    catalog_size = int(max(train["item_id"].max(), test["item_id"].max())) + 1

    results = []
    for m in models:
        print(f">> 训练 {m.name} ...")
        m.fit(train)
        r = evaluate_model(m, test_pos, catalog_size, args.k)
        print("   ", {k2: (round(v, 4) if isinstance(v, float) else v) for k2, v in r.items()})
        results.append(r)

    # 4) 输出报告
    res_df = pd.DataFrame(results)
    res_df.to_csv(os.path.join(args.out_dir, "metrics.csv"), index=False, encoding="utf-8-sig")

    md = [
        f"# 推荐算法对比实验报告（K={args.k}）", "",
        f"- 评估用户数：{len(test_pos)}（测试集评分>={args.threshold}视为正反馈）",
        f"- 协同过滤近邻数 KNN = {args.n_neighbors}",
        f"- 训练集交互数：{len(train)}，物品目录：{catalog_size}", "",
        "| 算法 | Precision@K | Recall@K | HitRate@K | NDCG@K | Coverage |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        md.append("| {} | {:.4f} | {:.4f} | {:.4f} | {:.4f} | {:.4f} |".format(
            r["algorithm"], r["Precision@K"], r["Recall@K"],
            r["HitRate@K"], r["NDCG@K"], r["Coverage"]))
    best = res_df.loc[res_df["NDCG@K"].idxmax(), "algorithm"]
    md += ["", f"**结论**：综合 NDCG@{args.k} 表现最好的算法是 **{best}**。", ""]
    with open(os.path.join(args.out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    make_charts(res_df, args.out_dir, args.k)
    print(f">> 完成！报告输出到 {args.out_dir}/report.md, metrics.csv, chart_*.png")


if __name__ == "__main__":
    main()
