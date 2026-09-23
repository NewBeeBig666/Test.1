# -*- coding: utf-8 -*-
"""
将三个域的预处理产物 items_meta.csv 导入 MySQL（供 SpringBoot 业务端查询）。

表结构与 JPA 实体（backend com.recsys.entity.Book/Course/Movie）保持一致：
    book   (item_id, isbn, title, author, publisher, image_url)
    course (item_id, title, level, category, platform, price, subscribers)
    movie  (item_id, title, genres, year)

用法：
    pip install pymysql
    python import_to_mysql.py --domain books|courses|movies
    python import_to_mysql.py --all
"""
import argparse
import os

import pandas as pd
import pymysql

CREATE_TABLES = {
    "books": """
        CREATE TABLE IF NOT EXISTS book (
            item_id   BIGINT NOT NULL PRIMARY KEY,
            isbn      VARCHAR(32)  DEFAULT NULL,
            title     VARCHAR(512) DEFAULT NULL,
            author    VARCHAR(256) DEFAULT NULL,
            publisher VARCHAR(256) DEFAULT NULL,
            image_url VARCHAR(512) DEFAULT NULL,
            rec_score DECIMAL(2,1) DEFAULT NULL,
            INDEX idx_title (title(64))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    "courses": """
        CREATE TABLE IF NOT EXISTS course (
            item_id     BIGINT NOT NULL PRIMARY KEY,
            title       VARCHAR(512) DEFAULT NULL,
            level       VARCHAR(64)  DEFAULT NULL,
            category    VARCHAR(64)  DEFAULT NULL,
            platform    VARCHAR(64)  DEFAULT NULL,
            price       DOUBLE        DEFAULT NULL,
            subscribers BIGINT        DEFAULT NULL,
            source_url  VARCHAR(512) DEFAULT NULL,
            poster_url  VARCHAR(512) DEFAULT NULL,
            rec_score   DECIMAL(2,1) DEFAULT NULL,
            INDEX idx_title (title(64))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    "movies": """
        CREATE TABLE IF NOT EXISTS movie (
            item_id    BIGINT NOT NULL PRIMARY KEY,
            title      VARCHAR(512) DEFAULT NULL,
            genres     VARCHAR(256) DEFAULT NULL,
            year       VARCHAR(8)   DEFAULT NULL,
            poster_url VARCHAR(512) DEFAULT NULL,
            rec_score  DECIMAL(2,1) DEFAULT NULL,
            INDEX idx_title (title(64))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
}

# items_meta 统一列 -> 表列 的映射与行构造
IMPORTERS = {
    "books": {
        "table": "book",
        "sql": "REPLACE INTO book (item_id, isbn, title, author, publisher, image_url, rec_score) "
               "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        "row": lambda r: (int(r[0]), (str(r[1]) or "")[:32] or None,
                          (str(r[2]) or "")[:500] or None, (str(r[3]) or "")[:250] or None,
                          (str(r[4]) or "")[:250] or None, (str(r[5]) or "")[:500] or None,
                          float(r[6]) if str(r[6]) not in ("", "nan") else None),
        "cols": ["item_id", "ISBN", "Book-Title", "Book-Author", "Publisher", "image_url",
                 "rec_score"],
    },
    "courses": {
        "table": "course",
        "sql": "REPLACE INTO course (item_id, title, level, category, platform, price, subscribers, source_url, poster_url, rec_score) "
               "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        "row": lambda r: (int(r[0]), (str(r[1]) or "")[:500] or None,
                          (str(r[2]) or "")[:64] or None, (str(r[3]) or "")[:64] or None,
                          (str(r[4]) or "")[:64] or None,
                          float(r[5]) if pd.notna(r[5]) else None,
                          int(r[6]) if pd.notna(r[6]) else None,
                          (str(r[7]) or "")[:500] or None,
                          f"/covers/courses/{int(r[0])}.png",
                          float(r[8]) if len(r) > 8 and str(r[8]) not in ("", "nan") else None),
        "cols": ["item_id", "title", "subtitle", "extra", "platform", "price",
                 "num_subscribers", "source_url", "rec_score"],
    },
    "movies": {
        "table": "movie",
        "sql": "REPLACE INTO movie (item_id, title, genres, year, poster_url, rec_score) VALUES (%s, %s, %s, %s, %s, %s)",
        "row": lambda r: (int(r[0]), (str(r[1]) or "")[:500] or None,
                          (str(r[2]) or "")[:250] or None, (str(r[3]) or "")[:8] or None,
                          (str(r[4]) or "")[:500] or None if str(r[4]) != "nan" else None,
                          float(r[5]) if len(r) > 5 and str(r[5]) not in ("", "nan") else None),
        "cols": ["item_id", "title", "subtitle", "extra", "poster_url", "rec_score"],
    },
}

PROCESSED_DIRS = {
    "books": "./data/processed_real",
    "courses": "./data/processed_courses",
    "movies": "./data/processed_movies",
}


def import_domain(domain: str, conn):
    cfg = IMPORTERS[domain]
    path = os.path.join(PROCESSED_DIRS[domain], "items_meta.csv")
    df = pd.read_csv(path)
    for col in cfg["cols"]:  # 增量列（如 poster_url 尚未预取时）容错为空
        if col not in df.columns:
            df[col] = ""
    df = df[cfg["cols"]].fillna("")
    rows = [cfg["row"](r) for r in df.itertuples(index=False, name=None)]
    with conn.cursor() as cur:
        # 表结构随 items_meta 演进（如新增 image_url），DROP+CREATE 保证一致
        cur.execute(f"DROP TABLE IF EXISTS {cfg['table']}")
        cur.execute(CREATE_TABLES[domain])
        cur.executemany(cfg["sql"], rows)
    conn.commit()
    print(f">> [{domain}] 已导入 {len(rows)} 条到 {cfg['table']} 表")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["books", "courses", "movies"])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=3306)
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="root")
    ap.add_argument("--database", default="recsys")
    args = ap.parse_args()

    domains = list(PROCESSED_DIRS) if args.all else [args.domain]
    conn = pymysql.connect(host=args.host, port=args.port, user=args.user,
                           password=args.password, database=args.database,
                           charset="utf8mb4", local_infile=False)
    try:
        for domain in domains:
            import_domain(domain, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
