# -*- coding: utf-8 -*-
"""
数据渠道扩展与整合框架（含自动化更新 + 数据质量监控）

三层能力：
  1) 渠道注册表 CHANNELS：覆盖图书/课程/电影/通用推荐数据平台共 22 个渠道，
     每个渠道含 URL、访问方式、字段结构、适用性与接入状态
       - integrated : 已接入主模型（Book-Crossing / MovieLens / Udemy）
       - adapter    : 已实现自动抓取适配器（本文件实现，可直连下载）
       - ready      : 可直连获取，接入需按注册表字段映射扩展 adapter
       - apply      : 需注册申请 / API Key / 联系作者（注册表给出指引）
  2) 自动化更新：--update 调用各 adapter 拉取→解析→统一格式落地 data/external/
     （Windows 计划任务示例见 docs/数据渠道.md；update_datasets.bat 一键脚本）
  3) 质量监控：--quality 扫描主模型三域 + external 渠道，
     输出 reports_all/data_quality.md（行数/用户/物品/评分分布/稀疏度/新鲜度/
     与基线对比异常检测，基线存 data/external/last_quality.json）

统一外部数据格式（data/external/{channel}/）：
    ratings.csv   orig_user_id, item_orig, rating        （评分型渠道）
    items.csv     item_orig, title, subtitle, extra      （元数据型渠道）
    raw/          原始下载文件

用法：
    py -3 dataset_channels.py --list
    py -3 dataset_channels.py --update [--channel movietweetings|gutenberg]
    py -3 dataset_channels.py --merge-movies   # MovieTweetings 合并 MovieLens -> data/processed_movies_merged
    py -3 dataset_channels.py --quality
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import time
import urllib.request

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
EXTERNAL_DIR = os.path.join(ROOT, "data", "external")
RAW_DIR = os.path.join(ROOT, "data", "raw_external")
QUALITY_BASELINE = os.path.join(EXTERNAL_DIR, "last_quality.json")
REPORT_PATH = os.path.join(ROOT, "reports_all", "data_quality.md")

UA = {"User-Agent": "Mozilla/5.0 (recsys-thesis)"}
MIRROR = "https://ghproxy.net/"  # raw.githubusercontent.com 直连不可达时的镜像前缀

# ---------------------------------------------------------------------------
# 渠道注册表（全量）
# ---------------------------------------------------------------------------
CHANNELS = [
    # ---- 图书域 ----
    dict(id="book-crossing", name="Book-Crossing", domain="books", status="integrated",
         url="https://tianchi.aliyun.com/dataset/31828",
         access="阿里云天池镜像直下（BX-CSV-Dump.zip）",
         fields="User-ID / ISBN / Book-Rating(0-10)；书表含 Title/Author/Publisher/Image-URL",
         notes="已接入：图书域主数据（9085 本 / 6851 用户）"),
    dict(id="goodreads", name="Goodreads 书评", domain="books", status="apply",
         url="https://www.goodreads.com/",
         access="官方 API 已于 2020 关闭；Kaggle 有 goodreads-reviews 等镜像（需账号）",
         fields="user_id / book_id / rating(1-5) / shelves / review_text",
         notes="评分密度高，可扩充图书域；从 Kaggle 镜像下载后按 preprocess.py 流程清洗"),
    dict(id="amazon-books", name="Amazon Books 子集", domain="books", status="ready",
         url="https://jmcauley.ucsd.edu/data/amazon/",
         access="UCSD McAuley 主页直链（ratings/reviews *.json.gz）",
         fields="asin / overall(1-5) / reviewText / verified",
         notes="量级大（千万级），建议取 Books 子集抽样后接入；字段映射见 preprocess.py"),
    dict(id="gutenberg", name="Project Gutenberg 书目", domain="books", status="adapter",
         url="https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv",
         access="官方 CSV 直链（全量书目元数据，无个体评分）",
         fields="Text# / Type / Title / Language / Authors / Subjects / LoCC",
         notes="内容增强型渠道：公版书元数据，可扩充图书域物品目录与 TF-IDF 内容特征"),
    # ---- 电影域 ----
    dict(id="movielens", name="MovieLens ml-latest-small", domain="movies", status="integrated",
         url="https://grouplens.org/datasets/movielens/",
         access="GroupLens 直链（天池有镜像）",
         fields="userId / movieId / rating(0.5-5) / timestamp；movies.csv 含 title+genres",
         notes="已接入：电影域主数据（3650 部 / 606 用户）"),
    dict(id="netflix-prize", name="Netflix Prize 历史数据", domain="movies", status="apply",
         url="https://www.netflixprize.com/",
         access="官方已下架；Kaggle 镜像（netflix-prize 需账号）",
         fields="CustomerID / MovieID / Rating(1-5) / Date（约 1 亿评分）",
         notes="评分规模最大，接入需抽样（建议 5-core + 随机用户抽样控制内存）"),
    dict(id="movietweetings", name="MovieTweetings", domain="movies", status="adapter",
         url="https://github.com/sidooms/MovieTweetings",
         access="GitHub raw 直链（本网络经镜像下载）；约 92 万评分 / 7.2 万用户 / 3.8 万部",
         fields="ratings.dat: userId::imdbId::rating(1-10)::ts；movies.dat: imdbId::title::genres",
         notes="已实现自动抓取与标准化（--update）；--merge-movies 可与 MovieLens 按 IMDb ID 合并"),
    dict(id="tmdb", name="TMDb Movies Dataset", domain="movies", status="ready",
         url="https://www.themoviedb.org/documentation/api",
         access="REST API v3，免费注册 API Key（无个体级评分，含 popularity/vote_average）",
         fields="id / title / genres / popularity / vote_average / release_date",
         notes="元数据增强渠道：用于扩充电影内容特征与海报（配置 TMDB_API_KEY 环境变量后可扩展）"),
    dict(id="filmtrust", name="FilmTrust / Flixster / CiaoDVD", domain="movies", status="apply",
         url="https://www.librec.net/datasets.html",
         access="librec.net 原分发页已停用（域名停靠）；需联系作者或 GuruRecommender 项目获取",
         fields="FilmTrust: userId itemId rating(0.5-4)；Flixster/CiaoDVD: 用户-电影信任+评分网络",
         notes="经典多源学术数据集，适合做跨数据源算法稳健性对比"),
    # ---- 课程域 ----
    dict(id="udemy", name="Udemy Courses Dataset", domain="courses", status="integrated",
         url="https://www.kaggle.com/datasets (搜索 udemy-courses)",
         access="Kaggle 公开数据集（仓库已含 data/udemy_courses.csv）",
         fields="course_id / course_title / subject / level / price / num_subscribers",
         notes="已接入：课程域主数据（真实课程目录，个体级评分按文档化模型模拟）"),
    dict(id="coco", name="COCO 课程数据集", domain="courses", status="apply",
         url="https://link.springer.com/chapter/10.1007/978-3-319-77712-2_133",
         access="需联系论文作者（研究用途授权）",
         fields="course_id / course_name / school / enrollments / concepts / 用户选课记录",
         notes="真实 MOOC 选课与概念标注，可替换当前模拟评分（字段映射见 preprocess_domain.py）"),
    dict(id="coursera-edx", name="Coursera / edX 公开教育数据", domain="courses", status="ready",
         url="https://www.kaggle.com/datasets (搜索 coursera-course-data)",
         access="Kaggle 课程元数据集（需账号）；edX 有部分公开课程结构导出",
         fields="course_id / course_title / subject / level / rating(课程均分) / num_subscribers",
         notes="与 Udemy 目录同构：替换 items 元数据即可（评分仍需模拟或接 COCO）"),
    dict(id="wikiqa", name="WikiQA 问答语料库", domain="courses", status="ready",
         url="https://www.microsoft.com/en-us/download/details.aspx?id=52419",
         access="微软直链下载",
         fields="question / answer_sentence / label（教育问答对，非评分）",
         notes="内容增强型：教育领域语料，可扩充课程域 TF-IDF 语义特征"),
    dict(id="industrycorpus", name="IndustryCorpus 等行业语料", domain="courses", status="apply",
         url="国家/行业语料平台（需注册）",
         access="注册申请制",
         fields="行业文本语料 / 技能标签",
         notes="职业教育领域内容补充渠道"),
    # ---- 通用推荐系统数据平台 ----
    dict(id="kaggle", name="Kaggle Datasets", domain="general", status="ready",
         url="https://www.kaggle.com/datasets",
         access="kaggle CLI + kaggle.json 凭证（账号设置页生成）",
         fields="各数据集异构；kaggle datasets download -d {owner}/{dataset}",
         notes="统一入口：凭 kaggle.json 可自动化拉取 Goodreads/Netflix 镜像等"),
    dict(id="huggingface", name="Hugging Face Datasets", domain="general", status="ready",
         url="https://huggingface.co/datasets",
         access="datasets 库直连（国内可配 HF_ENDPOINT=https://hf-mirror.com）",
         fields="load_dataset('{name}')，含 Yambda/MSD 衍生集等",
         notes="统一入口：transformers 生态，适合大规模交互数据"),
    dict(id="nstdc", name="国家基础学科公共科学数据中心", domain="general", status="apply",
         url="https://www.nbsdc.cn/",
         access="注册申请制",
         fields="学科基础数据 / 科研实体元数据",
         notes="科教领域权威数据源，需实名申请"),
    dict(id="amazon-product", name="Amazon Product Data", domain="general", status="ready",
         url="https://jmcauley.ucsd.edu/data/amazon/",
         access="UCSD 直链 *.json.gz（1996-2023 各年份子集）",
         fields="asin / overall / category / price / also_bought（共现图）",
         notes="电商全域：品类过滤后可用于任何域的物品元数据与协同信号扩充"),
    dict(id="yelp", name="Yelp Open Dataset", domain="general", status="apply",
         url="https://www.yelp.com/dataset",
         access="同意使用协议后下载（需注册）",
         fields="user_id / business_id / stars(1-5) / review_text",
         notes="本地生活评价，评价文本丰富，适合内容+协同混合建模"),
    dict(id="music-apis", name="Last.fm / MSD / Spotify", domain="general", status="apply",
         url="Last.fm API / Million Song Dataset (Columbia) / Spotify Web API",
         access="均需 API Key 或学术授权",
         fields="Last.fm: user-artist-play；MSD: user-song-rating+audio特征；Spotify: playlist音轨",
         notes="音乐/媒体推荐域扩展，可复用本系统四算法与评估框架"),
    dict(id="yambda", name="Yandex Yambda", domain="general", status="ready",
         url="https://huggingface.co/datasets/ai-forever/yambda",
         access="HuggingFace 直下（2025 发布，约 4.79B 音乐交互事件）",
         fields="user_id / item_id / event(listen/like/dislike) / ts",
         notes="隐式反馈大规模数据，抽样后可做冷启动/长尾对比实验"),
    dict(id="epinions-ciao", name="Epinions / Ciao", domain="general", status="apply",
         url="学术分发已终止（联系 Trustlet / 论文作者）",
         access="需联系作者获取",
         fields="user-item-rating(1-5) + user-user 信任网络",
         notes="信任感知推荐经典数据集，可扩展社交推荐方向"),
    dict(id="jester", name="Jester 笑话评分", domain="general", status="apply",
         url="http://eigentaste.berkeley.edu/dataset/",
         access="Berkeley 直链（本网络实测超时，需代理环境）",
         fields="userId / jokeId / rating(-10~10 连续)，7 万用户 / 100 笑话，密度极高",
         notes="连续评分域，适合回归式评分预测对比实验"),
]


# ---------------------------------------------------------------------------
# 下载工具
# ---------------------------------------------------------------------------
def http_get(url: str, dest: str, timeout: int = 120) -> str:
    """下载到 dest（自动建目录），返回文件路径；直连失败自动换镜像前缀。"""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for attempt_url in ([url] if url.startswith("https://www.gutenberg")
                        else [url, MIRROR + url]):
        try:
            req = urllib.request.Request(attempt_url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
                total = 0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    total += len(chunk)
            print(f"    下载完成 {os.path.basename(dest)}: {total/1e6:.1f} MB <- {attempt_url}")
            return dest
        except Exception as e:
            print(f"    失败 {attempt_url}: {repr(e)[:80]}")
    raise RuntimeError(f"全部下载源失败: {url}")


# ---------------------------------------------------------------------------
# 适配器 1：MovieTweetings（真实评分，92 万条）
# ---------------------------------------------------------------------------
def update_movietweetings():
    print(">> [MovieTweetings] 拉取 GitHub raw 数据 ...")
    base = ("https://raw.githubusercontent.com/sidooms/MovieTweetings/"
            "master/latest/")
    out = os.path.join(EXTERNAL_DIR, "movietweetings")
    raw = os.path.join(RAW_DIR, "movietweetings")
    for fn in ["ratings.dat", "movies.dat"]:
        http_get(base + fn, os.path.join(raw, fn))

    # ratings.dat: userId::imdbId::rating::ts  ->  ratings.csv
    rows = []
    with open(os.path.join(raw, "ratings.dat"), encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("::")
            if len(p) == 4:
                rows.append((int(p[0]), int(p[1]), float(p[2])))  # imdbId 去前导零
    ratings = pd.DataFrame(rows, columns=["orig_user_id", "item_orig", "rating"])
    # items: imdbId::title(year)::genres|pipe|
    items = []
    with open(os.path.join(raw, "movies.dat"), encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("::")
            if len(p) == 3:
                m = re.search(r"\((\d{4})\)\s*$", p[1])
                items.append({"item_orig": int(p[0]), "title": p[1].strip(),
                              "subtitle": p[2].replace("|", " "),
                              "extra": m.group(1) if m else ""})
    items = pd.DataFrame(items)
    os.makedirs(out, exist_ok=True)
    ratings.to_csv(os.path.join(out, "ratings.csv"), index=False)
    items.to_csv(os.path.join(out, "items.csv"), index=False)
    print(f"    标准化完成：{len(ratings)} 评分 / {len(items)} 部电影 "
          f"（IMDb ID 键，可 --merge-movies 并入 MovieLens）")
    return out


def merge_movies():
    """MovieTweetings 按 IMDb ID 合并 MovieLens -> data/processed_movies_merged（不动主模型）。"""
    from preprocess_domain import clean_and_split, build_features  # 复用统一流程

    mt_dir = os.path.join(EXTERNAL_DIR, "movietweetings")
    if not os.path.exists(os.path.join(mt_dir, "ratings.csv")):
        print("!! 请先运行 --update --channel movietweetings")
        return
    links = pd.read_csv(os.path.join(ROOT, "data", "ml-latest-small", "links.csv"))
    ml_ratings = pd.read_csv(os.path.join(ROOT, "data", "ml-latest-small", "ratings.csv"))
    ml_movies = pd.read_csv(os.path.join(ROOT, "data", "ml-latest-small", "movies.csv"))
    mt = pd.read_csv(os.path.join(mt_dir, "ratings.csv"))
    mt_items = pd.read_csv(os.path.join(mt_dir, "items.csv"))

    imdb2ml = links.dropna(subset=["imdbId"]).set_index("imdbId")["movieId"].to_dict()
    mt["item_orig"] = mt["item_orig"].map(imdb2ml)
    joined = mt.dropna(subset=["item_orig"])
    print(f">> IMDb 关联覆盖：{len(joined)}/{len(mt)} 条 MT 评分可映射到 MovieLens 电影 "
          f"({joined['item_orig'].nunique()} 部)")
    joined = joined.rename(columns={"item_orig": "movieId", "orig_user_id": "userId"})

    merged = pd.concat([ml_ratings[["userId", "movieId", "rating"]], joined],
                        ignore_index=True)
    merged = merged.rename(columns={"userId": "orig_user_id", "movieId": "item_orig"})
    df, train, test = clean_and_split(merged)
    items = pd.DataFrame({
        "item_orig": ml_movies["movieId"],
        "title": ml_movies["title"],
        "subtitle": ml_movies["genres"].str.replace("|", " ", regex=False),
        "extra": ml_movies["title"].str.extract(r"\((\d{4})\)$")[0].fillna(""),
    })
    tfidf, meta, vec = build_features(items, df)
    from scipy.sparse import save_npz
    out_dir = os.path.join(ROOT, "data", "processed_movies_merged")
    os.makedirs(out_dir, exist_ok=True)
    train.to_csv(os.path.join(out_dir, "ratings_train.csv"), index=False)
    test.to_csv(os.path.join(out_dir, "ratings_test.csv"), index=False)
    df.to_csv(os.path.join(out_dir, "ratings_all.csv"), index=False)
    meta.to_csv(os.path.join(out_dir, "items_meta.csv"), index=False)
    save_npz(os.path.join(out_dir, "item_tfidf.npz"), tfidf)
    import joblib
    joblib.dump(vec, os.path.join(out_dir, "item_vectorizer.joblib"))
    print(f">> 合并域输出 {out_dir}：评分 {len(df)}，用户 {df['user_id'].nunique()}，"
          f"物品 {df['item_id'].nunique()}（MovieLens {len(ml_ratings)} + MT {len(joined)}）")
    print("   启用方式：将 api.py DOMAINS[movies] 指向该目录并重启（或重跑 evaluate_all.py）")


# ---------------------------------------------------------------------------
# 适配器 2：Project Gutenberg（公版书元数据）
# ---------------------------------------------------------------------------
def update_gutenberg(max_rows: int = 50000):
    print(">> [Project Gutenberg] 拉取官方书目目录 ...")
    raw = os.path.join(RAW_DIR, "gutenberg")
    http_get("https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv",
             os.path.join(raw, "pg_catalog.csv"), timeout=300)
    cat = pd.read_csv(os.path.join(raw, "pg_catalog.csv"), low_memory=False)
    cat = cat[(cat["Type"] == "Text") & (cat["Language"].astype(str).str.startswith("en"))]
    items = pd.DataFrame({
        "item_orig": cat["Text#"],
        "title": cat["Title"].astype(str).str.slice(0, 200),
        "subtitle": cat["Authors"].astype(str).str.replace(r"\[|\]", "", regex=True).str.slice(0, 150),
        "extra": cat["Subjects"].astype(str).str.split(";").str[0].str.slice(0, 80),
    }).head(max_rows).drop_duplicates("item_orig")
    out = os.path.join(EXTERNAL_DIR, "gutenberg")
    os.makedirs(out, exist_ok=True)
    items.to_csv(os.path.join(out, "items.csv"), index=False)
    print(f"    标准化完成：{len(items)} 本公版书元数据（内容增强型渠道，无个体评分）")
    return out


ADAPTERS = {"movietweetings": update_movietweetings, "gutenberg": update_gutenberg}


# ---------------------------------------------------------------------------
# 数据质量监控
# ---------------------------------------------------------------------------
def _stat_domain(name: str, d: str) -> dict:
    r = pd.read_csv(os.path.join(d, "ratings_all.csv"))
    lo, hi = float(r["rating_norm"].min()), float(r["rating_norm"].max())
    return {
        "行数": len(r), "用户数": r["user_id"].nunique(), "物品数": r["item_id"].nunique(),
        "评分均值": round(float(r["rating_norm"].mean()), 3),
        "评分区间": f"{lo:.2f}~{hi:.2f}",
        "稀疏度": f"{len(r) / (r['user_id'].nunique() * r['item_id'].nunique()):.4%}",
        "文件更新": time.strftime("%Y-%m-%d %H:%M", time.localtime(
            os.path.getmtime(os.path.join(d, "ratings_all.csv")))),
    }


def _stat_external(name: str, d: str) -> dict:
    rp, ip = os.path.join(d, "ratings.csv"), os.path.join(d, "items.csv")
    s = {}
    if os.path.exists(rp):
        r = pd.read_csv(rp)
        s.update({"评分行数": len(r), "用户数": r["orig_user_id"].nunique(),
                  "物品数": r["item_orig"].nunique(),
                  "评分均值": round(float(r["rating"].mean()), 2)})
    if os.path.exists(ip):
        s["元数据物品数"] = len(pd.read_csv(ip))
    s["文件更新"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(
        os.path.getmtime(rp if os.path.exists(rp) else ip)))
    return s


def quality():
    """扫描全部数据资产 -> data_quality.md；与上次基线对比做异常告警。"""
    sections = []
    stats = {}

    # 主模型三域
    domains = {"books": "processed_real", "movies": "processed_movies",
               "courses": "processed_courses"}
    rows_md = ["| 域 | 行数 | 用户数 | 物品数 | 评分均值 | 稀疏度 | 文件更新 |",
               "|---|---|---|---|---|---|---|"]
    for dn, dd in domains.items():
        try:
            s = _stat_domain(dn, os.path.join(ROOT, "data", dd))
            stats[dn] = s
            rows_md.append(f"| {dn} | {s['行数']} | {s['用户数']} | {s['物品数']} | "
                           f"{s['评分均值']} | {s['稀疏度']} | {s['文件更新']} |")
        except Exception as e:
            rows_md.append(f"| {dn} | 读取失败: {repr(e)[:60]} | | | | | |")
    sections.append(("主模型数据（active）", "\n".join(rows_md)))

    # 外部渠道
    if os.path.isdir(EXTERNAL_DIR):
        ext_md = ["| 渠道 | 指标 |", "|---|---|"]
        for ch in sorted(os.listdir(EXTERNAL_DIR)):
            d = os.path.join(EXTERNAL_DIR, ch)
            if not os.path.isdir(d):
                continue
            s = _stat_external(ch, d)
            stats[f"ext:{ch}"] = s
            desc = "，".join(f"{k}={v}" for k, v in s.items())
            ext_md.append(f"| {ch} | {desc} |")
        if len(ext_md) > 2:
            sections.append(("外部渠道数据（external）", "\n".join(ext_md)))

    # 渠道状态
    st_md = ["| 渠道 | 域 | 状态 | 获取方式 |", "|---|---|---|---|"]
    badge = {"integrated": "已接入", "adapter": "已自动化", "ready": "可直连", "apply": "需申请"}
    for c in CHANNELS:
        st_md.append(f"| {c['name']} | {c['domain']} | {badge[c['status']]} | {c['access']} |")
    sections.append(("渠道注册表状态", "\n".join(st_md)))

    # 基线对比（异常检测：行数骤降 >5% 告警）
    alerts = []
    if os.path.exists(QUALITY_BASELINE):
        prev = json.load(open(QUALITY_BASELINE, encoding="utf-8"))
        for key, s in stats.items():
            for metric in ["行数", "评分行数"]:
                if metric in s and metric in (prev.get(key) or {}):
                    cur, old = s[metric], prev[key][metric]
                    if old and cur < old * 0.95:
                        alerts.append(f"{key}.{metric} 骤降：{old} -> {cur}（-5% 以上，请检查数据源）")
    json.dump(stats, open(QUALITY_BASELINE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    md = ["# 数据质量监控报告", "",
          f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}（`py -3 dataset_channels.py --quality`）",
          f"渠道总数：{len(CHANNELS)}（已接入 {sum(1 for c in CHANNELS if c['status']=='integrated')} / "
          f"已自动化 {sum(1 for c in CHANNELS if c['status']=='adapter')} / "
          f"可直连 {sum(1 for c in CHANNELS if c['status']=='ready')} / "
          f"需申请 {sum(1 for c in CHANNELS if c['status']=='apply')}）", ""]
    if alerts:
        md += ["## 异常告警", ""] + [f"- ⚠ {a}" for a in alerts] + [""]
    for title, body in sections:
        md += [f"## {title}", "", body, ""]
    md += ["## 自动化更新", "",
           "- 手动：`py -3 dataset_channels.py --update`（全部 adapter 渠道）",
           "- 一键脚本：`update_datasets.bat`（更新 + 质量报告）",
           "- Windows 计划任务（每日 03:00）：",
           "  `schtasks /Create /SC DAILY /TN RecSysDataUpdate /ST 03:00 /TR \"E:\\ZcodeSpace\\New Demo\\update_datasets.bat\"`",
           ""]
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f">> 质量报告已生成：{REPORT_PATH}")
    for a in alerts:
        print("   ⚠", a)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="数据渠道扩展与整合框架")
    ap.add_argument("--list", action="store_true", help="列出全部数据渠道")
    ap.add_argument("--update", action="store_true", help="更新全部/指定 adapter 渠道")
    ap.add_argument("--channel", help="仅更新指定渠道（movietweetings|gutenberg）")
    ap.add_argument("--merge-movies", action="store_true",
                    help="MovieTweetings 与 MovieLens 合并 -> data/processed_movies_merged")
    ap.add_argument("--quality", action="store_true", help="生成数据质量监控报告")
    args = ap.parse_args()

    if args.list or not any(vars(args).values()):
        print(f"{'渠道':<28}{'域':<10}{'状态':<8}说明")
        badge = {"integrated": "已接入", "adapter": "已自动化", "ready": "可直连", "apply": "需申请"}
        for c in CHANNELS:
            print(f"{c['name']:<30}{c['domain']:<10}{badge[c['status']]:<8}{c['url']}")
        return

    if args.update:
        targets = [args.channel] if args.channel else list(ADAPTERS)
        for t in targets:
            if t not in ADAPTERS:
                print(f"!! 渠道 {t} 无自动 adapter（状态见 --list）")
                continue
            try:
                ADAPTERS[t]()
            except Exception as e:
                print(f"!! {t} 更新失败：{repr(e)[:100]}")
        quality()
    if args.merge_movies:
        merge_movies()
    if args.quality:
        quality()


if __name__ == "__main__":
    main()
