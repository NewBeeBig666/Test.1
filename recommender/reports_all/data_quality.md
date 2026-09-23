# 数据质量监控报告

生成时间：2026-09-18 13:37:35（`py -3 dataset_channels.py --quality`）
渠道总数：23（已接入 3 / 已自动化 2 / 可直连 8 / 需申请 10）

## 主模型数据（active）

| 域 | 行数 | 用户数 | 物品数 | 评分均值 | 稀疏度 | 文件更新 |
|---|---|---|---|---|---|---|
| books | 115219 | 6851 | 9085 | 0.756 | 0.1851% | 2026-09-18 11:15 |
| movies | 90274 | 610 | 3650 | 0.675 | 4.0545% | 2026-09-17 11:54 |
| courses | 78685 | 2500 | 2205 | 0.749 | 1.4274% | 2026-09-18 11:13 |

## 外部渠道数据（external）

| 渠道 | 指标 |
|---|---|
| gutenberg | 元数据物品数=9447，文件更新=2026-09-18 13:06 |
| movietweetings | 评分行数=921398，用户数=71707，物品数=38013，评分均值=7.31，元数据物品数=38018，文件更新=2026-09-18 13:12 |

## 渠道注册表状态

| 渠道 | 域 | 状态 | 获取方式 |
|---|---|---|---|
| Book-Crossing | books | 已接入 | 阿里云天池镜像直下（BX-CSV-Dump.zip） |
| Goodreads 书评 | books | 需申请 | 官方 API 已于 2020 关闭；Kaggle 有 goodreads-reviews 等镜像（需账号） |
| Amazon Books 子集 | books | 可直连 | UCSD McAuley 主页直链（ratings/reviews *.json.gz） |
| Project Gutenberg 书目 | books | 已自动化 | 官方 CSV 直链（全量书目元数据，无个体评分） |
| MovieLens ml-latest-small | movies | 已接入 | GroupLens 直链（天池有镜像） |
| Netflix Prize 历史数据 | movies | 需申请 | 官方已下架；Kaggle 镜像（netflix-prize 需账号） |
| MovieTweetings | movies | 已自动化 | GitHub raw 直链（本网络经镜像下载）；约 92 万评分 / 7.2 万用户 / 3.8 万部 |
| TMDb Movies Dataset | movies | 可直连 | REST API v3，免费注册 API Key（无个体级评分，含 popularity/vote_average） |
| FilmTrust / Flixster / CiaoDVD | movies | 需申请 | librec.net 原分发页已停用（域名停靠）；需联系作者或 GuruRecommender 项目获取 |
| Udemy Courses Dataset | courses | 已接入 | Kaggle 公开数据集（仓库已含 data/udemy_courses.csv） |
| COCO 课程数据集 | courses | 需申请 | 需联系论文作者（研究用途授权） |
| Coursera / edX 公开教育数据 | courses | 可直连 | Kaggle 课程元数据集（需账号）；edX 有部分公开课程结构导出 |
| WikiQA 问答语料库 | courses | 可直连 | 微软直链下载 |
| IndustryCorpus 等行业语料 | courses | 需申请 | 注册申请制 |
| Kaggle Datasets | general | 可直连 | kaggle CLI + kaggle.json 凭证（账号设置页生成） |
| Hugging Face Datasets | general | 可直连 | datasets 库直连（国内可配 HF_ENDPOINT=https://hf-mirror.com） |
| 国家基础学科公共科学数据中心 | general | 需申请 | 注册申请制 |
| Amazon Product Data | general | 可直连 | UCSD 直链 *.json.gz（1996-2023 各年份子集） |
| Yelp Open Dataset | general | 需申请 | 同意使用协议后下载（需注册） |
| Last.fm / MSD / Spotify | general | 需申请 | 均需 API Key 或学术授权 |
| Yandex Yambda | general | 可直连 | HuggingFace 直下（2025 发布，约 4.79B 音乐交互事件） |
| Epinions / Ciao | general | 需申请 | 需联系作者获取 |
| Jester 笑话评分 | general | 需申请 | Berkeley 直链（本网络实测超时，需代理环境） |

## 自动化更新

- 手动：`py -3 dataset_channels.py --update`（全部 adapter 渠道）
- 一键脚本：`update_datasets.bat`（更新 + 质量报告）
- Windows 计划任务（每日 03:00）：
  `schtasks /Create /SC DAILY /TN RecSysDataUpdate /ST 03:00 /TR "E:\ZcodeSpace\New Demo\update_datasets.bat"`
