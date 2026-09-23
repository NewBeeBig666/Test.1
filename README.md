<div align="center">

# 智荐 RecOS · 个性化推荐系统

**基于推荐算法的图书 / 课程 / 电影跨域个性化推荐平台**

![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.2.5-6DB33F?style=flat-square&logo=springboot&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688?style=flat-square&logo=fastapi&logoColor=white)
![Vue 3](https://img.shields.io/badge/Vue%203-4DB33D?style=flat-square&logo=vuedotjs&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-5.7-4479A1?style=flat-square&logo=mysql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7.x-DC382D?style=flat-square&logo=redis&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

</div>

---

## 📖 项目简介

**智荐 RecOS** 是一个面向图书、课程、电影三个内容领域的个性化推荐系统，采用「前端 + 业务后端 + 算法服务」三方分离的微服务架构。系统基于用户行为（浏览、点击、评分、收藏）构建**跨域统一兴趣画像**，融合多类推荐算法，为每位用户提供千人千面的个性化内容推荐，并内置完整的推荐算法对比实验环境。

- 🌍 **多区域内容库**：覆盖中国 / 日本 / 韩国 / 欧洲 / 拉美等区域精选内容，全量内容标注区域标签并支持中文主语言 + 原语言双语展示
- 🎯 **跨域推荐**：通过统一 TF-IDF 标签空间桥接三域，实现「在电影领域的兴趣也能推荐相关图书」的跨域联动
- 🧪 **算法实验室**：内置 5 种推荐算法（UserCF / ItemCF / ContentBased / CrossDomain / MostPopular），支持在线对比实验指标

## ✨ 功能特性

| 模块 | 特性 |
|---|---|
| 🏠 个性化首页 | 三域全球精选与个性化推荐交错混排，区域筛选，地区展示比例均衡 |
| 📚 三个内容栏目 | 图书 / 课程 / 电影各 18 项 3×6 网格浏览、关键词与类目筛选、区域精选 |
| 🎬 内容详情 | 右侧抽屉详情（封面 / 简介 / 主演 / 外链），推荐指数 1-10 分制全量覆盖 |
| 🌐 外部跳转 | /away 过渡页国内站点优先（豆瓣 / 微信读书 / B站 / MOOC 等），4 秒倒计时自主选择 |
| 📊 用户画像 | 跨域兴趣标签云、各域行为统计与画像可视化 |
| 🧪 算法实验室 | 5 算法对比实验（Precision@K / Recall@K 等），参数可调，图表化结果 |
| 🎨 界面视觉 | 苹果官网风格 UI，三域专属渐变配色，全响应式（375px → 1440px+） |
| 🛡️ 版权合规 | 外链统一过渡页安全跳转；区域内容均为公版 / 授权数据源 |

## 🛠 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 · Vite · Element Plus · Vue Router · Pinia |
| 业务后端 | Spring Boot 3.2.5 · Spring Data JPA · Redis · JWT |
| 算法服务 | FastAPI · scikit-learn · pandas · TF-IDF / 协同过滤 |
| 数据存储 | MySQL 5.7（业务数据）· Redis（会话 / 缓存） |
| 数据集 | BookCrossing · MovieLens · Udemy（真实课程目录）· Project Gutenberg · IMDb |

## 🚀 安装步骤

### 环境要求

| 依赖 | 版本要求 |
|---|---|
| JDK | 21+ |
| Python | 3.11 / 3.12 |
| Node.js | 18+（建议 20+） |
| MySQL | 5.7+ |
| Redis | 6.x+ |

### 1. 克隆仓库

```bash
git clone https://github.com/NewBeeBig666/Test.1.git
cd Test.1
```

### 2. 初始化数据（算法服务）

```bash
cd recommender
pip install -r requirements.txt

# 数据预处理与导入（依据实际数据文件路径）
python preprocess.py --domain books
python preprocess.py --domain movies
python preprocess_global.py
python import_to_mysql.py --all
```

### 3. 启动算法服务（端口 8001）

```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8001
```

### 4. 配置并启动业务后端（端口 8080）

```bash
cd backend
# 修改 application.yml 中 MySQL / Redis 连接信息
mvn spring-boot:run
```

### 5. 构建并启动前端

```bash
cd frontend
npm install
npm run build        # 产物输出至 backend/src/main/resources/static（随后端一起发布）
```

## 💡 使用方法

1. 访问 `http://localhost:8080` 打开系统，**无需注册即可作为游客浏览**（免认证直达）；
2. 在**首行区域筛选**中切换「全部地区 / 中国 / 日本 / 韩国 / 欧洲 …」查看全球内容；
3. 进入 **图书 / 课程 / 电影** 栏目：18 项网格浏览、顶部关键词搜索、类目筛选；
4. 点击任意作品卡片 → 右侧弹出**详情抽屉**（封面 / 双语标题 / 简介 / 推荐指数 / 外链按钮）；
5. 点击**评分 / 收藏**，行为即时进入推荐模型（自动重训），影响三域个性化结果；
6. 通过右上角「**更多**」进入 **画像**（跨域兴趣画像）与 **实验室**（算法对比实验）；
7. 点击抽屉内「豆瓣 / 微信读书 / MOOC」等外链 → 进入 `/away` 过渡页，**国内站点优先**，4 秒倒计时后默认打开；海外原站保留为可选。

## 📁 项目结构

```
├── frontend/                 # Vue 3 前端（构建产物随后端发布）
│   └── src/
│       ├── views/            # 页面（首页 / 三栏目 / 画像 / 实验室 / 过渡页）
│       ├── components/       # 卡片 / 详情抽屉 / 导航等组件
│       └── stores/           # Pinia 状态（用户会话等）
├── backend/                  # Spring Boot 业务后端（8080）
│   ├── src/main/java/...     # controller / service / entity / repo
│   └── src/main/resources/   # 配置、前端静态资源、中文译名词典
└── recommender/              # FastAPI 算法服务（8001）
    ├── api.py                # 推荐 / 跨域 / 富化 接口
    ├── algorithms.py         # 5 种推荐算法实现
    ├── preprocess*.py        # 数据预处理流水线
    └── data/                 # 处理后数据集、封面资源
```

## 🤝 贡献指南

欢迎任何形式的贡献（Bug 修复、新算法、内容扩充、文档改进）！

1. **Fork** 本仓库并创建特性分支：
   ```bash
   git checkout -b feat/your-feature
   ```
2. **提交** 符合规范的改动（遵循 Conventional Commits）：
   ```bash
   git commit -m "feat: add xxx algorithm"
   ```
3. **推送** 分支并发起 Pull Request：
   ```bash
   git push origin feat/your-feature
   ```
4. 请在 PR 描述中说明改动动机、验证方式与影响范围；代码需通过既有构建与测试。

> 💡 开发约定：前后端接口字段使用下划线风格（`item_id`）；中文面部注释与文档；新增数据源需在 `dataset_channels.py` 注册并说明牌照。

## 📄 许可证

本项目基于 **MIT License** 开源。

```
MIT License

Copyright (c) 2026 NewBeeBig666

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
...（详见 LICENSE 文件）
```

## 👤 作者

- **GitHub**：[NewBeeBig666](https://github.com/NewBeeBig666)
- **邮箱**：[3430244613@qq.com](mailto:3430244613@qq.com)

---

<p align="center">Made with ❤️ by NewBeeBig666</p>