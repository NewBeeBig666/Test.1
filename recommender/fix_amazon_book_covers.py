# -*- coding: utf-8 -*-
"""美国图书死链封面修复：

images.amazon.com 旧版图床已全面停服（HTTP 403），book 表中 9017 条
BX 数据集外链全部失效。本脚本将其替换为平台自设计的程序化封面：

  1) 查询 image_url LIKE 'http://images.amazon.com%' 的图书
  2) PIL 生成 450×600 JPEG 封面（书名 + 作者，暖棕渐变，与平台视觉一致）
     —— 小体积（~20KB/张）保证 <2s 加载，本地静态资源无 CDN 依赖
  3) 回写 MySQL book.image_url = /covers/books/{item_id}.jpg

已有的本地封面（/covers/books/*.png，68 张）与电影海报（m.media-amazon.com，
实测可达）不受影响。
用法：py -3 fix_amazon_book_covers.py
"""
from __future__ import annotations

import os
import re

import pymysql
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
BOOK_DIR = os.path.join(ROOT, "data", "covers", "books")
W, H = 450, 600  # 卡片显示宽最大 210px，450×600 已满足 2x 高清屏
JPG_EXT = ".jpg"

FB = r"C:\Windows\Fonts\segoeuib.ttf"
FM = r"C:\Windows\Fonts\segoeui.ttf"

BOOK_GRAD = ((138, 90, 59), (44, 26, 16))  # 图书域暖棕（与平台渐变体系一致）


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
    return [l.strip() for l in lines if l.strip()][:4]


def base_canvas(grad):
    top, bottom = grad
    img = Image.new("RGB", (W, H), bottom)
    for y in range(H):
        t = y / H
        img.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    base = img.crop((0, 0, 1, H)).resize((W, H)).filter(ImageFilter.GaussianBlur(1))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    acc = tuple(min(255, c + 70) for c in top) + (60,)
    gd.ellipse([W * 0.5, -H * 0.2, W * 1.4, H * 0.3], fill=acc)
    return Image.alpha_composite(base.convert("RGBA"),
                                 glow.filter(ImageFilter.GaussianBlur(28)))


def make_cover(title, author, path):
    base = base_canvas(BOOK_GRAD)
    draw = ImageDraw.Draw(base, "RGBA")
    # 经典书页双线边框（缩放版）
    draw.rectangle([24, 24, W - 24, H - 24], outline=(255, 250, 240, 150), width=2)
    draw.rectangle([32, 32, W - 32, H - 32], outline=(255, 250, 240, 70), width=1)
    # 顶部小标签
    tag = "CLASSIC LIBRARY"
    tw = draw.textlength(tag, font=f(FM, 14))
    draw.text(((W - tw) / 2, 58), tag, font=f(FM, 14), fill=(240, 220, 190, 200))
    # 书名（居中自适应）
    tfont = f(FB, 34)
    lines = wrap(draw, title, tfont, W - 100)
    if len(lines) >= 4:
        tfont = f(FB, 26)
        lines = wrap(draw, title, tfont, W - 100)
    y = (H - len(lines) * tfont.size * 1.25) // 2 - 16
    for ln in lines:
        lw = draw.textlength(ln, font=tfont)
        draw.text(((W - lw) / 2 + 1, y + 1), ln, font=tfont, fill=(0, 0, 0, 120))
        draw.text(((W - lw) / 2, y), ln, font=tfont, fill=(255, 250, 240))
        y += int(tfont.size * 1.25)
    # 作者
    a = str(author or "").strip()
    if a and a != "nan":
        a = re.sub(r"\s+", " ", a)[:36]
        afont = f(FM, 17)
        aw = draw.textlength(a, font=afont)
        draw.text(((W - aw) / 2, y + 20), a, font=afont, fill=(220, 196, 165, 230))
    base.convert("RGB").save(path, "JPEG", quality=82, optimize=True)


def main():
    conn = pymysql.connect(host="127.0.0.1", user="root",
                            password=os.environ.get("DB_PASSWORD", "root"),
                            database="recsys", charset="utf8mb4")
    with conn.cursor() as cur:
        cur.execute("SELECT item_id, title, author FROM book "
                    "WHERE image_url LIKE 'http://images.amazon.com%'")
        rows = cur.fetchall()
    print(f">> 待修复死链封面：{len(rows)} 本")

    os.makedirs(BOOK_DIR, exist_ok=True)
    done = 0
    for iid, title, author in rows:
        path = os.path.join(BOOK_DIR, f"{iid}{JPG_EXT}")
        if not os.path.exists(path):
            make_cover(str(title or ""), author, path)
        done += 1
        if done % 500 == 0:
            print(f"    生成 {done}/{len(rows)}")

    with conn.cursor() as cur:
        for iid, _, _ in rows:
            cur.execute("UPDATE book SET image_url=%s WHERE item_id=%s",
                        (f"/covers/books/{iid}{JPG_EXT}", iid))
        conn.commit()
    conn.close()
    print(f">> MySQL book.image_url 已更新 {len(rows)} 行（本地程序化封面）")
    print("done")


if __name__ == "__main__":
    main()
