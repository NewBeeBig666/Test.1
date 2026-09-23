# -*- coding: utf-8 -*-
"""图书封面全量补充：

  1) book 表（BX 目录）外链存活检测（并发）：死链/缺失 → PIL 程序化封面
  2) world_content 图书条目（44 条名著）→ PIL 典藏版封面（中文书名 + 区域配色）

版权规范：保留的数据集自带封面（Amazon CDN，BX 数据集授权字段）为官方资源；
程序化封面为平台自设计（无版权风险），视觉规范与平台渐变体系一致。

输出：data/covers/books/{item_id}.png、data/covers/world/{id}.png（1200×1600）
回写：items_meta.csv（image_url）+ MySQL book.image_url / world_content.image_url（新列）
用法：py -3 fill_book_covers.py [--check-only]
"""
from __future__ import annotations

import argparse
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import pymysql
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
META = os.path.join(ROOT, "data", "processed_real", "items_meta.csv")
BOOK_DIR = os.path.join(ROOT, "data", "covers", "books")
WORLD_DIR = os.path.join(ROOT, "data", "covers", "world")
W, H = 1200, 1600
UA = {"User-Agent": "Mozilla/5.0 (recsys-thesis; contact: student)"}

FB = r"C:\Windows\Fonts\segoeuib.ttf"
FM = r"C:\Windows\Fonts\segoeui.ttf"
ZB = r"C:\Windows\Fonts\msyhbd.ttc"
ZH = r"C:\Windows\Fonts\msyh.ttc"


def f(p, s):
    return ImageFont.truetype(p, s) if os.path.exists(p) else ImageFont.load_default()


