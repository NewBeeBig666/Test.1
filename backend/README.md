# recsys-backend — SpringBoot 业务后端

个性化图书推荐系统的业务层：图书管理、用户行为采集、推荐结果缓存与代理。

## 架构

```
浏览器(8080静态页) ──> SpringBoot(8080) ──> FastAPI算法服务(8001)
                          │   │
                     MySQL   Redis
                  (图书/行为) (推荐缓存)
```

- `POST /api/event`：行为落库 MySQL `behavior_event` 表 + 转发算法服务 + 淘汰该用户 Redis 推荐缓存
- `GET /api/rec/recommend`：查 Redis（key=`rec:{algo}:{userId}:{n}`，TTL 30分钟）→ 未命中调算法服务
- Redis 不可用时自动降级为本地内存缓存（60秒后自动重试 Redis）

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/rec/recommend?userId=114&algo=ItemCF&n=10` | 推荐（fromCache 字段标识缓存命中） |
| GET | `/api/rec/profile?userId=114` | 用户画像（兴趣标签+属性标签） |
| GET | `/api/rec/metrics` | 离线算法对比指标 |
| GET | `/api/rec/algorithms` | 算法列表 |
| GET | `/api/books?q=&page=&size=` | 图书检索（MySQL） |
| POST | `/api/event` | 行为采集 `{userId,itemId,eventType,rating?}` |
| GET | `/api/event/user/{userId}` | 行为历史 |

## 构建与运行

```bash
# 1) MySQL：建库并导入图书（root密码按实际修改）
mysql -uroot -proot -e "CREATE DATABASE IF NOT EXISTS recsys CHARACTER SET utf8mb4"
cd ../recommender && python import_to_mysql.py --processed_dir ./data/processed_real

# 2) 构建（首次会下载依赖）
mvn -DskipTests package

# 3) 运行（先启动算法服务和Redis，见项目根 start_all.bat）
java -jar target/recsys-backend-1.0.0.jar
```

前端页面：启动后访问 http://127.0.0.1:8080 （静态资源在 `src/main/resources/static/`）。

配置见 `application.yml`（数据源、Redis、算法服务地址、缓存TTL均可调）。
