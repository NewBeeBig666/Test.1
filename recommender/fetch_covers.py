# -*- coding: utf-8 -*-
"""
电影封面批量预取 + 质量审核（IMDb Suggestion API，免 key）

流程：
  1) 读取 data/processed_movies/items_meta.csv
  2) 逐部（断点续传，已有 poster_url 跳过）经 IMDb suggest 检索：
     标题精确匹配 + 年份校验 + q=feature，取海报 CDN URL 与 width/height
  3) 质量审核：宽 >= 300 且 0.4 <= 高/宽 <= 1.8（排除拉伸变形/横幅图），
     分辨率与审核结论写入 poster_w / poster_h / cover_ok 列
  4) 回写 items_meta.csv（持久化，re-import 安全）
  5) 直接 UPDATE movie 表 poster_url（即时生效，无需整表重导）
  6) 生成 reports_all/cover_audit.md（覆盖率 / 分辨率分布 / 失败清单）

用法：
    py -3 fetch_covers.py                    # 全量（约 3650 部，~20 分钟，可中断续传）
    py -3 fetch_covers.py --popular 400      # 仅按热度预取前 400 部（快速演示）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request

import pandas as pd
import pymysql

ROOT = os.path.dirname(os.path.abspath(__file__))
META = os.path.join(ROOT, "data", "processed_movies", "items_meta.csv")
RATINGS = os.path.join(ROOT, "data", "processed_movies", "ratings_all.csv")
REPORT = os.path.join(ROOT, "reports_all", "cover_audit.md")
SUGGEST = "https://v3.sg.media-imdb.com/suggestion/x/{}.json"
UA = {"User-Agent": "Mozilla/5.0 (recsys-thesis; contact: student)"}
MIN_W, ASPECT_LO, ASPECT_HI = 300, 0.45, 1.8


def norm_title(title: str) -> str:
    """剥离年份与外文括注：'Crouching Tiger, Hidden Dragon (Wo hu cang long) (2000)' -> 'crouching tiger, hidden dragon'"""
    t = re.sub(r"\s*\(\d{4}\)\s*$", "", title)     # 年份
    t = re.sub(r"\s*\([^)]*\)", "", t)             # 外文/别名括注
    m = re.match(r"^(.*),\s+(The|A|An|Les|La|Le|Los|Das|Der|Il|El)$", t)
    return (f"{m.group(2)} {m.group(1)}" if m else t).strip().lower()


def clean_title(title: str) -> str:
    t = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
    t = re.sub(r"\s*\([^)]*\)", "", t)
    return t.strip().lower()


def suggest_poster(title: str, year: str):
    """返回 (url, w, h) 或 None；标题精确匹配优先，年份校验。

    匹配策略（逐级放宽，保证外文/系列片也能命中官方海报）：
      1) 精确标题 + feature + 年份一致
      2) 精确标题 + feature（年份不符，如翻拍/数据误差）
      3) 同年份 feature 且带海报（外文别名条目，标题微差）
      4) 查询词改用冒号前主标题重试 1)~3)（"Star Wars: Episode IV - ..."）
    """
    for query in (norm_title(title), norm_title(title).split(":")[0].strip()):
        if not query:
            continue
        got = _suggest_once(query, year)
        if got:
            return got
    return None


def _suggest_once(query: str, year: str):
    q = urllib.parse.quote(query.replace(" ", "_"))
    try:
        req = urllib.request.Request(SUGGEST.format(q), headers=UA)
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception:
        return None
    exact, year_feat = None, None
    for it in data.get("d", []):
        if not it.get("i", {}).get("imageUrl"):
            continue
        if it.get("q") != "feature":
            continue
        label = it.get("l", "").strip().lower()
        if label == query:
            if not year or str(it.get("y")) == year:
                return it["i"]["imageUrl"], it["i"].get("width"), it["i"].get("height")
            exact = exact or it  # 精确标题但年份不符（翻拍/误差）
        elif year and str(it.get("y")) == year and year_feat is None:
            year_feat = it  # 同年份 feature（外文别名/标题微差）
    best = exact or year_feat
    if best is None:
        return None
    img = best["i"]
    return img["imageUrl"], img.get("width"), img.get("height")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--popular", type=int, default=0, help="仅预取热度前 N 部")
    ap.add_argument("--delay", type=float, default=0.12, help="请求间隔（秒，限速）")
    args = ap.parse_args()

    meta = pd.read_csv(META)
    for col in ["poster_url", "poster_w", "poster_h", "cover_ok"]:
        if col not in meta.columns:
            meta[col] = "" if col == "poster_url" else None

    todo = meta.index[meta["poster_url"].fillna("") == ""]
    if args.popular:
        pop = pd.read_csv(RATINGS).groupby("item_id").size().sort_values(ascending=False)
        hot = set(pop.head(args.popular).index)
        todo = [i for i in todo if meta.at[i, "item_id"] in hot]
    print(f">> 待预取 {len(todo)} 部（已有封面 {len(meta) - len(todo)} 部）")

    t0, done, fails = time.time(), 0, []
    for k, idx in enumerate(todo):
        row = meta.loc[idx]
        got = suggest_poster(str(row["title"]), str(row.get("extra", "") or ""))
        if got:
            url, w, h = got
            ok = bool(w and w >= MIN_W and h and ASPECT_LO <= h / max(w, 1) <= ASPECT_HI)
            meta.at[idx, "poster_url"] = url
            meta.at[idx, "poster_w"] = w
            meta.at[idx, "poster_h"] = h
            meta.at[idx, "cover_ok"] = ok
        else:
            fails.append(int(row["item_id"]))
        done += 1
        if done % 100 == 0:
            meta.to_csv(META, index=False)  # 断点续传
            rate = done / (time.time() - t0)
            print(f"    进度 {done}/{len(todo)}（{rate:.1f} 部/秒，预计剩余 "
                  f"{(len(todo) - done) / max(rate, 0.01) / 60:.0f} 分钟）")
        time.sleep(args.delay)
    meta.to_csv(META, index=False)

    # ---- 质量审核报告 ----
    have = meta[meta["poster_url"].fillna("") != ""]
    ok_rows = have[have["cover_ok"] == True]  # noqa: E712
    ws = have["poster_w"].dropna().astype(int)
    md = ["# 封面质量审核报告（电影域）", "",
          f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
          f"- 覆盖率：{len(have)}/{len(meta)}（{len(have)/len(meta):.1%}）",
          f"- 通过审核（宽≥{MIN_W}px 且比例 {ASPECT_LO}~{ASPECT_HI}）：{len(ok_rows)} 部",
          f"- 分辨率中位数：{int(ws.median()) if len(ws) else '—'}px 宽",
          f"- 高清（宽≥1080）：{(ws >= 1080).sum() if len(ws) else 0} 部", ""]
    if fails:
        md.append(f"- 未能匹配海报：{len(fails)} 部（标题含外文/生僻或 IMDb 无收录，"
                  f"可在管理后台手动补充）：`{fails[:30]}`")
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f">> 完成：{len(have)}/{len(meta)} 有封面，报告 {REPORT}")

    # ---- 同步 MySQL（即时生效）----
    try:
        conn = pymysql.connect(host="127.0.0.1", user="root", password="root",
                                database="recsys", charset="utf8mb4")
        with conn.cursor() as cur:
            for idx, row in have.iterrows():
                cur.execute("UPDATE movie SET poster_url=%s WHERE item_id=%s",
                            (str(row["poster_url"]), int(row["item_id"])))
        conn.commit()
        conn.close()
        print(f">> MySQL movie.poster_url 已更新 {len(have)} 行")
    except Exception as e:
        print(f"!! MySQL 更新失败（导入时仍会带上）：{repr(e)[:90]}")


if __name__ == "__main__":
    main()
