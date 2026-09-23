# -*- coding: utf-8 -*-
"""
课程封面程序化设计生成（平台视觉风格统一）

为全部无封面课程生成真实 PNG 封面文件：
  - 尺寸 1200×1600（3:4 匹配卡片；宽≥1080、高≥720，满足分辨率要求）
  - 类目差异化设计模板：课程绿主渐变（与平台 --courses 色系一致）
    + 类目辅助色 + 几何视觉元素（代码括号/图表/音符/画笔）
  - 内容：课程标题（自动换行排版）、难度/平台徽标条、类目标签
  - 输出 data/covers/courses/{item_id}.png，并更新 MySQL course.poster_url

字体：Windows 内置 Segoe UI Bold（英文标题）+ 微软雅黑（中文标签）。
用法：py -3 generate_course_covers.py [--limit 100]
"""
from __future__ import annotations

import argparse
import os

import pandas as pd
import pymysql
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "data", "covers", "courses")
META = os.path.join(ROOT, "data", "processed_courses", "items_meta.csv")
W, H = 1200, 1600

FONTS = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]
ZH_FONTS = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"]


def load_font(candidates, size):
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# 类目设计令牌：类目专属双色渐变（色彩层次升级）+ 辅助色 + 图标类型
THEMES = {
    "Web Development": dict(grad=((36, 100, 200), (10, 28, 84)), accent=(96, 180, 255), icon="code",
                            label="网页开发"),
    "Business Finance": dict(grad=((158, 108, 26), (56, 36, 6)), accent=(255, 198, 92), icon="chart",
                             label="商业金融"),
    "Musical Instruments": dict(grad=((168, 74, 58), (58, 22, 18)), accent=(255, 152, 122), icon="note",
                                label="乐器演奏"),
    "Graphic Design": dict(grad=((134, 62, 184), (48, 18, 88)), accent=(222, 144, 255), icon="brush",
                           label="平面设计"),
}
LEVEL_ZH = {"All Levels": "通用", "Beginner Level": "入门", "Intermediate Level": "进阶",
            "Expert Level": "高级"}


