# -*- coding: utf-8 -*-
"""
资源富化服务（enrichment）：封面 / 简介 / 外部链接的按需抓取与合成。

数据源（按域）：
  books   封面：BX Image-URL-M（已导入 items_meta.image_url）
          简介：OpenLibrary Read API（外部，超时/不可达时回退元数据合成）
          链接：OpenLibrary 阅读页 + Amazon 购买搜索（ISBN 构造，无需抓取）
  movies  封面+主演：IMDb Suggestion API（免 key：
          https://v3.sg.media-imdb.com/suggestion/x/{query}.json，响应含海报
          CDN URL 与 width/height 分辨率元数据，供质量审核）
          链接：IMDb 详情页（links.csv imdbId 构造）
  courses 封面：无公开封面 API（Udemy 服务器端 403）-> 前端类目矢量封面
          简介：基于课程元数据（标题/类目/难度/热度）模板合成
          链接：Udemy 官方课程页（items_meta.source_url）

简介 sections 格式（前后端与 item_enrichment 表共用）：
  {"sections": [{"label": "...", "text": "..."}], "source": "openlibrary|imdb|synthetic|admin"}
链接格式：
  [{"label": "...", "url": "https://...", "type": "read|buy|info|study"}]

说明：外部抓取（OpenLibrary）受服务器网络限制时自动回退合成简介并在
source 字段如实标注；管理后台支持手动编辑覆盖（manual=1，不会被自动抓取覆盖）。
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (recsys-thesis; contact: student)"}
SUGGEST = "https://v3.sg.media-imdb.com/suggestion/x/{}.json"
OPENLIB = "https://openlibrary.org/api/books?bibkeys=ISBN:{}&format=json&jscmd=data"

_items = {}   # domain -> DataFrame(item_id -> row)
_links = {}   # movies: item_id -> imdbId


def _load(domain: str):
    if domain in _items:
        return
    if domain == "books":
        m = pd.read_csv(os.path.join(ROOT, "data", "processed_real", "items_meta.csv"))
        m = m.rename(columns={"Book-Title": "title", "Book-Author": "subtitle",
                              "Publisher": "extra"})
        m["image_url"] = m.get("image_url", "")
    elif domain == "courses":
        m = pd.read_csv(os.path.join(ROOT, "data", "processed_courses", "items_meta.csv"))
        m["source_url"] = m.get("source_url", "")
    else:
        m = pd.read_csv(os.path.join(ROOT, "data", "processed_movies", "items_meta.csv"))
        m["poster_url"] = m.get("poster_url", "")
    m = m.set_index("item_id")
    _items[domain] = m
    if domain == "movies":
        lk = pd.read_csv(os.path.join(ROOT, "data", "ml-latest-small", "links.csv"))
        _links["map"] = lk.dropna(subset=["imdbId"]).set_index("movieId")["imdbId"].astype(int).to_dict()


def _fetch_json(url: str, timeout: float = 4.0):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _norm_title(title: str) -> str:
    """'Matrix, The (1999)' -> 'the matrix'（IMDb suggest 检索用）"""
    t = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
    m = re.match(r"^(.*),\s+(The|A|An|Les|La|Le|Los|Das|Der|Il|El)$", t)
    if m:
        t = f"{m.group(2)} {m.group(1)}"
    return t.strip().lower()


# ---------------------------------------------------------------------------
# 各域富化
# ---------------------------------------------------------------------------
# 国内站点搜索模板（title 参数 URL 编码后拼接；国内优先原则：列表顺序即优先级）
CN_SEARCH = {
    "douban_book": "https://book.douban.com/subject_search?search_text={}",
    # 微信读书网页版无公开搜索页路由，/web/search/global 为 XHR 数据接口
    # （浏览器直开显示 JSON 且无 charset 声明，国产浏览器按 GBK 解码 UTF-8 产生乱码）。
    # 改走平台后端代理：服务端 UTF-8 检索并 302 直达书籍详情页（WereadController）。
    "weread": "/api/weread?q={}",
    "jd": "https://search.jd.com/Search?keyword={}&enc=utf-8",
    "dangdang": "http://search.dangdang.com/?key={}",
    "douban_movie": "https://search.douban.com/movie/subject_search?search_text={}",
    "bilibili": "https://search.bilibili.com/all?keyword={}",
    "qq_video": "https://v.qq.com/x/search/?q={}",
    "iqiyi": "https://so.iqiyi.com/so/q_{}",
    "icourse163": "https://www.icourse163.org/search.htm?search={}",
    "xuetangx": "https://www.xuetangx.com/search?query={}",
}
# Udemy 类目 -> 中文检索词（国内课程平台检索用）
CAT_QUERY = {"Web Development": "编程开发", "Business Finance": "商业金融",
             "Musical Instruments": "音乐演奏", "Graphic Design": "平面设计"}


def _q(s: str) -> str:
    return urllib.parse.quote(str(s))


def _links_books(row) -> list[dict]:
    """图书链接：国内站点优先（豆瓣/微信读书/京东/当当），海外 OpenLibrary/Amazon 保留可选项"""
    title = str(row.get("title", "")).strip()
    links = []
    if title:
        links.append({"label": "豆瓣读书", "type": "info",
                      "url": CN_SEARCH["douban_book"].format(_q(title))})
        links.append({"label": "微信读书 · 直达书页", "type": "read",
                      "url": CN_SEARCH["weread"].format(_q(title))})
        links.append({"label": "京东图书", "type": "buy",
                      "url": CN_SEARCH["jd"].format(_q(title))})
        links.append({"label": "当当图书", "type": "buy",
                      "url": CN_SEARCH["dangdang"].format(_q(title))})
    isbn = str(row.get("ISBN", ""))
    if isbn and isbn not in ("nan", ""):
        links.append({"label": "OpenLibrary（海外）", "type": "read",
                      "url": f"https://openlibrary.org/isbn/{isbn}"})
        links.append({"label": "Amazon（海外）", "type": "buy",
                      "url": f"https://www.amazon.com/s?k={isbn}"})
    return links


def _enrich_books(row) -> dict:
    isbn = str(row.get("ISBN", ""))
    cover = None
    if str(row.get("image_url", "")) not in ("nan", ""):
        cover = {"url": str(row["image_url"]), "width": None, "height": None,
                 "source": "book-crossing"}
    sections, source = [], "synthetic"
    # OpenLibrary 简介（外部，受限时回退）
    try:
        data = _fetch_json(OPENLIB.format(isbn), timeout=4)
        rec = data.get(f"ISBN:{isbn}", {})
        desc = (rec.get("excerpts") or [{}])[0].get("text") or rec.get("notes") or ""
        if not desc:
            desc = (rec.get("subjects") or [""])[0]
        if desc:
            sections.append({"label": "内容摘要", "text": str(desc)[:1200]})
            source = "openlibrary"
    except Exception:
        pass
    if not sections:
        sections.append({
            "label": "内容摘要",
            "text": f"《{row['title']}》由 {row.get('subtitle', '知名作者')} 创作，"
                    f"{row.get('extra', '')} 出版发行。更多详细内容简介可在管理后台补充，"
                    f"或通过下方链接查看 OpenLibrary 书目信息。"})
    sections.insert(0, {"label": "作者信息",
                        "text": f"作者：{row.get('subtitle', '—')}｜出版社：{row.get('extra', '—')}"})
    sections.append({"label": "推荐理由",
                     "text": "该书的题材与内容特征已进入系统统一兴趣画像，"
                             "当其与你的跨域兴趣标签匹配时会被优先推荐。"})
    return {"cover": cover, "source": source,
            "sections": sections, "links": _links_books(row)}


GENRE_ZH = {"Action": "动作", "Adventure": "冒险", "Animation": "动画", "Children": "儿童",
            "Comedy": "喜剧", "Crime": "犯罪", "Documentary": "纪录片", "Drama": "剧情",
            "Fantasy": "奇幻", "Film-Noir": "黑色", "Horror": "恐怖", "IMAX": "IMAX",
            "Musical": "音乐剧", "Mystery": "悬疑", "Romance": "爱情", "Sci-Fi": "科幻",
            "Thriller": "惊悚", "War": "战争", "Western": "西部"}


def _enrich_movies(row) -> dict:
    item_id = int(row.name)
    title, year = str(row["title"]), str(row.get("extra", ""))
    cover, cast = None, None
    try:
        q = urllib.parse.quote(_norm_title(title).replace(" ", "_"))
        data = _fetch_json(SUGGEST.format(q), timeout=4)
        want = re.sub(r"\s*\(\d{4}\)$", "", title).strip().lower()
        best = None
        for it in data.get("d", []):
            if it.get("q") != "feature":
                continue
            if it.get("l", "").strip().lower() == want:
                if not year or str(it.get("y")) == year:
                    best = it
                    break
                best = best or it
        if best is None and data.get("d"):
            for it in data["d"]:
                if it.get("l", "").lower() == want:
                    best = it
                    break
        if best:
            img = best.get("i", {})
            if img.get("imageUrl"):
                cover = {"url": img["imageUrl"], "width": img.get("width"),
                         "height": img.get("height"), "source": "imdb"}
            cast = best.get("s") or None
    except Exception:
        pass
    poster = str(row.get("poster_url", "") or "")
    if poster not in ("nan", ""):
        cover = {"url": poster, "width": None, "height": None, "source": "imdb_prefetch"}

    genres_raw = (str(row.get("subtitle", "")) or "").split()
    genres = "、".join(GENRE_ZH.get(g, g) for g in genres_raw)
    clean = re.sub(r"\s*\(\d{4}\)$", "", title)
    lead = (cast.split(",")[0] if cast else "").strip()
    sections = [{"label": "影片信息",
                 "text": f"上映时间：{year or '—'}｜类型：{genres or '—'}"}]
    if cast:
        sections.append({"label": "主演", "text": cast})
    sections.append({"label": "剧情简介",
                     "text": f"《{clean}》是一部{year}年上映的"
                             f"{genres_raw[0] if genres_raw else '电影'}题材影片"
                             + (f"，由 {lead} 等主演。" if lead else "。")
                             + "完整剧情简介可在管理后台编辑补充，或访问 IMDb 详情页查看。"})
    # 链接：国内站点优先（豆瓣/B站/腾讯视频/爱奇艺），IMDb 海外保留
    clean_title = re.sub(r"\s*\(\d{4}\)\s*$", "", str(title))
    links = [
        {"label": "豆瓣电影", "type": "info",
         "url": CN_SEARCH["douban_movie"].format(_q(clean_title))},
        {"label": "哔哩哔哩", "type": "info",
         "url": CN_SEARCH["bilibili"].format(_q(clean_title))},
        {"label": "腾讯视频", "type": "info",
         "url": CN_SEARCH["qq_video"].format(_q(clean_title))},
        {"label": "爱奇艺", "type": "info",
         "url": CN_SEARCH["iqiyi"].format(_q(clean_title))},
    ]
    imdb_id = _links.get("map", {}).get(item_id)
    if imdb_id:
        links.append({"label": "IMDb（海外）", "type": "info",
                      "url": f"https://www.imdb.com/title/tt{imdb_id:07d}/"})
    return {"cover": cover, "source": "imdb" if cover else "synthetic",
            "sections": sections, "links": links}


def _enrich_courses(row) -> dict:
    LEVEL_ZH = {"All Levels": "通用", "Beginner Level": "入门",
                "Intermediate Level": "进阶", "Expert Level": "高级"}
    CAT_ZH = {"Web Development": "网页开发", "Business Finance": "商业金融",
              "Musical Instruments": "乐器演奏", "Graphic Design": "平面设计"}
    # 中国课程平台集合（源数据 platform 字段）
    CN_PLATFORMS = {"中国大学MOOC", "学堂在线", "网易公开课", "国家高等教育智慧教育平台",
                    "国家中小学智慧教育平台", "终身教育平台"}
    subject = str(row.get("extra", ""))
    level = str(row.get("subtitle", ""))
    platform = str(row.get("platform", "") or "")
    subs = int(row.get("num_subscribers", 0) or 0)
    topic = re.sub(r"[:：].*$", "", str(row["title"])).strip()
    outlines = {
        "Web Development": ["开发环境搭建", "核心语法与页面结构", "组件与样式实战", "项目综合演练"],
        "Business Finance": ["财务与金融基础", "分析方法与模型", "案例实战", "风险与决策"],
        "Musical Instruments": ["乐器基础与乐理", "演奏技法训练", "曲目练习", "进阶表演"],
        "Graphic Design": ["设计原理与构图", "色彩与排版", "工具实战", "作品集打磨"],
        "计算机": ["计算机基础与思维", "核心原理讲解", "编程实践训练", "综合项目演练"],
        "经济管理": ["经济管理基础", "分析方法与工具", "案例实战", "决策与应用"],
        "人文历史": ["历史脉络梳理", "经典文本研读", "文化比较视野", "专题研讨"],
        "基础科学": ["科学概念建立", "原理推导详解", "实验与练习", "综合应用"],
        "考研升学": ["考情分析与规划", "核心考点精讲", "真题演练", "冲刺策略"],
        "K12教育": ["知识要点讲解", "例题精析", "同步练习", "拓展提升"],
        "生活技能": ["基础概念与准备", "方法与技巧", "实践演练", "进阶应用"],
    }.get(subject, ["基础概念", "核心方法", "实践案例", "综合应用"])
    is_cn = platform in CN_PLATFORMS or (platform and any(
        "\u4e00" <= ch <= "\u9fff" for ch in platform))
    sections = [
        {"label": "课程信息",
         "text": f"平台：{platform or 'Udemy'}｜难度：{LEVEL_ZH.get(level, level) or '通用'}｜{subs:,} 人已学习"},
        {"label": "学习目标", "text": f"掌握 {topic} 的核心概念与实践技能，"
                                      f"能够独立完成相关领域的典型任务。"},
        {"label": "课程大纲", "text": "、".join(outlines)},
        {"label": "适合人群",
         "text": ("零基础入门者" if "Beginner" in level or level == "入门" else
                  "有一定基础、希望进阶的学习者" if level in ("进阶", "高级") else "各水平学习者")
                 + f"；对 {CAT_ZH.get(subject, subject)} 方向感兴趣者优先。"},
        {"label": "讲师信息",
         "text": (f"{platform} 优质课程资源" if is_cn else
                  "Udemy 平台认证讲师（本数据渠道未含讲师署名，详见课程页）。")},
    ]
    # 链接：中国课程 = 平台官方页（国内优先）+ 国内其他平台检索；
    #        Udemy 课程 = 国内类目检索优先 + Udemy 官方页（海外保留）
    url = str(row.get("source_url", "") or "")
    links = []
    if is_cn:
        if url not in ("nan", ""):
            links.append({"label": f"{platform} · 前往学习", "type": "study", "url": url})
        links.append({"label": "中国大学MOOC 检索同类课", "type": "study",
                      "url": CN_SEARCH["icourse163"].format(_q(topic))})
        links.append({"label": "哔哩哔哩 课程检索", "type": "study",
                      "url": CN_SEARCH["bilibili"].format(_q(topic))})
    else:
        links.append({"label": "中国大学MOOC 同类中文课", "type": "study",
                      "url": CN_SEARCH["icourse163"].format(_q(CAT_QUERY.get(subject, topic)))})
        links.append({"label": "学堂在线 同类中文课", "type": "study",
                      "url": CN_SEARCH["xuetangx"].format(_q(CAT_QUERY.get(subject, topic)))})
        links.append({"label": "哔哩哔哩 课程检索", "type": "study",
                      "url": CN_SEARCH["bilibili"].format(_q(topic))})
        if url not in ("nan", ""):
            links.append({"label": "Udemy 课程页（海外）", "type": "study", "url": url})
    return {"cover": None, "source": "synthetic", "sections": sections, "links": links}


def enrich_item(domain: str, item_id: int) -> dict:
    """统一入口：返回 {cover, source, sections, links}；未知物品抛 KeyError。"""
    _load(domain)
    items = _items[domain]
    if item_id not in items.index:
        raise KeyError(f"物品不存在: {domain}/{item_id}")
    row = items.loc[item_id]
    t0 = time.time()
    if domain == "books":
        res = _enrich_books(row)
    elif domain == "movies":
        res = _enrich_movies(row)
    else:
        res = _enrich_courses(row)
    res["title"] = str(row["title"])
    res["latency_ms"] = round((time.time() - t0) * 1000, 1)
    return res
