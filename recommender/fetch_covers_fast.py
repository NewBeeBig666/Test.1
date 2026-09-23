# -*- coding: utf-8 -*-
"""fetch_covers 并发加速版：对 poster_url 为空的条目 16 线程并发抓取 IMDb 海报。

复用 fetch_covers.suggest_poster 的逐级匹配策略；失败条目交由
fill_movie_covers.py 程序化兜底。回写 items_meta.csv + MySQL。
用法：py -3 fetch_covers_fast.py
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import pymysql

import fetch_covers as fc

ROOT = os.path.dirname(os.path.abspath(__file__))
META = os.path.join(ROOT, "data", "processed_movies", "items_meta.csv")


def main():
    meta = pd.read_csv(META)
    for col in ["poster_url", "poster_w", "poster_h", "cover_ok"]:
        if col not in meta.columns:
            meta[col] = "" if col == "poster_url" else None
    todo = meta.index[meta["poster_url"].fillna("").astype(str).str.strip() == ""]
    print(f">> 待并发抓取 {len(todo)} 部（16 线程）")

    def work(idx):
        row = meta.loc[idx]
        return idx, fc.suggest_poster(str(row["title"]), str(row.get("extra", "") or ""))

    done = got = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(work, i) for i in todo]
        for fut in as_completed(futs):
            idx, res = fut.result()
            if res:
                url, w, h = res
                ok = bool(w and w >= fc.MIN_W and h
                          and fc.ASPECT_LO <= h / max(w, 1) <= fc.ASPECT_HI)
                meta.at[idx, "poster_url"] = url
                meta.at[idx, "poster_w"] = w
                meta.at[idx, "poster_h"] = h
                meta.at[idx, "cover_ok"] = ok
                got += 1
            done += 1
            if done % 200 == 0:
                meta.to_csv(META, index=False)  # 断点续传
                print(f"    进度 {done}/{len(todo)}，已命中 {got}")
    meta.to_csv(META, index=False)
    print(f">> 完成：新命中 {got}/{done}")

    have = meta[meta["poster_url"].fillna("").astype(str).str.strip() != ""]
    conn = pymysql.connect(host="127.0.0.1", user="root", password=os.environ.get("DB_PASSWORD", "root"),
                            database="recsys", charset="utf8mb4")
    with conn.cursor() as cur:
        for _, row in have.iterrows():
            cur.execute("UPDATE movie SET poster_url=%s WHERE item_id=%s",
                        (str(row["poster_url"]), int(row["item_id"])))
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM movie WHERE poster_url IS NULL OR poster_url=''")
        left = cur.fetchone()[0]
    conn.close()
    print(f">> MySQL 已同步；剩余缺失 {left} 部（交 fill_movie_covers.py 兜底）")


if __name__ == "__main__":
    main()