# ---------------------------------------------------------------------------
# 1) BX 图书外链存活检测（并发）
# ---------------------------------------------------------------------------
def alive(url: str) -> bool:
    u = str(url or "").strip()
    if not u or u == "nan":
        return False
    if u.startswith("/covers/"):  # 平台本地程序化封面（必然可用）
        return True
    for attempt in range(2):  # 重试一次，规避 CDN 限流误报
        try:
            req = urllib.request.Request(u, headers={**UA, "Range": "bytes=0-0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                return r.status in (200, 206)
        except Exception:
            if attempt == 0:
                time.sleep(0.8)
    return False


def check_books(meta: pd.DataFrame):
    """并发检测全部 image_url，返回 (dead_ids, ok_ids)"""
    urls = meta["image_url"].fillna("").astype(str).str.strip()
    dead, ok = [], []
    with ThreadPoolExecutor(max_workers=32) as ex:
        futs = {ex.submit(alive, u): i for i, u in zip(meta.index, urls)}
        done = 0
        for fut in as_completed(futs):
            i = futs[fut]
            (ok if fut.result() else dead).append(i)
            done += 1
            if done % 1000 == 0:
                print(f"    检测 {done}/{len(meta)}：失效 {len(dead)}")
    return dead, ok


# ---------------------------------------------------------------------------
# 2) PIL 程序化封面
# ---------------------------------------------------------------------------
BOOK_GRAD = ((138, 90, 59), (44, 26, 16))       # 图书域暖棕
WORLD_GRADS = {  # 区域典藏配色
    "中国": ((128, 30, 30), (54, 12, 12)),
    "日本": ((96, 60, 130), (36, 20, 56)),
    "韩国": ((24, 96, 110), (8, 36, 44)),
    "欧洲": ((30, 70, 130), (10, 26, 54)),
    "拉美": ((170, 88, 20), (64, 30, 6)),
    "世界其他": ((60, 96, 60), (18, 36, 20)),
}


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


def base_canvas(grad):
    top, bottom = grad
    img = Image.new("RGB", (W, H), bottom)
    for y in range(H):
        t = y / H
        img.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    base = img.crop((0, 0, 1, H)).resize((W, H)).filter(ImageFilter.GaussianBlur(2))
    # 顶部光晕（视觉层次）
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    acc = tuple(min(255, c + 70) for c in top) + (60,)
    gd.ellipse([W * 0.5, -H * 0.2, W * 1.4, H * 0.3], fill=acc)
    return Image.alpha_composite(base.convert("RGBA"),
                                  glow.filter(ImageFilter.GaussianBlur(70)))


def classic_frame(draw, color=(255, 250, 240, 150)):
    """经典书页双线边框"""
    draw.rectangle([64, 64, W - 64, H - 64], outline=color, width=3)
    draw.rectangle([84, 84, W - 84, H - 84], outline=color[:3] + (70,), width=1)


def make_book_cover(title, author, path):
    base = base_canvas(BOOK_GRAD)
    draw = ImageDraw.Draw(base, "RGBA")
    classic_frame(draw)
    tfont = f(FB, 86)
    afont = f(FM, 44)
    # 顶部小标签
    tag = "WORLD LIBRARY"
    tw = draw.textlength(tag, font=f(FM, 34))
    draw.text(((W - tw) / 2, 150), tag, font=f(FM, 34), fill=(240, 220, 190, 200))
    # 书名（居中自适应）
    lines = wrap(draw, title, tfont, W - 260)
    if len(lines) >= 4:
        lines = wrap(draw, title, f(FB, 68), W - 260)
        tfont = f(FB, 68)
    y = (H - len(lines) * tfont.size * 1.25) // 2 - 40
    for ln in lines:
        lw = draw.textlength(ln, font=tfont)
        draw.text(((W - lw) / 2 + 3, y + 3), ln, font=tfont, fill=(0, 0, 0, 120))
        draw.text(((W - lw) / 2, y), ln, font=tfont, fill=(255, 250, 240))
        y += int(tfont.size * 1.25)
    # 作者
    a = str(author or "").strip()
    if a and a != "nan":
        aw = draw.textlength(a, font=afont)
        draw.text(((W - aw) / 2, y + 56), a, font=afont, fill=(220, 196, 165, 230))
    base.convert("RGB").save(path, "PNG", optimize=True)


def make_world_cover(zh, orig, region, note, path):
    base = base_canvas(WORLD_GRADS.get(region, BOOK_GRAD))
    draw = ImageDraw.Draw(base, "RGBA")
    classic_frame(draw, (255, 252, 245, 170))
    zfont = f(ZB, 96)
    hfont = f(ZH, 44)
    # 顶部：区域徽标
    label = f"{region} · 典藏"
    tw = draw.textlength(label, font=hfont)
    draw.rounded_rectangle([(W - tw) / 2 - 28, 130, (W + tw) / 2 + 28, 198],
                           radius=34, fill=(255, 255, 255, 30),
                           outline=(255, 255, 255, 90), width=2)
    draw.text(((W - tw) / 2, 142), label, font=hfont, fill=(245, 240, 230))
    # 中文名大字（1-2 行）
    lines = wrap(draw, zh, zfont, W - 240)
    if len(lines) >= 3:
        zfont = f(ZB, 72)
        lines = wrap(draw, zh, zfont, W - 240)
    y = (H - len(lines) * zfont.size * 1.3) // 2 - 60
    for ln in lines:
        lw = draw.textlength(ln, font=zfont)
        draw.text(((W - lw) / 2 + 3, y + 3), ln, font=zfont, fill=(0, 0, 0, 130))
        draw.text(((W - lw) / 2, y), ln, font=zfont, fill=(255, 252, 245))
        y += int(zfont.size * 1.3)
    # 原语言名 / 说明
    if orig:
        ow = draw.textlength(orig, font=hfont)
        draw.text(((W - ow) / 2, y + 44), orig, font=hfont, fill=(235, 225, 210, 220))
    if note:
        n = re.sub(r"\s+", " ", str(note))
        if len(n) > 42:
            n = n[:40] + "…"
        nw = draw.textlength(n, font=f(ZH, 36))
        draw.text(((W - nw) / 2, H - 240), n, font=f(ZH, 36), fill=(225, 212, 190, 200))
    base.convert("RGB").save(path, "PNG", optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true", help="仅检测不生成")
    args = ap.parse_args()

    meta = pd.read_csv(META)
    if "image_url" not in meta.columns:
        meta["image_url"] = ""
    print(f">> book 表 {len(meta)} 本，检测外链存活（并发 32）…")
    dead, ok = check_books(meta)
    print(f">> 存活 {len(ok)} / 失效或缺失 {len(dead)}")

    if not args.check_only and dead:
        os.makedirs(BOOK_DIR, exist_ok=True)
        en_font_note = f(FM, 30)
        for k, idx in enumerate(dead):
            row = meta.loc[idx]
            iid = int(row["item_id"])
            png = os.path.join(BOOK_DIR, f"{iid}.png")
            if not os.path.exists(png):
                make_book_cover(str(row.get("Book-Title", row.get("title", ""))),
                                str(row.get("Book-Author", row.get("subtitle", ""))), png)
            meta.at[idx, "image_url"] = f"/covers/books/{iid}.png"
            if (k + 1) % 100 == 0:
                print(f"    程序化封面 {k + 1}/{len(dead)}")
        meta.to_csv(META, index=False)
        print(f">> 已生成 {len(dead)} 张程序化封面并回写 items_meta.csv")

    conn = pymysql.connect(host="127.0.0.1", user="root", password="root",
                            database="recsys", charset="utf8mb4")
    with conn.cursor() as cur:
        if not args.check_only and dead:
            for idx in dead:
                iid = int(meta.at[idx, "item_id"])
                cur.execute("UPDATE book SET image_url=%s WHERE item_id=%s",
                            (f"/covers/books/{iid}.png", iid))
            conn.commit()
            print(f">> MySQL book.image_url 已更新 {len(dead)} 行（程序化封面）")

        # 2) world_content 图书：典藏封面
        if not args.check_only:
            cur.execute("""SELECT COUNT(*) FROM information_schema.COLUMNS
                          WHERE TABLE_SCHEMA='recsys' AND TABLE_NAME='world_content'
                            AND COLUMN_NAME='image_url'""")
            if not cur.fetchone()[0]:
                cur.execute("ALTER TABLE world_content ADD COLUMN image_url VARCHAR(512)")
                conn.commit()
            cur.execute("SELECT id, title, subtitle, note, region FROM world_content "
                        "WHERE domain='books'")
            rows = cur.fetchall()
            os.makedirs(WORLD_DIR, exist_ok=True)
            n = 0
            for wid, title, subtitle, note, region in rows:
                png = os.path.join(WORLD_DIR, f"{wid}.png")
                zh = re.sub(r"\s+", " ", str(note)).split("《")[-1].split("》")[0] \
                    if "《" in str(note) else re.sub(r"\s+", " ", str(note)).split(" · ")[0]
                orig = re.sub(r"\s+", " ", str(title)) if str(title) != zh else None
                if not os.path.exists(png):
                    make_world_cover(zh, orig, region, note, png)
                cur.execute("UPDATE world_content SET image_url=%s WHERE id=%s",
                            (f"/covers/world/{wid}.png", wid))
                n += 1
            conn.commit()
            print(f">> world_content 图书典藏封面 {n} 张（/covers/world/）")
    conn.close()
    print("done")


if __name__ == "__main__":
    main()
