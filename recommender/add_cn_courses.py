# -*- coding: utf-8 -*-
"""中国课程补充：整合国内六大教育平台 53 门课程到 course 目录

  - 平台：中国大学MOOC / 学堂在线 / 网易公开课 / 国家高等教育智慧教育平台 /
          国家中小学智慧教育平台 / 终身教育平台
  - 类目（中文）：计算机 / 经济管理 / 人文历史 / 基础科学 / 考研升学 / K12教育 / 生活技能
  - 与 Udemy 现有课程共用 course 表，探索模式自动随机混排
  - PIL 程序化封面（1200×1600，类目专属双色渐变 + 中文排版）
  - item_id 固定 2205 起（可重复执行，幂等 REPLACE）

用法：py -3 add_cn_courses.py
"""
from __future__ import annotations

import os
import urllib.parse

import pandas as pd
import pymysql
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "data", "covers", "courses")
META = os.path.join(ROOT, "data", "processed_courses", "items_meta.csv")
W, H = 1200, 1600
BASE_ID = 2205

ZB = r"C:\Windows\Fonts\msyhbd.ttc"
ZH = r"C:\Windows\Fonts\msyh.ttc"


def f(p, s):
    return ImageFont.truetype(p, s) if os.path.exists(p) else ImageFont.load_default()


# ---------------------------------------------------------------------------
# 课程清单（真实知名课程；source 为平台内搜索/首页链接）
# ---------------------------------------------------------------------------
def u_search(base, key, q):
    q = urllib.parse.quote(q)
    return {"icourse163": f"https://www.icourse163.org/search.htm?search={q}",
            "xuetangx": f"https://www.xuetangx.com/search?query={q}",
            "open163": "https://open.163.com/",
            "higher": "https://higher.smartedu.cn/",
            "basic": "https://basic.smartedu.cn/",
            "le": "https://le.ouchn.cn/"}[key] if base is None else base


def s_icourse(q):
    return f"https://www.icourse163.org/search.htm?search={urllib.parse.quote(q)}"


def s_xtx(q):
    return f"https://www.xuetangx.com/search?query={urllib.parse.quote(q)}"


