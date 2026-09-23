# -*- coding: utf-8 -*-
"""
多区域内容库构建（中国 / 日本 / 韩国 / 欧洲及其他世界区域）

数据来源（版权合规）：
  图书：Project Gutenberg 官方目录（公版书，含中日韩及世界各国文学代表作英译本）
  电影：MovieLens（元数据引用；区域内电影本就存在于 MovieLens 目录中）

产出 MySQL world_content 表：
  (domain, region, title, subtitle, extra, note, item_id, source_url)
  domain=movies 时 item_id 关联 movie 表（详情/海报/评分推荐全联动）；
  domain=books 时为 Gutenberg 公版书（source_url 指向官方阅读页）。

用法：py -3 build_world_regions.py
"""
from __future__ import annotations

import os

import pandas as pd
import pymysql

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(ROOT, "data", "raw_external", "gutenberg", "pg_catalog.csv")
MOVIES_META = os.path.join(ROOT, "data", "processed_movies", "items_meta.csv")

# ---------------------------------------------------------------------------
# 精选书单（region, 分类, 标题关键词, 中文说明）
# ---------------------------------------------------------------------------
BOOKS = [
    ("中国", "古典文学", "Analects", "孔子《论语》英译本"),
    ("中国", "古典文学", "Tao Teh King", "老子《道德经》英译本（理雅各译）"),
    ("中国", "古典文学", "Art of War", "孙子《孙子兵法》英译本"),
    ("中国", "古典文学", "Dream of the Red Chamber", "曹雪芹《红楼梦》英译本"),
    ("中国", "古典文学", "Chinese Classics", "《中国经典》理雅各译注系列"),
    ("中国", "历史文化", "Buddhistic Kingdoms", "法显《佛国记》英译本"),
    ("中国", "古典文学", "Chinese Fairy Book", "中国童话故事集"),
    ("日本", "古典文学", "tale of Genji", "紫式部《源氏物语》英译本"),
    ("日本", "古典文学", "Kwaidan", "小泉八云《怪谈》"),
    ("日本", "现代文学", "Kokoro", "夏目漱石《心》英译本"),
    ("日本", "现代文学", "Botchan", "夏目漱石《哥儿》英译本"),
    ("日本", "历史文化", "Bushido", "新渡户稻造《武士道》"),
    ("日本", "历史文化", "Book of Tea", "冈仓天心《茶之书》"),
    ("日本", "历史文化", "Old Japan", "《日本昔话》明治民间传说集"),
    ("韩国", "历史文化", "History of Korea", "《朝鲜半岛史》英译本"),
    ("欧洲", "古典文学", "Divine Comedy", "但丁《神曲》（意大利）"),
    ("欧洲", "古典文学", "Don Quixote", "塞万提斯《堂吉诃德》（西班牙）"),
    ("欧洲", "现代文学", "War and Peace", "托尔斯泰《战争与和平》（俄国）"),
    ("欧洲", "现代文学", "Crime and Punishment", "陀思妥耶夫斯基《罪与罚》（俄国）"),
    ("欧洲", "现代文学", "Brothers Karamazov", "陀思妥耶夫斯基《卡拉马佐夫兄弟》（俄国）"),
    ("欧洲", "现代文学", "Anna Karenina", "托尔斯泰《安娜·卡列尼娜》（俄国）"),
    ("欧洲", "现代文学", "Les Mis", "雨果《悲惨世界》（法国）"),
    ("欧洲", "现代文学", "Count of Monte Cristo", "大仲马《基督山伯爵》（法国）"),
    ("欧洲", "现代文学", "Madame Bovary", "福楼拜《包法利夫人》（法国）"),
    ("欧洲", "古典文学", "Faust", "歌德《浮士德》（德国）"),
    ("欧洲", "现代文学", "Pride and Prejudice", "简·奥斯汀《傲慢与偏见》（英国）"),
    ("欧洲", "现代文学", "Jane Eyre", "夏洛蒂·勃朗特《简·爱》（英国）"),
    ("世界其他", "现代文学", "Huckleberry Finn", "马克·吐温《哈克贝利·费恩历险记》（美国）"),
    ("世界其他", "现代文学", "Moby Dick", "梅尔维尔《白鲸》（美国）"),
    ("世界其他", "现代文学", "Great Gatsby", "菲茨杰拉德《了不起的盖茨比》（美国）"),
]

