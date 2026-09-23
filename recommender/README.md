# 推荐算法服务（Python 端，三域：图书/课程/电影）

基于三域公开数据集的个性化推荐算法服务，供 SpringBoot 后端调用：

| 域 | 数据集 | 性质 |
|---|---|---|
| 图书 | Book-Crossing（天池镜像 `tianchi.aliyun.com/dataset/31828`） | 真实评分 |
| 电影 | MovieLens ml-latest-small（`grouplens.org/datasets/movielens/`） | 真实评分 |
| 课程 | Udemy Courses（Kaggle；仓库已含 `data/udemy_courses.csv`） | 真实课程目录 + 文档化模拟评分 |

算法：UserCF / ItemCF / ContentBased / **CrossDomain（跨域推荐，统一 TF-IDF 标签空间）** / MostPopular。

## 运行流程

```bash
pip install -r requirements.txt

# 1) 数据预处理（统一格式：5-core 清洗、评分归一化、TF-IDF、8:2 划分）
py -3 preprocess.py --data_dir ./data/raw_real --out_dir ./data/processed_real   # 图书
py -3 preprocess_domain.py --domain movies                                      # 电影
py -3 preprocess_domain.py --domain courses --seed 42                          # 课程
py -3 preprocess_global.py        # 跨域统一 TF-IDF 空间（论文亮点）
py -3 import_to_mysql.py --all     # 三张物品表导入 MySQL

# 2) 三域评估 + 跨域模拟实验（产出 reports_all/）
py -3 evaluate_all.py --k 10 --sample 1000

# 3) 启动在线推理服务（默认 8001 端口）
py -3 -m uvicorn api:app --host 0.0.0.0 --port 8001
```

| 文件 | 说明 |
|---|---|
| `preprocess.py` | 图书域：清洗、低频过滤、归一化、TF-IDF、画像、8:2 分层划分（含封面 URL） |
| `preprocess_domain.py` | 电影（MovieLens 真实）/ 课程（Udemy 真实目录 + 模拟评分） |
| `preprocess_global.py` | 三域统一 TF-IDF 空间（global_id 偏移防冲突） |
| `algorithms.py` | 五算法统一接口：`fit()` / `recommend(user_id, n)`；CrossDomain 为跨域接口 |
| `evaluate.py` | 单域评估（Precision/Recall/HitRate/NDCG/Coverage） |
| `evaluate_all.py` | 三域 × 4 算法评估 + 跨域模拟实验 + 词表重叠度分析 |
| `api.py` | FastAPI 三域服务：推荐、画像（含跨域）、行为采集、模型热更新 |
| `import_to_mysql.py` | book / course / movie 三表导入 |

## HTTP 接口（domain ∈ books|courses|movies）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 存活检查（含三域训练时间） |
| GET | `/api/algorithms` | 算法列表（含 CrossDomain） |
| GET | `/api/recommend?user_id=114&domain=books&algo=ItemCF&n=10` | 域内推荐；algo=CrossDomain 为跨域推荐 |
| GET | `/api/user/{id}/profile?domain=books` | 单域画像（TF-IDF 兴趣标签 + 属性标签） |
| GET | `/api/user/{id}/profile/global` | **跨域统一画像**（统一词表标签 + 三域分域明细） |
| POST | `/api/events` | 行为采集（body 含 domain；rating 事件用真实评分归一化） |
| POST | `/api/reload` | 合并行为日志并重训三域模型（SpringBoot 在评分后异步调用） |

响应结构：

```json
{
  "user_id": 114, "domain": "books", "algo": "ItemCF", "cold_start": false, "latency_ms": 0.5,
  "items": [
    {"item_id": 6029, "title": "Under the Beetle's Cellar", "subtitle": "Mary Willis Walker",
     "extra": "Bantam Books", "score": 0.5854, "image_url": "http://images.amazon.com/..."}
  ]
}
```

## 设计要点

- **用户 ID 解析（每域独立）**：数据集原始 User-ID（体验用户）→ `online_user_map.csv`（线上注册用户，ID ≥ 1e9）→ 冷启动回退 MostPopular。跨次 reload 映射稳定。
- **统一 TF-IDF 空间**：三域物品文本共享一份词表（14940 物品 × 17315 词），是 CrossDomain 跨域推荐的基石；词表重叠度见 `reports_all/report.md` 第三节。
- **相似度计算**：scikit-learn `NearestNeighbors(cosine)` 只保留 Top-K 近邻（KNN 图），避免万级物品稠密相似度矩阵爆内存。
- **评估口径**：rating_norm ≥ 0.7 统一正反馈阈值（图书 ≥8/10、电影 ≥4.0/5、课程 ≥3.8/5），三域可比。
- **线上增量**：行为日志加权伪评分合并进训练数据（rating 用真实值），评分事件触发 SpringBoot 异步调用 `/api/reload`（秒级重训）。
