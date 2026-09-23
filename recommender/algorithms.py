# -*- coding: utf-8 -*-
"""
推荐算法实现（任务2 + 任务3的核心模块）

包含四种算法，统一接口：
    fit(ratings_df)          ratings_df 需含 user_id / item_id / rating_norm 三列
    recommend(user_id, n)    返回 [(item_id, score), ...] 按分数降序

算法清单：
    UserCF        基于用户的协同过滤（余弦相似度 + Top-K 近邻）
    ItemCF        基于物品的协同过滤
    ContentBased  基于内容推荐（TF-IDF 物品向量 + 用户兴趣画像）
    MostPopular   热门基线（对比实验的下界参照 / 冷启动兜底）

相似度计算与近邻检索使用 scikit-learn 的 NearestNeighbors / cosine_similarity。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics.pairwise import cosine_similarity


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------
def build_user_item_matrix(ratings_df: pd.DataFrame) -> sparse.csr_matrix:
    """由评分DataFrame构建 users x items 的稀疏评分矩阵（值为归一化评分）"""
    n_users = int(ratings_df["user_id"].max()) + 1
    n_items = int(ratings_df["item_id"].max()) + 1
    return sparse.csr_matrix(
        (
            ratings_df["rating_norm"].astype(float).values,
            (ratings_df["user_id"].astype(int).values, ratings_df["item_id"].astype(int).values),
        ),
        shape=(n_users, n_items),
    )


def _knn_graph(matrix: sparse.csr_matrix, k: int):
    """对 matrix 的每一行检索 Top-K 余弦近邻。

    返回 (idx, sim)：idx 每行的近邻行号，sim 为对应的相似度（夹在 [0,1]）。
    自身会被置零相似度而非删除列，避免重复行导致“自己不在第一列”的问题。
    """
    n = matrix.shape[0]
    k = min(k + 1, n)  # +1 是为了容纳自身
    nn = NearestNeighbors(n_neighbors=k, metric="cosine", algorithm="brute")
    nn.fit(matrix)
    dist, idx = nn.kneighbors(matrix)
    sim = np.clip(1.0 - dist, 0.0, 1.0)
    sim[np.arange(n)[:, None] == idx] = 0.0  # 屏蔽自身
    return idx.astype(np.int32), sim.astype(np.float32)


def _top_n(scores: np.ndarray, seen: np.ndarray, n: int):
    """从分数向量中选出未见过（seen）的 Top-N，返回 [(item_id, score)]"""
    if len(scores) == 0:
        return []
    scores = scores.copy()
    if len(seen):
        scores[seen] = -np.inf
    k = min(n, scores.size)
    if k <= 0:
        return []
    top = np.argpartition(-scores, k - 1)[:k]
    top = top[np.argsort(-scores[top])]
    return [(int(i), float(scores[i])) for i in top if np.isfinite(scores[i])]


# ---------------------------------------------------------------------------
# UserCF：基于用户的协同过滤
# ---------------------------------------------------------------------------
class UserCF:
    """score(u, i) = Σ_{v∈TopK近邻用户} sim(u,v) * r(v,i)"""

    name = "UserCF"

    def __init__(self, n_neighbors: int = 20):
        self.k = n_neighbors

    def fit(self, ratings_df: pd.DataFrame):
        self.R = build_user_item_matrix(ratings_df)
        # 用户相似度：对用户向量（评分行）做余弦近邻检索
        self.neigh_idx, self.neigh_sim = _knn_graph(self.R, self.k)
        return self

    def recommend(self, user_id: int, n: int = 10):
        if user_id < 0 or user_id >= self.R.shape[0]:
            return []
        ru = self.R[user_id]
        if ru.nnz == 0:
            return []
        nb, sims = self.neigh_idx[user_id], self.neigh_sim[user_id]
        # (k,) x (k, n_items) -> (n_items,) 加权汇总近邻用户的评分
        scores = np.asarray(self.R[nb].T @ sims).ravel()
        return _top_n(scores, ru.indices, n)


# ---------------------------------------------------------------------------
# ItemCF：基于物品的协同过滤
# ---------------------------------------------------------------------------
class ItemCF:
    """score(u, i) = Σ_{j∈u交互过的物品} sim(i,j) * r(u,j)"""

    name = "ItemCF"

    def __init__(self, n_neighbors: int = 20):
        self.k = n_neighbors

    def fit(self, ratings_df: pd.DataFrame):
        self.R = build_user_item_matrix(ratings_df)
        # 物品相似度：转置后对物品向量（评分列）做余弦近邻检索
        items = self.R.T.tocsr()
        self.item_nb, self.item_sim = _knn_graph(items, self.k)
        return self

    def recommend(self, user_id: int, n: int = 10):
        if user_id < 0 or user_id >= self.R.shape[0]:
            return []
        ru = self.R[user_id]
        if ru.nnz == 0:
            return []
        scores = np.zeros(self.R.shape[1], dtype=np.float64)
        for j, r in zip(ru.indices, ru.data):
            # 用户喜欢 j，则 j 的近邻物品获得 sim*r 的加分
            np.add.at(scores, self.item_nb[j], self.item_sim[j] * r)
        return _top_n(scores, ru.indices, n)


# ---------------------------------------------------------------------------
# ContentBased：基于内容推荐
# ---------------------------------------------------------------------------
class ContentBased:
    """用户画像 = 其交互物品TF-IDF向量的评分加权平均；
    推荐分数 = 画像与候选物品向量的余弦相似度。"""

    name = "ContentBased"

    def __init__(self, item_tfidf: sparse.csr_matrix, item_ids: np.ndarray):
        # item_tfidf 第 r 行对应物品 item_ids[r]
        self.tfidf = item_tfidf.tocsr()
        self.item_ids = np.asarray(item_ids, dtype=int)
        self.item2row = {int(i): r for r, i in enumerate(self.item_ids)}

    def fit(self, ratings_df: pd.DataFrame):
        self.R = build_user_item_matrix(ratings_df)
        return self

    def user_profile(self, user_id: int) -> sparse.csr_matrix | None:
        """返回 1 x d 的用户兴趣画像（L2归一化），无可用内容时返回 None"""
        if user_id < 0 or user_id >= self.R.shape[0]:
            return None
        ru = self.R[user_id]
        if ru.nnz == 0:
            return None
        pairs = [(self.item2row[i], float(r)) for i, r in zip(ru.indices, ru.data) if i in self.item2row]
        if not pairs:
            return None
        rows = np.array([p[0] for p in pairs], dtype=int)
        w = np.array([p[1] for p in pairs])
        prof = sparse.csr_matrix(w.reshape(1, -1)) @ self.tfidf[rows]
        norm = float(np.sqrt(prof.multiply(prof).sum()))
        if norm > 0:
            prof = prof / norm
        return prof.tocsr()

    def recommend(self, user_id: int, n: int = 10):
        prof = self.user_profile(user_id)
        if prof is None:
            return []
        sims = cosine_similarity(prof, self.tfidf).ravel()
        seen_rows = [self.item2row[i] for i in self.R[user_id].indices if i in self.item2row]
        # 屏蔽已交互物品（按tfidf行号）
        top = _top_n(sims, np.array(seen_rows, dtype=int), n)
        return [(int(self.item_ids[r]), s) for r, s in top]


# ---------------------------------------------------------------------------
# MostPopular：热门基线（冷启动兜底）
# ---------------------------------------------------------------------------
class MostPopular:
    name = "MostPopular"

    def fit(self, ratings_df: pd.DataFrame):
        self.R = build_user_item_matrix(ratings_df)
        # 热度 = 交互次数（可换为平均分 x log次数）
        self.pop = np.asarray(self.R.astype(bool).sum(axis=0)).ravel().astype(float)
        return self

    def recommend(self, user_id: int, n: int = 10):
        seen = self.R[user_id].indices if 0 <= user_id < self.R.shape[0] else np.array([], dtype=int)
        return _top_n(self.pop, seen, n)


# ---------------------------------------------------------------------------
# CrossDomain：跨域推荐（统一 TF-IDF 标签空间桥接）
# ---------------------------------------------------------------------------
class CrossDomain:
    """跨领域内容推荐（论文亮点）。

    三域物品共享统一 TF-IDF 词表（preprocess_global.py 构建）：
    用户在任意域的交互加权合成统一画像向量，再与目标域物品向量做余弦排序。
    离线数据集用户互不重叠，本算法主要服务线上跨域用户（注册用户在
    多个模块的行为），也可用任一域行为冷启动另一域推荐。

    接口与域内算法不同（无 fit(ratings)），由 api.py 单独调度：
        profile(interactions)                      -> 1 x V 画像
        recommend(interactions, target_domain, n)  -> [(item_id, score)]
        interactions = [(domain, item_id, weight), ...]
    """

    name = "CrossDomain"

    def __init__(self, global_tfidf: sparse.csr_matrix, items_global: pd.DataFrame):
        self.tfidf = global_tfidf.tocsr()
        domains = items_global["domain"].values
        item_ids = items_global["item_id"].astype(int).values
        self.row_item = item_ids  # 行号 -> 域内 item_id
        self.key_row: dict[tuple[str, int], int] = {}
        self.domain_rows: dict[str, np.ndarray] = {}
        for r, (d, i) in enumerate(zip(domains, item_ids)):
            self.key_row[(d, int(i))] = r
            self.domain_rows.setdefault(d, []).append(r)
        self.domain_rows = {d: np.array(v, dtype=int) for d, v in self.domain_rows.items()}

    def profile(self, interactions):
        """用户全部域行为 -> L2 归一化的统一画像；无可用内容时返回 None"""
        pairs = [(self.key_row[(d, int(i))], float(w))
                 for d, i, w in interactions if (d, int(i)) in self.key_row]
        if not pairs:
            return None
        rows = np.array([p[0] for p in pairs], dtype=int)
        ws = np.array([p[1] for p in pairs])
        prof = sparse.csr_matrix(ws.reshape(1, -1)) @ self.tfidf[rows]
        norm = float(np.sqrt(prof.multiply(prof).sum()))
        return (prof / norm).tocsr() if norm > 0 else None

    def recommend(self, interactions, target_domain: str, n: int = 10):
        prof = self.profile(interactions)
        if prof is None:
            return []
        sims = cosine_similarity(prof, self.tfidf).ravel()
        cand = self.domain_rows.get(target_domain)
        if cand is None or cand.size == 0:
            return []
        cand_scores = sims[cand]
        seen = np.array([self.key_row[(target_domain, int(i))]
                         for d, i, _ in interactions
                         if d == target_domain and (d, int(i)) in self.key_row],
                        dtype=int)
        if seen.size:
            cand_scores = cand_scores.copy()
            cand_scores[np.isin(cand, seen)] = -np.inf
        k = min(n, cand.size)
        if k <= 0:
            return []
        top_local = np.argpartition(-cand_scores, k - 1)[:k]
        top_local = top_local[np.argsort(-cand_scores[top_local])]
        return [(int(self.row_item[cand[t]]), float(cand_scores[t]))
                for t in top_local if np.isfinite(cand_scores[t])]


# ---------------------------------------------------------------------------
# 组合推荐器：统一对外（API层使用），未知用户自动回退热门
# ---------------------------------------------------------------------------
class RecommenderSystem:
    """管理多个算法实例；冷启动用户回退 MostPopular。"""

    FALLBACK = "MostPopular"

    def __init__(self):
        self.models: dict[str, object] = {}

    def add(self, model) -> "RecommenderSystem":
        self.models[model.name] = model
        return self

    def recommend(self, algo: str, user_id: int, n: int = 10):
        model = self.models.get(algo) or self.models[self.FALLBACK]
        recs = model.recommend(user_id, n)
        if not recs and model.name != self.FALLBACK:
            recs = self.models[self.FALLBACK].recommend(user_id, n)
        return recs