# ---------------------------------------------------------------------------
# 精选片单（region, 标题关键词, 年份, 中文说明）——匹配 MovieLens 目录
# ---------------------------------------------------------------------------
FILMS = [
    ("中国", "Crouching Tiger", 2000, "卧虎藏龙 · 李安武侠史诗"),
    ("中国", "Farewell My Concubine", 1993, "霸王别姬 · 陈凯歌戛纳金棕榈"),
    ("中国", "Raise the Red Lantern", 1991, "大红灯笼高高挂 · 张艺谋"),
    ("中国", "To Live", 1994, "活着 · 张艺谋"),
    ("中国", "Hero", 2002, "英雄 · 张艺谋"),
    ("中国", "Infernal Affairs", 2002, "无间道 · 刘伟强/麦兆辉"),
    ("中国", "Kung Fu Hustle", 2004, "功夫 · 周星驰"),
    ("中国", "In the Mood for Love", 2000, "花样年华 · 王家卫"),
    ("中国", "2046", 2004, "2046 · 王家卫"),
    ("中国", "Eat Drink Man Woman", 1994, "饮食男女 · 李安"),
    ("中国", "Yi Yi", 2000, "一一 · 杨德昌"),
    ("中国", "Last Emperor", 1987, "末代皇帝 · 贝托鲁奇（奥斯卡最佳影片）"),
    ("日本", "Seven Samurai", 1954, "七武士 · 黑泽明"),
    ("日本", "Rashomon", 1950, "罗生门 · 黑泽明威尼斯金狮"),
    ("日本", "Tokyo Story", 1953, "东京物语 · 小津安二郎"),
    ("日本", "Spirited Away", 2001, "千与千寻 · 宫崎骏奥斯卡最佳动画"),
    ("日本", "My Neighbor Totoro", 1988, "龙猫 · 宫崎骏"),
    ("日本", "Princess Mononoke", 1997, "幽灵公主 · 宫崎骏"),
    ("日本", "Battle Royale", 2000, "大逃杀 · 深作欣二"),
    ("日本", "Godzilla", 1954, "哥斯拉 · 本多猪四郎"),
    ("日本", "Shall We Dance", 1996, "谈谈情跳跳舞 · 周防正行"),
    ("韩国", "Oldboy", 2003, "老男孩 · 朴赞郁戛纳评审团大奖"),
    ("韩国", "Memories of Murder", 2003, "杀人回忆 · 奉俊昊"),
    ("韩国", "Host, The", 2006, "汉江怪物 · 奉俊昊"),
    ("韩国", "My Sassy Girl", 2001, "我的野蛮女友 · 郭在容"),
    ("韩国", "Sympathy for Mr. Vengeance", 2002, "我要复仇 · 朴赞郁"),
    ("韩国", "Spring, Summer", 2003, "春夏秋冬又一春 · 金基德"),
    ("欧洲", "Poulain", 2001, "天使爱美丽 · 让-皮埃尔·热内（法国）"),
    ("欧洲", "Cinema Paradiso", 1988, "天堂电影院 · 托纳多雷（意大利）"),
    ("欧洲", "Life Is Beautiful", 1997, "美丽人生 · 罗伯托·贝尼尼（意大利）"),
    ("欧洲", "Bicycle Thief", 1948, "偷自行车的人 · 德西卡（意大利）"),
    ("欧洲", "Run Lola Run", 1998, "罗拉快跑 · 汤姆·提克威（德国）"),
    ("欧洲", "Lives of Others", 2006, "窃听风暴 · 冯·多纳斯马（德国）"),
    ("欧洲", "Good Bye Lenin", 2003, "再见列宁 · 沃尔夫冈·贝克（德国）"),
    ("欧洲", "400 Blows", 1959, "四百击 · 特吕弗（法国）"),
    ("欧洲", "Intouchables", 2011, "触不可及 · （法国）"),
    ("欧洲", "Hunt, The", 2012, "狩猎 · 温特伯格（丹麦）"),
    ("欧洲", "Let the Right One In", 2008, "生人勿进 · （瑞典）"),
    ("欧洲", "Girl with the Dragon Tattoo", 2009, "龙纹身的女孩 · （瑞典）"),
    ("欧洲", "Three Colors: Red", 1994, "蓝白红三部曲之红 · 基耶斯洛夫斯基"),
    ("欧洲", "Three Colors: Blue", 1993, "蓝白红三部曲之蓝 · 基耶斯洛夫斯基"),
    ("拉美", "City of God", 2002, "上帝之城 · 费尔南多·梅里尔斯（巴西）"),
    ("拉美", "Central Station", 1998, "中央车站 · （巴西）"),
    ("拉美", "Pan's Labyrinth", 2006, "潘神的迷宫 · 吉尔莫·德尔·托罗（墨西哥）"),
    ("拉美", "Amores Perros", 2000, "爱情是狗娘 · 伊纳里图（墨西哥）"),
    ("拉美", "Y Tu Mama Tambien", 2001, "你妈妈也一样 · 卡隆（墨西哥）"),
    ("世界其他", "Slumdog Millionaire", 2008, "贫民窟的百万富翁 · （印度）"),
    ("世界其他", "3 Idiots", 2009, "三傻大闹宝莱坞 · （印度）"),
    ("世界其他", "Lagaan", 2001, "印度往事 · （印度）"),
    ("世界其他", "Separation, A", 2011, "一次别离 · 法哈蒂（伊朗）"),
    ("世界其他", "District 9", 2009, "第九区 · （南非）"),
    ("世界其他", "Tsotsi", 2005, "黑帮暴徒 · （南非）"),
    ("世界其他", "Incendies", 2010, "焦土之城 · 维伦纽瓦（加拿大）"),
    ("世界其他", "Das Boot", 1981, "从海底出击 · （德国）"),
    ("世界其他", "Once", 2007, "曾经 · （爱尔兰）"),
]