def draw_icon(draw, kind, cx, cy, r, color):
    """几何视觉元素（纯 PIL 绘制，矢量级清晰）"""
    c = color + (255,)
    if kind == "code":  # </> 代码括号
        for sgn in (-1, 1):
            pts = [(cx + sgn * r * 0.55, cy - r), (cx + sgn * r, cy),
                   (cx + sgn * r * 0.55, cy + r)]
            draw.line(pts, fill=c, width=max(10, r // 6), joint="curve")
        draw.line([(cx - r * 0.3, cy), (cx + r * 0.3, cy)], fill=c, width=max(10, r // 6))
    elif kind == "chart":  # 上升柱状
        for i, (dx, hh) in enumerate([(-0.7, 0.45), (-0.1, 0.75), (0.5, 1.05)]):
            x = cx + dx * r
            draw.rounded_rectangle([x - r * 0.16, cy + r - hh * r * 1.4,
                                    x + r * 0.16, cy + r], radius=8, fill=c)
        draw.line([(cx - r * 0.8, cy + r * 0.4), (cx, cy - r * 0.15), (cx + r * 0.8, cy - r)],
                  fill=(255, 255, 255, 90), width=6)
    elif kind == "note":  # 音符
        draw.ellipse([cx - r * 0.9, cy + r * 0.1, cx - r * 0.1, cy + r * 0.9], fill=c)
        draw.ellipse([cx + r * 0.15, cy - r * 0.1, cx + r * 0.95, cy + r * 0.7], fill=c)
        draw.rectangle([cx - r * 0.25, cy - r, cx - r * 0.05, cy + r * 0.5], fill=c)
        draw.rectangle([cx + r * 0.8, cy - r * 1.2, cx + r, cy + r * 0.3], fill=c)
        draw.rectangle([cx - r * 0.25, cy - r, cx + r, cy - r * 0.78], fill=c)
    else:  # brush 画笔
        draw.line([(cx - r * 0.7, cy + r * 0.7), (cx + r * 0.45, cy - r * 0.45)],
                  fill=c, width=max(12, r // 5))
        draw.polygon([(cx + r * 0.45, cy - r * 0.45), (cx + r * 0.95, cy - r * 0.95),
                      (cx + r * 0.78, cy - r * 0.18)], fill=(255, 255, 255, 140))
        draw.ellipse([cx - r * 0.95, cy + r * 0.45, cx - r * 0.45, cy + r * 0.95], fill=c)


def wrap_title(draw, text, font, max_w):
    lines, cur = [], ""
    for ch in text.replace("\r", " ").replace("\n", " "):
        if ch == " " and not cur:
            continue
        if draw.textlength(cur + ch, font=font) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return [l.strip() for l in lines if l.strip()][:5]


def make_cover(row, zh_font, en_font, en_mid, tag_font):
    subject = str(row.get("extra", "Course"))
    theme = THEMES.get(subject, dict(grad=((60, 120, 160), (20, 40, 70)),
                                     accent=(140, 190, 230), icon="code", label="综合课程"))
    acc = theme["accent"]
    top, bottom = theme["grad"]

    img = Image.new("RGB", (W, H), bottom)
    # 类目专属双色渐变
    for y in range(H):
        t = y / H
        img.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    grad = img.crop((0, 0, 1, H)).resize((W, H))
    base = grad.filter(ImageFilter.GaussianBlur(2))
    draw = ImageDraw.Draw(base, "RGBA")

    # 类目辅助色氛围（右上角光晕）
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W * 0.55, -H * 0.18, W * 1.35, H * 0.35], fill=acc + (70,))
    gd.ellipse([-W * 0.35, H * 0.72, W * 0.35, H * 1.3], fill=acc + (45,))
    base = Image.alpha_composite(base.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(60)))
    draw = ImageDraw.Draw(base, "RGBA")

    # 顶部：几何图标 + 中文类目标签
    draw_icon(draw, theme["icon"], W // 2, 400, 150, (255, 255, 255))
    label = theme["label"]
    tw = draw.textlength(label, font=zh_font)
    draw.rounded_rectangle([(W - tw) / 2 - 30, 636, (W + tw) / 2 + 30, 716],
                           radius=40, fill=(255, 255, 255, 36),
                           outline=(255, 255, 255, 90), width=2)
    draw.text(((W - tw) / 2, 652), label, font=zh_font, fill=(240, 250, 255))

    # 标题（自适应换行 + 字号收缩）
    title = str(row.get("title", "")).strip()
    font = en_font
    lines = wrap_title(draw, title, font, W - 180)
    if len(lines) >= 5:
        font = en_mid
        lines = wrap_title(draw, title, font, W - 180)
    y = 830
    for ln in lines:
        lw = draw.textlength(ln, font=font)
        draw.text(((W - lw) / 2 + 3, y + 3), ln, font=font, fill=(0, 0, 0, 110))
        draw.text(((W - lw) / 2, y), ln, font=font, fill=(255, 255, 255))
        y += int(font.size * 1.22)

    # 底部信息条（中文）
    bar_y = H - 220
    draw.rectangle([0, bar_y, W, H], fill=(8, 14, 28, 205))
    level = str(row.get("subtitle", "") or "All Levels")
    if level == "nan":
        level = "All Levels"
    level = LEVEL_ZH.get(level, level.replace(" Level", ""))
    info = f"{level}难度 · Udemy"
    iw = draw.textlength(info, font=zh_font)
    draw.text(((W - iw) / 2, bar_y + 60), info, font=zh_font, fill=(220, 232, 245))
    sub = row.get("num_subscribers", 0)
    sub = 0 if sub is None or pd.isna(sub) else int(float(sub))
    sw = draw.textlength(f"{sub:,} 人已学习", font=zh_font)
    draw.text(((W - sw) / 2, bar_y + 128), f"{sub:,} 人已学习",
              font=zh_font, fill=(170, 190, 210))
    return base.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="仅生成前 N 张（调试）")
    args = ap.parse_args()

    meta = pd.read_csv(META)
    os.makedirs(OUT_DIR, exist_ok=True)
    en_font = load_font(FONTS, 88)
    en_mid = load_font(FONTS, 66)
    zh_font = load_font(ZH_FONTS, 46)
    tag_font = load_font(FONTS, 40)

    targets = meta if not args.limit else meta.head(args.limit)
    n = 0
    for _, row in targets.iterrows():
        path = os.path.join(OUT_DIR, f"{int(row['item_id'])}.png")
        if os.path.exists(path):
            continue
        make_cover(row, zh_font, en_font, en_mid, tag_font).save(path, "PNG", optimize=True)
        n += 1
        if n % 200 == 0:
            print(f"    已生成 {n} 张")
    print(f">> 封面生成完成：本次 {n} 张，目录 {OUT_DIR}")

    # 更新 MySQL course.poster_url
    conn = pymysql.connect(host="127.0.0.1", user="root", password="root",
                            database="recsys", charset="utf8mb4")
    with conn.cursor() as cur:
        for _, row in meta.iterrows():
            cur.execute("UPDATE course SET poster_url=%s WHERE item_id=%s",
                        (f"/covers/courses/{int(row['item_id'])}.png", int(row["item_id"])))
    conn.commit()
    conn.close()
    print(f">> MySQL course.poster_url 已指向本地封面（/covers/courses/{{id}}.png）")


if __name__ == "__main__":
    main()