COURSES = [
    # ---- 计算机（11） ----
    ("数据结构（清华大学·邓俊辉）", "通用", "计算机", "学堂在线", 9.7, 520000, s_xtx("数据结构")),
    ("C语言程序设计（浙江大学·翁恺）", "入门", "计算机", "中国大学MOOC", 9.6, 480000, s_icourse("C语言程序设计")),
    ("Python语言程序设计（北京理工大学·嵩天）", "入门", "计算机", "中国大学MOOC", 9.5, 620000, s_icourse("Python语言程序设计")),
    ("大学计算机——计算思维导论（国防科技大学）", "入门", "计算机", "中国大学MOOC", 9.3, 380000, s_icourse("大学计算机")),
    ("计算机网络（国防科技大学）", "进阶", "计算机", "中国大学MOOC", 9.4, 260000, s_icourse("计算机网络")),
    ("操作系统（哈尔滨工业大学·李治军）", "进阶", "计算机", "中国大学MOOC", 9.5, 210000, s_icourse("操作系统")),
    ("数据结构（浙江大学·陈越）", "进阶", "计算机", "中国大学MOOC", 9.6, 450000, s_icourse("数据结构")),
    ("人工智能导论（北京大学）", "通用", "计算机", "中国大学MOOC", 9.2, 180000, s_icourse("人工智能导论")),
    ("电路原理（清华大学·于歆杰）", "通用", "计算机", "学堂在线", 9.3, 150000, s_xtx("电路原理")),
    ("大数据技术原理与应用（厦门大学·林子雨）", "进阶", "计算机", "中国大学MOOC", 9.1, 170000, s_icourse("大数据技术原理与应用")),
    ("程序设计入门——Java语言（浙江大学·翁恺）", "入门", "计算机", "中国大学MOOC", 9.4, 230000, s_icourse("程序设计入门 Java语言")),
    # ---- 经济管理（8） ----
    ("金融学（中央财经大学·李健）", "通用", "经济管理", "中国大学MOOC", 9.4, 240000, s_icourse("金融学")),
    ("微观经济学（复旦大学）", "通用", "经济管理", "中国大学MOOC", 9.2, 130000, s_icourse("微观经济学")),
    ("宏观经济学（复旦大学）", "通用", "经济管理", "中国大学MOOC", 9.1, 110000, s_icourse("宏观经济学")),
    ("会计学（厦门大学）", "通用", "经济管理", "中国大学MOOC", 9.3, 160000, s_icourse("会计学")),
    ("市场营销学", "通用", "经济管理", "中国大学MOOC", 9.0, 140000, s_icourse("市场营销学")),
    ("货币金融学（中国人民大学）", "通用", "经济管理", "中国大学MOOC", 9.0, 95000, s_icourse("货币金融学")),
    ("财务分析与决策（清华大学·肖星）", "通用", "经济管理", "学堂在线", 9.5, 260000, s_xtx("财务分析与决策")),
    ("可汗学院：微观经济学", "入门", "经济管理", "网易公开课", 9.2, 880000, "https://open.163.com/"),
    # ---- 人文历史（10） ----
    ("中国古代史（北京大学·阎步克）", "通用", "人文历史", "中国大学MOOC", 9.7, 310000, s_icourse("中国古代史")),
    ("中国哲学史（武汉大学·郭齐勇）", "通用", "人文历史", "中国大学MOOC", 9.3, 120000, s_icourse("中国哲学史")),
    ("《论语》导读（复旦大学）", "通用", "人文历史", "中国大学MOOC", 9.4, 150000, s_icourse("论语导读")),
    ("唐诗宋词的人文解读（浙江大学）", "通用", "人文历史", "中国大学MOOC", 9.3, 180000, s_icourse("唐诗宋词")),
    ("文物精品与文化中国（清华大学·彭林）", "通用", "人文历史", "学堂在线", 9.2, 90000, s_xtx("文物精品与文化中国")),
    ("西方文明史导论（北京大学）", "通用", "人文历史", "中国大学MOOC", 9.1, 85000, s_icourse("西方文明史")),
    ("中国古代建筑艺术（湖南大学·柳肃）", "通用", "人文历史", "中国大学MOOC", 9.5, 200000, s_icourse("中国古代建筑艺术")),
    ("哈佛大学：幸福课", "通用", "人文历史", "网易公开课", 9.6, 1200000, "https://open.163.com/"),
    ("耶鲁大学：心理学导论", "通用", "人文历史", "网易公开课", 9.5, 960000, "https://open.163.com/"),
    ("心理学概论（清华大学·彭凯平）", "通用", "人文历史", "学堂在线", 9.4, 175000, s_xtx("心理学概论")),
    # ---- 基础科学（6） ----
    ("概率论与数理统计（浙江大学）", "通用", "基础科学", "中国大学MOOC", 9.4, 290000, s_icourse("概率论与数理统计")),
    ("线性代数", "通用", "基础科学", "中国大学MOOC", 9.2, 210000, s_icourse("线性代数")),
    ("大学物理", "通用", "基础科学", "中国大学MOOC", 9.1, 190000, s_icourse("大学物理")),
    ("微积分入门（可汗学院）", "入门", "基础科学", "网易公开课", 9.1, 720000, "https://open.163.com/"),
    ("生命科学导论", "通用", "基础科学", "中国大学MOOC", 9.0, 88000, s_icourse("生命科学导论")),
    ("基础数学（可汗学院）", "入门", "基础科学", "网易公开课", 9.0, 650000, "https://open.163.com/"),
    # ---- 考研升学（4） ----
    ("考研数学：高等数学强化", "进阶", "考研升学", "国家高等教育智慧教育平台", 9.2, 340000, "https://higher.smartedu.cn/"),
    ("考研英语（一）冲刺", "进阶", "考研升学", "国家高等教育智慧教育平台", 9.1, 280000, "https://higher.smartedu.cn/"),
    ("考研政治：马克思主义基本原理", "进阶", "考研升学", "国家高等教育智慧教育平台", 9.0, 260000, "https://higher.smartedu.cn/"),
    ("大学生职业发展与就业指导", "通用", "考研升学", "国家高等教育智慧教育平台", 8.9, 190000, "https://higher.smartedu.cn/"),
    # ---- K12教育（6） ----
    ("小学语文同步课", "入门", "K12教育", "国家中小学智慧教育平台", 9.0, 560000, "https://basic.smartedu.cn/"),
    ("小学数学同步课", "入门", "K12教育", "国家中小学智慧教育平台", 9.0, 610000, "https://basic.smartedu.cn/"),
    ("初中物理同步课", "入门", "K12教育", "国家中小学智慧教育平台", 8.9, 380000, "https://basic.smartedu.cn/"),
    ("高中数学同步课", "进阶", "K12教育", "国家中小学智慧教育平台", 9.0, 420000, "https://basic.smartedu.cn/"),
    ("高中英语同步课", "进阶", "K12教育", "国家中小学智慧教育平台", 8.9, 350000, "https://basic.smartedu.cn/"),
    ("素质教育：书法基础", "入门", "K12教育", "国家中小学智慧教育平台", 8.8, 120000, "https://basic.smartedu.cn/"),
    # ---- 生活技能（8） ----
    ("智能手机应用入门", "入门", "生活技能", "终身教育平台", 8.5, 260000, "https://le.ouchn.cn/"),
    ("手机摄影入门", "入门", "生活技能", "终身教育平台", 8.6, 180000, "https://le.ouchn.cn/"),
    ("家庭理财入门", "入门", "生活技能", "终身教育平台", 8.7, 220000, "https://le.ouchn.cn/"),
    ("职场Office高效办公", "通用", "生活技能", "终身教育平台", 8.8, 310000, "https://le.ouchn.cn/"),
    ("演讲与口才", "通用", "生活技能", "终身教育平台", 8.6, 150000, "https://le.ouchn.cn/"),
    ("营养与健康", "通用", "生活技能", "终身教育平台", 8.7, 98000, "https://le.ouchn.cn/"),
    ("太极拳入门", "入门", "生活技能", "终身教育平台", 8.5, 86000, "https://le.ouchn.cn/"),
    ("生活英语听说（清华大学·杨芳）", "入门", "生活技能", "学堂在线", 9.4, 480000, s_xtx("生活英语听说")),
]

