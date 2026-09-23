# -*- coding: utf-8 -*-
"""
推荐算法服务（三域：图书/课程/电影）：FastAPI 封装，供 SpringBoot 后端调用。

启动（在 recommender 目录下）：
    uvicorn api:app --host 0.0.0.0 --port 8001
    或: python api.py

统一接口规范（domain ∈ books|courses|movies）：
    GET  /health                              存活检查
    GET  /api/algorithms                      可用算法列表（含 CrossDomain）
    GET  /api/recommend?user_id&domain&algo&n 域内/跨域 Top-N 推荐
    GET  /api/user/{user_id}/profile?domain=  单域用户画像（兴趣+属性标签）
    GET  /api/user/{user_id}/profile/global   跨域统一画像（三域兴趣融合）
    POST /api/events                          接收用户行为（含 domain）
    POST /api/reload                          合并行为日志并重新训练模型

用户ID解析（每域独立）：
    1) 数据集原始 User-ID（体验用户，如 BX 的 114 / MovieLens 的 7）
    2) 线上注册用户（>=1e9，经 data/online_user_map.csv 映射到各域内部ID）
    3) 未知 -> 冷启动，回退 MostPopular

说明：
    生产环境推荐结果缓存放在 SpringBoot 侧（Redis，TTL 30~60 分钟），
    本服务无状态、可水平扩展。
"""
from __future__ import annotations

import csv
import os
import threading
import time
from contextlib import asynccontextmanager

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import load_npz
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from algorithms import UserCF, ItemCF, ContentBased, MostPopular, CrossDomain, RecommenderSystem
from enrichment import enrich_item

ROOT = os.environ.get("REC_ROOT", ".")
DOMAINS = {
    "books": os.path.join(ROOT, "data", "processed_real"),
    "movies": os.path.join(ROOT, "data", "processed_movies"),
    "courses": os.path.join(ROOT, "data", "processed_courses"),
}
GLOBAL_DIR = os.path.join(ROOT, "data", "processed_global")
EVENTS_FILE = os.environ.get("REC_EVENTS_FILE", os.path.join(ROOT, "data", "events.csv"))
ONLINE_MAP_FILE = os.path.join(ROOT, "data", "online_user_map.csv")
DOMAIN_PATTERN = "^(books|courses|movies)$"
# 线上注册用户ID下限（SpringBoot 侧保证从 1e9 起自增）
WEB_USER_BASE = 1_000_000_000

# evaluate.py 生成的算法对比指标（优先三域汇总报告）
METRICS_CANDIDATES = [
    os.environ.get("REC_METRICS_FILE", ""),
    os.path.join(ROOT, "reports_all", "all_metrics.csv"),
    os.path.join(ROOT, "reports_real", "metrics.csv"),
    os.path.join(ROOT, "reports", "metrics.csv"),
]

_state: dict[str, dict] = {}     # domain -> 状态
_global: dict = {}               # CrossDomain 全局模型
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# 事件日志 / 线上用户映射
# ---------------------------------------------------------------------------
def load_events() -> pd.DataFrame:
    cols = ["user_id", "item_id", "domain", "event_type", "rating", "ts"]
    if not os.path.exists(EVENTS_FILE):
        return pd.DataFrame(columns=cols)
    ev = pd.read_csv(EVENTS_FILE)
    if "domain" not in ev.columns:  # 旧格式兼容：无 domain 列默认 books
        ev["domain"] = "books"
    return ev


def load_online_map() -> dict[tuple[str, int], int]:
    if not os.path.exists(ONLINE_MAP_FILE):
        return {}
    df = pd.read_csv(ONLINE_MAP_FILE)
    return {(r.domain, int(r.user_id)): int(r.internal_id) for r in df.itertuples()}


def save_online_map(online_map: dict[tuple[str, int], int]):
    rows = [{"domain": d, "user_id": u, "internal_id": i} for (d, u), i in online_map.items()]
    pd.DataFrame(rows, columns=["domain", "user_id", "internal_id"]).to_csv(
        ONLINE_MAP_FILE, index=False)


def event_rating_norm(event_type: str, rating) -> float:
    """行为 -> 归一化伪评分：rating 事件用真实评分（1-5星 -> 0.2~1.0）"""
    if event_type == "rating" and rating is not None and not pd.isna(rating):
        return float(rating) / 5.0
    return {"view": 0.4, "click": 0.6, "favorite": 0.9}.get(event_type, 0.5)


