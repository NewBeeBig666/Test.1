# -*- coding: utf-8 -*-
"""清洗数据文件中的 HTML 实体（BX/MovieTweetings 数据源转义残留）

范围：processed_* / external / processed_global 的物品元数据 title 类列。
清洗后与 MySQL 侧保持一致，避免推荐流标题出现 &amp; 等转义。
"""
import os
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))

ENTITIES = [("&amp;", "&"), ("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">")]


def clean_series(s: pd.Series) -> pd.Series:
    for a, b in ENTITIES:
        s = s.str.replace(a, b, regex=False)
    return s


def clean_csv(path: str, cols: list) -> None:
    if not os.path.exists(path):
        print(f"[skip] {path}")
        return
    df = pd.read_csv(path)
    n = 0
    for c in cols:
        if c in df.columns and pd.api.types.is_string_dtype(df[c]):
            mask = df[c].str.contains("&(amp|quot|lt|gt);", regex=True, na=False)
            n += int(mask.sum())
            df[c] = clean_series(df[c].fillna(""))
    df.to_csv(path, index=False)
    print(f"[ok] {os.path.relpath(path, ROOT)}: fixed {n} cells")


if __name__ == "__main__":
    for d in ("processed_real", "processed_courses", "processed_movies",
              "external/movietweetings"):
        clean_csv(os.path.join(ROOT, "data", d, "items_meta.csv"),
                  ["title", "subtitle", "extra", "Book-Title", "Book-Author", "Publisher"])
    clean_csv(os.path.join(ROOT, "data", "external", "movietweetings", "items.csv"),
              ["title"])
    clean_csv(os.path.join(ROOT, "data", "processed_global", "items_global.csv"),
              ["title", "subtitle", "extra"])
    print("done")