# 类目封面主题：专属双色渐变 + 图标 + 中文标签
THEMES = {
    "计算机": dict(grad=((15, 52, 96), (22, 160, 133)), accent=(72, 201, 176), icon="code"),
    "经济管理": dict(grad=((123, 36, 28), (212, 172, 13)), accent=(255, 198, 92), icon="chart"),
    "人文历史": dict(grad=((78, 36, 122), (165, 105, 189)), accent=(222, 144, 255), icon="brush"),
    "基础科学": dict(grad=((20, 90, 50), (39, 174, 96)), accent=(130, 220, 160), icon="chart"),
    "考研升学": dict(grad=((26, 82, 118), (93, 173, 226)), accent=(160, 210, 250), icon="code"),
    "K12教育": dict(grad=((160, 64, 6), (245, 176, 65)), accent=(255, 214, 140), icon="note"),
    "生活技能": dict(grad=((22, 105, 122), (72, 159, 181)), accent=(150, 220, 235), icon="note"),
}


def draw_icon(draw, kind, cx, cy, r, color):
    c = color + (255,)
    if kind == "code":
        for sgn in (-1, 1):
            pts = [(cx + sgn * r * 0.55, cy - r), (cx + sgn * r, cy),
                   (cx + sgn * r * 0.55, cy + r)]
            draw.line(pts, fill=c, width=max(10, r // 6), joint="curve")
        draw.line([(cx - r * 0.3, cy), (cx + r * 0.3, cy)], fill=c, width=max(10, r // 6))
    elif kind == "chart":
        for dx, hh in ((-0.7, 0.45), (-0.1, 0.75), (0.5, 1.05)):
            x = cx + dx * r
            draw.rounded_rectangle([x - r * 0.16, cy + r - hh * r * 1.4,
                                    x + r * 0.16, cy + r], radius=8, fill=c)
    elif kind == "note":
        draw.ellipse([cx - r * 0.9, cy + r * 0.1, cx - r * 0.1, cy + r * 0.9], fill=c)
        draw.ellipse([cx + r * 0.15, cy - r * 0.1, cx + r * 0.95, cy + r * 0.7], fill=c)
        draw.rectangle([cx - r * 0.25, cy - r, cx - r * 0.05, cy + r * 0.5], fill=c)
        draw.rectangle([cx + r * 0.8, cy - r * 1.2, cx + r, cy + r * 0.3], fill=c)
        draw.rectangle([cx - r * 0.25, cy - r, cx + r, cy - r * 0.78], fill=c)
    else:  # brush
        draw.line([(cx - r * 0.7, cy + r * 0.7), (cx + r * 0.45, cy - r * 0.45)],
                  fill=c, width=max(12, r // 5))
        draw.polygon([(cx + r * 0.45, cy - r * 0.45), (cx + r * 0.95, cy - r * 0.95),
                      (cx + r * 0.78, cy - r * 0.18)], fill=(255, 255, 255, 140))


def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return [l.strip() for l in lines if l.strip()][:4]


def make_cover(title, level, category, platform, subs, score, path):
    theme = THEMES.get(category, THEMES["计算机"])
    acc, (top, bottom) = theme["accent"], theme["grad"]

    img = Image.new("RGB", (W, H), bottom)
    for y in range(H):
        t = y / H
        img.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    base = img.crop((0, 0, 1, H)).resize((W, H)).filter(ImageFilter.GaussianBlur(2))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W * 0.55, -H * 0.18, W * 1.35, H * 0.35], fill=acc + (70,))
    gd.ellipse([-W * 0.35, H * 0.72, W * 0.35, H * 1.3], fill=acc + (45,))
    base = Image.alpha_composite(base.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(60)))
    draw = ImageDraw.Draw(base, "RGBA")

    title_font = f(ZB, 84)
    small = f(ZH, 46)

    # 顶部：几何图标 + 类目标签
    draw_icon(draw, theme["icon"], W // 2, 380, 150, (255, 255, 255))
    tw = draw.textlength(category, font=small)
    draw.rounded_rectangle([(W - tw) / 2 - 30, 606, (W + tw) / 2 + 30, 686],
                           radius=40, fill=(255, 255, 255, 36),
                           outline=(255, 255, 255, 90), width=2)
    draw.text(((W - tw) / 2, 622), category, font=small, fill=(240, 250, 255))

    # 课程标题（中文粗体，自适应换行）
    lines = wrap(draw, title, title_font, W - 200)
    if len(lines) >= 4:
        title_font = f(ZB, 68)
        lines = wrap(draw, title, title_font, W - 200)
    y = 800
    for ln in lines:
        lw = draw.textlength(ln, font=title_font)
        draw.text(((W - lw) / 2 + 3, y + 3), ln, font=title_font, fill=(0, 0, 0, 110))
        draw.text(((W - lw) / 2, y), ln, font=title_font, fill=(255, 255, 255))
        y += int(title_font.size * 1.22)

    # 底部信息条：难度 · 平台 + 学习人数 · 推荐指数
    bar_y = H - 220
    draw.rectangle([0, bar_y, W, H], fill=(8, 14, 28, 205))
    info = f"{level}难度 · {platform}"
    iw = draw.textlength(info, font=small)
    draw.text(((W - iw) / 2, bar_y + 52), info, font=small, fill=(220, 232, 245))
    sub = f"{subs:,} 人已学习 · 推荐指数 {score}"
    sw = draw.textlength(sub, font=small)
    draw.text(((W - sw) / 2, bar_y + 122), sub, font=small, fill=(255, 214, 140))
    base.convert("RGB").save(path, "PNG", optimize=True)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    for i, (title, level, category, platform, score, subs, url) in enumerate(COURSES):
        iid = BASE_ID + i
        png = os.path.join(OUT_DIR, f"{iid}.png")
        if not os.path.exists(png):
            make_cover(title, level, category, platform, subs, score, png)
        rows.append(dict(title=title, subtitle=level, extra=category, platform=platform,
                         price=0.0, num_subscribers=subs, source_url=url,
                         item_id=iid, rec_score=score))
        if (i + 1) % 20 == 0:
            print(f"    封面 {i + 1}/{len(COURSES)}")

    # 1) 追加到 processed_courses/items_meta.csv（FastAPI 富化用）
    meta = pd.read_csv(META)
    add = pd.DataFrame(rows)
    before = len(meta)
    meta = pd.concat([meta[~meta["item_id"].isin(add["item_id"])], add], ignore_index=True)
    meta = meta.sort_values("item_id").reset_index(drop=True)
    meta.to_csv(META, index=False)
    print(f">> items_meta.csv: {before} -> {len(meta)} 行（+{len(add)} 中国课程）")

    # 2) MySQL course 表（幂等 REPLACE）
    conn = pymysql.connect(host="127.0.0.1", user="root", password=os.environ.get("DB_PASSWORD", "root"),
                            database="recsys", charset="utf8mb4")
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                "REPLACE INTO course (item_id, title, level, category, platform, price, "
                "subscribers, source_url, poster_url, rec_score) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (r["item_id"], r["title"], r["subtitle"], r["extra"], r["platform"],
                 r["price"], r["num_subscribers"], r["source_url"],
                 f"/covers/courses/{r['item_id']}.png", r["rec_score"]))
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM course")
        print(f">> course 表现共 {cur.fetchone()[0]} 门")
    conn.close()
    print("done")


if __name__ == "__main__":
    main()
