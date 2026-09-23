# -*- coding: utf-8 -*-
"""电影封面兜底：IMDb 抓取后仍缺失的海报 → PIL 程序化电影海报

设计：影域靛蓝渐变 + 片名/年份大字排版 + 中文类型标签，1200×1600。
版权：平台自设计（无版权风险），视觉规范与域渐变一致。
输出：data/covers/movies/{item_id}.png；回写 items_meta.csv + MySQL poster_url。
用法：py -3 fill_movie_covers.py
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pymysql
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
META = os.path.join(ROOT, "data", "processed_movies", "items_meta.csv")
OUT = os.path.join(ROOT, "data", "covers", "movies")
W, H = 1200, 1600

FB = r"C:\Windows\Fonts\segoeuib.ttf"
FM = r"C:\Windows\Fonts\segoeui.ttf"
ZH = r"C:\Windows\Fonts\msyh.ttc"

GRAD = ((52, 72, 160), (14, 18, 52))  # 影域靛蓝
GENRE_ZH = {"Action": "动作", "Adventure": "冒险", "Animation": "动画", "Children": "儿童",
            "Comedy": "喜剧", "Crime": "犯罪", "Documentary": "纪录片", "Drama": "剧情",
            "Fantasy": "奇幻", "Film-Noir": "黑色", "Horror": "恐怖", "IMAX": "IMAX",
            "Musical": "音乐剧", "Mystery": "悬疑", "Romance": "爱情", "Sci-Fi": "科幻",
            "Thriller": "惊悚", "War": "战争", "Western": "西部"}


def f(p, s):
    return ImageFont.truetype(p, s) if os.path.exists(p) else ImageFont.load_default()


def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for ch in str(text):
        if draw.textlength(cur + ch, font=font) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return [l.strip() for l in lines if l.strip()][:5]


def make_cover(title, year, genres, path):
    img = Image.new("RGB", (W, H), GRAD[1])
    for y in range(H):
        t = y / H
        img.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(*GRAD)))
    base = img.crop((0, 0, 1, H)).resize((W, H)).filter(ImageFilter.GaussianBlur(2))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W * 0.45, -H * 0.2, W * 1.4, H * 0.3], fill=(90, 120, 255, 60))
    base = Image.alpha_composite(base.convert("RGBA"),
                                  glow.filter(ImageFilter.GaussianBlur(70)))
    draw = ImageDraw.Draw(base, "RGBA")

    clean = re.sub(r"\s*\(\d{4}\)\s*$", "", str(title)).strip()
    # 顶部类型标签（中文，至多 3 个）
    gs = [GENRE_ZH.get(g, g) for g in str(genres or "").split()[:3] if g and g != "nan"]
    if gs:
        tag = " · ".join(gs)
        tw = draw.textlength(tag, font=f(ZH, 38))
        draw.rounded_rectangle([(W - tw) / 2 - 26, 150, (W + tw) / 2 + 26, 216],
                               radius=34, fill=(255, 255, 255, 28),
                               outline=(255, 255, 255, 80), width=2)
        draw.text(((W - tw) / 2, 160), tag, font=f(ZH, 38), fill=(235, 240, 255))
    # 片名
    tfont = f(FB, 88)
    lines = wrap(draw, clean, tfont, W - 220)
    if len(lines) >= 4:
        tfont = f(FB, 66)
        lines = wrap(draw, clean, tfont, W - 220)
    y = (H - len(lines) * tfont.size * 1.24 - 180) // 2 + 60
    for ln in lines:
        lw = draw.textlength(ln, font=tfont)
        draw.text(((W - lw) / 2 + 3, y + 3), ln, font=tfont, fill=(0, 0, 0, 120))
        draw.text(((W - lw) / 2, y), ln, font=tfont, fill=(255, 255, 255))
        y += int(tfont.size * 1.24)
    # 年份大字
    if year and str(year) not in ("nan", ""):
        yf = f(FB, 130)
        yw = draw.textlength(str(year), font=yf)
        draw.text(((W - yw) / 2 + 4, y + 40 + 4), str(year), font=yf, fill=(0, 0, 0, 100))
        draw.text(((W - yw) / 2, y + 40), str(year), font=yf, fill=(170, 190, 255))
    # 底部标签
    lab = "光影世界 · 智荐"
    lw = draw.textlength(lab, font=f(ZH, 34))
    draw.text(((W - lw) / 2, H - 200), lab, font=f(ZH, 34), fill=(190, 200, 235, 200))
    base.convert("RGB").save(path, "PNG", optimize=True)


def main():
    meta = pd.read_csv(META)
    if "poster_url" not in meta.columns:
        meta["poster_url"] = ""
    todo = meta[meta["poster_url"].fillna("").astype(str).str.strip() == ""]
    print(f">> IMDb 抓取后仍缺海报 {len(todo)} 部 → 程序化海报兜底")
    if not len(todo):
        return
    os.makedirs(OUT, exist_ok=True)
    conn = pymysql.connect(host="127.0.0.1", user="root", password="root",
                            database="recsys", charset="utf8mb4")
    n = 0
    with conn.cursor() as cur:
        for idx, row in todo.iterrows():
            iid = int(row["item_id"])
            png = os.path.join(OUT, f"{iid}.png")
            if not os.path.exists(png):
                make_cover(str(row["title"]), str(row.get("extra", "")),
                           str(row.get("subtitle", "")), png)
            meta.at[idx, "poster_url"] = f"/covers/movies/{iid}.png"
            cur.execute("UPDATE movie SET poster_url=%s WHERE item_id=%s",
                        (f"/covers/movies/{iid}.png", iid))
            n += 1
        conn.commit()
    conn.close()
    meta.to_csv(META, index=False)
    print(f">> 完成：程序化电影海报 {n} 张（/covers/movies/），覆盖率 100%")


if __name__ == "__main__":
    main()
