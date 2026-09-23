# 三域算法效果对比实验报告（K=10）

- 正反馈阈值：rating_norm >= 0.7（三域统一；对应图书评分>=8/10、电影>=4.0/5、课程>=3.8/5）
- 协同过滤近邻数 KNN = 20；每域抽样评估用户数 <= 1000
- 数据：Book-Crossing（图书，真实）/ MovieLens ml-latest-small（电影，真实）/ Udemy 目录（课程，真实物品+模拟评分）

## 一、各域算法对比

### books
| 算法 | Precision@K | Recall@K | HitRate@K | NDCG@K | Coverage |
|---|---|---|---|---|---|
| UserCF | 0.0202 | 0.0768 | 0.1530 | 0.0622 | 0.3763 |
| ItemCF | 0.0168 | 0.0633 | 0.1240 | 0.0505 | 0.3609 |
| ContentBased | 0.0216 | 0.0949 | 0.1760 | 0.0629 | 0.3926 |
| MostPopular | 0.0051 | 0.0204 | 0.0490 | 0.0125 | 0.0019 |

**books 域最优（NDCG@10）：ContentBased**

### movies
| 算法 | Precision@K | Recall@K | HitRate@K | NDCG@K | Coverage |
|---|---|---|---|---|---|
| UserCF | 0.2030 | 0.1996 | 0.7211 | 0.2778 | 0.0860 |
| ItemCF | 0.1738 | 0.1750 | 0.6931 | 0.2370 | 0.1521 |
| ContentBased | 0.0322 | 0.0404 | 0.2706 | 0.0416 | 0.2701 |
| MostPopular | 0.1200 | 0.1066 | 0.5380 | 0.1641 | 0.0156 |

**movies 域最优（NDCG@10）：UserCF**

### courses
| 算法 | Precision@K | Recall@K | HitRate@K | NDCG@K | Coverage |
|---|---|---|---|---|---|
| UserCF | 0.0648 | 0.1460 | 0.4790 | 0.1318 | 0.2458 |
| ItemCF | 0.0774 | 0.1746 | 0.5520 | 0.1592 | 0.0789 |
| ContentBased | 0.0065 | 0.0150 | 0.0630 | 0.0095 | 0.1483 |
| MostPopular | 0.0357 | 0.0803 | 0.3090 | 0.0632 | 0.0077 |

**courses 域最优（NDCG@10）：ItemCF**

## 二、跨域模拟实验（books → movies）

| 实验 | Precision@K | Recall@K | HitRate@K | NDCG@K |
|---|---|---|---|---|
| CrossDomain-Sim | 0.0066 | 0.0072 | 0.0594 | 0.0086 |
| CrossDomain-Random | 0.0040 | 0.0030 | 0.0363 | 0.0048 |
| ContentBased(单域参照) | 0.0322 | 0.0404 | 0.2706 | 0.0416 |

实验设计：三域数据集用户互不重叠，无法获得真实跨域用户测试集。本实验将电影测试用户与统一 TF-IDF 空间中画像最相似的图书用户配对（相似配对），嫁接其全部图书行为构造统一画像后推荐电影，并与随机配对（负对照）、单域内容推荐（参照）比较。

**解读**：若 CrossDomain-Sim 显著优于 CrossDomain-Random 并接近单域 ContentBased，说明统一标签空间中的跨域兴趣迁移携带真实偏好信号；线上注册用户在三个模块的真实行为（跨域画像）是本机制的实际应用场景。

## 三、跨域词表重叠度（统一空间可行性）

- books∩courses：共有词 645 个，Jaccard = 0.0296
- books∩movies：共有词 1162 个，Jaccard = 0.0543
- courses∩movies：共有词 151 个，Jaccard = 0.0314

三域共有高频词（按全局 IDF 升序，跨域信号最强的词）：
`action`, `book`, `musical`, `company`, `animation`, `love`, `life`, `del`, `new`, `star`, `world`, `time`, `play`, `white`, `black`, `true`, `easy`, `master`, `day`, `circle`, `professional`, `big`, `ii`, `great`