# ---------------------------------------------------------------------------
# 模型加载与训练
# ---------------------------------------------------------------------------
def train_domain(domain: str, data_dir: str, events: pd.DataFrame,
                 online_map: dict[tuple[str, int], int]):
    """训练单个域的 4 个域内算法，并合并该域线上行为。"""
    ratings = pd.read_csv(os.path.join(data_dir, "ratings_all.csv"))
    orig_col = "User-ID" if "User-ID" in ratings.columns else "orig_user_id"
    uid2iid = ratings.drop_duplicates(orig_col).set_index(orig_col)["user_id"].to_dict()

    # 合并线上行为（本域）：事件用户 -> 域内部ID（数据集用户走 uid2iid，
    # 其余经 online_map 分配新内部ID，跨次 reload 稳定）
    ev = events[events["domain"] == domain]
    ev = ev[ev["item_id"] >= 0]  # 防御：负 ID 为外部精选条目，不参与评分矩阵
    next_internal = int(ratings["user_id"].max()) + 1
    if len(ev):
        ev = ev.copy()
        ev = ev.drop_duplicates(subset=["user_id", "item_id"], keep="last")
        internal = []
        for u in ev["user_id"].astype(int):
            if u in uid2iid:
                internal.append(uid2iid[u])
            elif (domain, int(u)) in online_map:
                internal.append(online_map[(domain, int(u))])
            else:
                online_map[(domain, int(u))] = next_internal
                internal.append(next_internal)
                next_internal += 1
        ev["user_id"] = internal
        ev["rating_norm"] = [event_rating_norm(t, r) for t, r in
                             zip(ev["event_type"], ev["rating"])]
        ratings = pd.concat(
            [ratings[["user_id", "item_id", "rating_norm"]],
             ev[["user_id", "item_id", "rating_norm"]]],
            ignore_index=True,
        ).drop_duplicates(subset=["user_id", "item_id"], keep="last")

    # 物品元数据（统一列名：title/subtitle/extra）
    items = pd.read_csv(os.path.join(data_dir, "items_meta.csv"))
    if domain == "books":
        items = items.rename(columns={"Book-Title": "title", "Book-Author": "subtitle",
                                      "Publisher": "extra"})
    tfidf = load_npz(os.path.join(data_dir, "item_tfidf.npz"))

    sys_rec = RecommenderSystem()
    for m in [UserCF(), ItemCF(), ContentBased(tfidf, items["item_id"].values),
              MostPopular()]:
        m.fit(ratings)
        sys_rec.add(m)

    by_user = {int(uid): (g["item_id"].values.astype(int), g["rating_norm"].values.astype(float))
               for uid, g in ratings.groupby("user_id")}
    _state[domain] = {
        "rec": sys_rec,
        "cb": sys_rec.models["ContentBased"],
        "vec": joblib.load(os.path.join(data_dir, "item_vectorizer.joblib")),
        "items": items.set_index("item_id"),
        "by_user": by_user,
        "uid2iid": uid2iid,
        "online_map": {},  # 填充见 train_all
        "user_ids": set(ratings["user_id"].astype(int)),
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def train_all():
    """加载三域预处理产物并训练全部算法（进程启动时或 /api/reload 后调用）"""
    events = load_events()
    online_map = load_online_map()
    for domain, data_dir in DOMAINS.items():
        t0 = time.time()
        train_domain(domain, data_dir, events, online_map)
        print(f">> [{domain}] 训练完成 ({time.time() - t0:.1f}s)")
    save_online_map(online_map)

    # 跨域统一模型
    items_global = pd.read_csv(os.path.join(GLOBAL_DIR, "items_global.csv"))
    gtfidf = load_npz(os.path.join(GLOBAL_DIR, "global_tfidf.npz"))
    _global.update(
        cross=CrossDomain(gtfidf, items_global),
        vec=joblib.load(os.path.join(GLOBAL_DIR, "global_vectorizer.joblib")),
        items=items_global,
    )
    # 各域 online_map 引用（解析线上用户用）
    for domain in DOMAINS:
        _state[domain]["online_map"] = {u: i for (d, u), i in online_map.items() if d == domain}


@asynccontextmanager
async def lifespan(app: FastAPI):
    train_all()
    print(">> 推荐服务就绪（三域 + CrossDomain）:", time.strftime("%Y-%m-%d %H:%M:%S"))
    yield


app = FastAPI(title="Rec-Algo Service", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def resolve_user(user_id: int, domain: str) -> int:
    """原始User-ID / 线上用户 -> 域内部ID；未知返回 -1（冷启动）"""
    st = _state[domain]
    if user_id in st["uid2iid"]:
        return st["uid2iid"][user_id]
    if user_id in st["online_map"]:
        return st["online_map"][user_id]
    if user_id in st["user_ids"]:
        return user_id
    return -1


def collect_interactions(user_id: int):
    """收集用户在三域的全部行为 [(domain, item_id, weight)]"""
    out = []
    for domain, st in _state.items():
        iid = resolve_user(user_id, domain)
        if iid < 0:
            continue
        hit = st["by_user"].get(iid)
        if hit is not None:
            items, ws = hit
            out.extend((domain, int(i), float(w)) for i, w in zip(items, ws))
    return out


def enrich(recs, domain: str):
    items = _state[domain]["items"]
    has_img = "image_url" in items.columns
    out = []
    for item_id, score in recs:
        row = items.loc[item_id] if item_id in items.index else None
        d = {
            "item_id": item_id,
            "title": None if row is None else str(row.get("title", "")),
            "subtitle": None if row is None else str(row.get("subtitle", "")),
            "extra": None if row is None else str(row.get("extra", "")),
            "score": round(float(score), 4),
        }
        if has_img and row is not None:
            d["image_url"] = row.get("image_url") if pd.notna(row.get("image_url")) else None
        out.append(d)
    return out


def profile_tags(prof, vec, top_tags: int):
    """画像向量 -> Top 兴趣标签"""
    if prof is None:
        return []
    weights = np.asarray(prof.todense()).ravel()
    top = weights.argsort()[::-1][:top_tags]
    vocab_inv = {i: w for w, i in vec.vocabulary_.items()}
    return [{"tag": vocab_inv.get(int(i), ""), "weight": round(float(weights[i]), 4)}
            for i in top if weights[i] > 0]


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok",
            "domains": {d: st["trained_at"] for d, st in _state.items()},
            "cross_domain": "ready" if _global else "loading"}


@app.get("/api/algorithms")
def algorithms():
    return {"algorithms": ["UserCF", "ItemCF", "ContentBased", "CrossDomain", "MostPopular"]}


@app.get("/api/recommend")
def recommend(
    user_id: int,
    domain: str = Query(..., pattern=DOMAIN_PATTERN),
    algo: str = Query("ItemCF",
                      description="UserCF|ItemCF|ContentBased|CrossDomain|MostPopular"),
    n: int = Query(10, ge=1, le=50),
):
    if not _state:
        raise HTTPException(503, "模型加载中，请稍后重试")
    st = _state[domain]
    t0 = time.time()
    cold_start = False

    if algo == "CrossDomain":
        interactions = collect_interactions(user_id)
        recs = _global["cross"].recommend(interactions, domain, n) if interactions else []
        if not recs:  # 无跨域行为 -> 热门兜底
            cold_start = True
            recs = st["rec"].recommend("MostPopular", -1, n)
    else:
        if algo not in st["rec"].models:
            raise HTTPException(400, f"未知算法: {algo}")
        internal_id = resolve_user(user_id, domain)
        recs = st["rec"].recommend(algo, internal_id, n)
        cold_start = internal_id < 0 or not recs

    return {
        "user_id": user_id,
        "domain": domain,
        "algo": algo,
        "cold_start": cold_start,
        "latency_ms": round((time.time() - t0) * 1000, 2),
        "items": enrich(recs, domain),
    }


@app.get("/api/user/{user_id}/profile")
def user_profile(user_id: int, domain: str = Query(..., pattern=DOMAIN_PATTERN),
                 top_tags: int = Query(10, ge=1, le=50)):
    if not _state:
        raise HTTPException(503, "模型加载中")
    st = _state[domain]
    internal_id = resolve_user(user_id, domain)
    if internal_id < 0:
        raise HTTPException(404, "用户不存在（无历史行为，暂无画像）")

    prof = st["cb"].user_profile(internal_id)
    tags = profile_tags(prof, st["vec"], top_tags)
    # 属性标签：来自预处理产物（如 BX 用户的年龄段/国家）
    attr = []
    um_path = os.path.join(DOMAINS[domain], "users_meta.csv")
    if os.path.exists(um_path):
        um = pd.read_csv(um_path)
        row = um[um["User-ID"] == user_id]
        if len(row):
            r = row.iloc[0]
            attr = [t for t in [r.get("age_group"), r.get("country")] if pd.notna(t)]

    return {"user_id": user_id, "domain": domain,
            "interest_tags": tags, "attribute_tags": attr}


class Event(BaseModel):
    user_id: int
    item_id: int
    domain: str = Field(pattern=DOMAIN_PATTERN)
    event_type: str = Field(description="view|click|rating|favorite")
    rating: float | None = None


EVENTS_HEADER = ["user_id", "item_id", "domain", "event_type", "rating", "ts"]


def ensure_events_schema():
    """旧格式（无 domain 列）迁移：重写文件并补 domain=books"""
    if not os.path.exists(EVENTS_FILE):
        return
    with open(EVENTS_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows or "domain" in rows[0]:
        return
    with open(EVENTS_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(EVENTS_HEADER)
        for r in rows[1:]:
            if len(r) == 5:
                w.writerow([r[0], r[1], "books", r[2], r[3], r[4]])


@app.post("/api/events")
def record_event(ev: Event):
    """接收 SpringBoot 转发的用户行为，落盘 CSV；调用 /api/reload 后生效"""
    if ev.event_type not in ("view", "click", "rating", "favorite"):
        raise HTTPException(400, "event_type 须为 view|click|rating|favorite")
    os.makedirs(os.path.dirname(EVENTS_FILE), exist_ok=True)
    ensure_events_schema()
    new_file = not os.path.exists(EVENTS_FILE)
    with _lock, open(EVENTS_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(EVENTS_HEADER)
        w.writerow([ev.user_id, ev.item_id, ev.domain, ev.event_type, ev.rating,
                    time.strftime("%Y-%m-%d %H:%M:%S")])
    return {"status": "recorded"}


@app.get("/api/user/{user_id}/profile/global")
def profile_global(user_id: int, top_tags: int = Query(10, ge=1, le=50)):
    """跨域统一画像：统一 TF-IDF 词表下的兴趣标签 + 三域分域画像（论文亮点）"""
    if not _global:
        raise HTTPException(503, "模型加载中")
    interactions = collect_interactions(user_id)
    if not interactions:
        raise HTTPException(404, "用户不存在（三域均无历史行为，暂无画像）")

    prof = _global["cross"].profile(interactions)
    tags = profile_tags(prof, _global["vec"], top_tags)

    domains = {}
    for domain, st in _state.items():
        cnt = sum(1 for d, _, _ in interactions if d == domain)
        d_tags = []
        if cnt:
            prof_d = st["cb"].user_profile(resolve_user(user_id, domain))
            d_tags = profile_tags(prof_d, st["vec"], top_tags)
        domains[domain] = {"interactions": cnt, "interest_tags": d_tags}

    return {"user_id": user_id, "interest_tags": tags, "domains": domains}


@app.get("/api/metrics")
def metrics():
    """离线对比实验结果（evaluate.py 产出），供前端算法对比页展示"""
    for path in METRICS_CANDIDATES:
        if path and os.path.exists(path):
            df = pd.read_csv(path)
            return {"metrics_file": path, "rows": df.to_dict(orient="records")}
    raise HTTPException(404, "未找到 metrics.csv，请先运行 evaluate.py")


@app.post("/api/reload")
def reload_models():
    train_all()
    return {"status": "retrained",
            "trained_at": {d: st["trained_at"] for d, st in _state.items()}}


@app.get("/api/enrich/{domain}/{item_id}")
def enrich_endpoint(domain: str, item_id: int):
    """资源富化（封面/简介/外链），SpringBoot 缓存进 item_enrichment 表"""
    if domain not in DOMAINS:
        raise HTTPException(404, f"未知域: {domain}")
    try:
        return enrich_item(domain, item_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except Exception as e:  # 外部源异常不阻断，返回可识别错误
        raise HTTPException(502, f"富化服务异常: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