def find_book(catalog: pd.DataFrame, key: str):
    """目录标题/主题模糊匹配（取首个命中）"""
    m = catalog[catalog["Title"].str.contains(key, case=False, na=False, regex=False)]
    if m.empty:
        m = catalog[catalog["Subjects"].str.contains(key, case=False, na=False, regex=False)]
    return m.iloc[0] if not m.empty else None


def find_movie(movies: pd.DataFrame, key: str, year: int):
    """严格年份匹配（防止错配翻拍版，如 Oldboy 2013 美版）；找不到返回 None。"""
    m = movies[movies["title"].str.contains(key, case=False, na=False, regex=False)]
    m = m[m["extra"].astype(str) == str(year)]
    if not m.empty:
        return m.iloc[0]
    return None


def main():
    catalog = pd.read_csv(CATALOG, low_memory=False)
    catalog = catalog[catalog["Type"] == "Text"]
    movies = pd.read_csv(MOVIES_META)

    rows, missed = [], []
    # ---- 图书（Gutenberg 公版）----
    for region, cat, key, note in BOOKS:
        hit = find_book(catalog, key)
        if hit is None:
            missed.append(f"books:{key}")
            continue
        rows.append(("books", region, str(hit["Title"])[:500],
                     str(hit["Authors"])[:250].replace("[", "").replace("]", ""),
                     cat, note, None,
                     f"https://www.gutenberg.org/ebooks/{hit['Text#']}"))
    # ---- 电影（MovieLens 目录内匹配）----
    for region, key, year, note in FILMS:
        hit = find_movie(movies, key, year)
        if hit is None:
            missed.append(f"movies:{key}")
            continue
        rows.append(("movies", region, str(hit["title"])[:500],
                     str(hit["subtitle"])[:250], str(hit["extra"])[:64],
                     note, int(hit["item_id"]), None))

    print(f">> 世界内容库：{len(rows)} 条（未匹配 {len(missed)}：{missed}）")
    df = pd.DataFrame(rows, columns=["domain", "region", "title", "subtitle",
                                     "extra", "note", "item_id", "source_url"])
    print(df.groupby(["domain", "region"]).size())

    conn = pymysql.connect(host="127.0.0.1", user="root", password="root",
                           database="recsys", charset="utf8mb4")
    with conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS world_content (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            domain VARCHAR(16) NOT NULL,
            region VARCHAR(16) NOT NULL,
            title VARCHAR(512),
            subtitle VARCHAR(256),
            extra VARCHAR(256),
            note VARCHAR(256),
            item_id BIGINT NULL,
            source_url VARCHAR(512),
            INDEX idx_dr (domain, region)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        cur.execute("TRUNCATE TABLE world_content")
        cur.executemany(
            "INSERT INTO world_content (domain, region, title, subtitle, extra, note, item_id, source_url) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", rows)
    conn.commit()
    conn.close()
    print(">> 已写入 MySQL world_content 表")


if __name__ == "__main__":
    main()
