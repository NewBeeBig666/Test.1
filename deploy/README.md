# 智荐 RecOS · 云服务器一键部署手册

> 目标：让任意浏览器访问 `http://<服务器公网IP>` 直接开启系统，而非查看仓库。
> 适用：阿里云 / 腾讯云 / 华为云 等**轻量应用服务器**，系统镜像 **Ubuntu 24.04**。
> 部署后架构：Nginx(80) → SpringBoot(8080，托管前端) ⇄ FastAPI 算法(8001) + MySQL(3306) + Redis(6379)

---

## 一、选购建议（可以购买）

| 项 | 建议 |
|---|---|
| 实例 | 轻量应用服务器，**2 核 4G**（最低 2 核 2G 可跑） |
| 镜像 | **Ubuntu 24.04 LTS**（自带 JDK21 源，脚本依赖它） |
| 地域 | 离您/答辩老师近的地域（如广州、成都、上海），延迟低 |
| 带宽 | 3~5 Mbps 起，上传数据时快些 |
| 计费 | 学生优惠 / 新用户优惠 通常几十元/年；临时用可按量 |
| 安全组 | ALWAYS 开放端口：**80**（网页）、3306 可不开外网（同机内网访问） |

> 公有云控制台默认放行 80；若自定义安全组，请额外确认 80 已放行。

## 二、服务器初始化

### 1. 登录服务器

```bash
ssh root@<服务器公网IP>
# 部分厂商默认用户是 ubuntu，用 ubuntu 登录后 sudo -i 切 root
```

### 2. 上传本项目代码与数据

在**本机**执行（路径按实际调整）：

```bash
# 代码（GitHub 仓库）
ssh root@IP "mkdir -p /opt/recsys"
ssh root@IP "git clone https://github.com/NewBeeBig666/Test.1.git /opt/recsys"   # 需先把本仓库 push 到 GitHub

# 数据（推荐算法服务必需：processed_* / covers / external / ml-latest-small）
scp -r recommender/data/processed_movies recommender/data/processed_courses \
        recommender/data/processed_real recommender/data/processed_global \
        recommender/data/external recommender/data/ml-latest-small \
        root@IP:/opt/recsys/recommender/data/
scp -r recommender/data/covers root@IP:/opt/recsys/recommender/data/

# 数据库导出（本机 MySQL57 导出，兼容服务器 MySQL8）
mysqldump -uroot -proot --databases recsys > recsys_dump.sql
scp recsys_dump.sql root@IP:/opt/recsys/
```

> 若代码尚未进仓库，也可整体 `scp -r` 上传：`scp -r backend frontend recommender deploy root@IP:/opt/recsys/`

### 3. 依次执行部署脚本（均需 root）

```bash
cd /opt/recsys/deploy
bash 01-init-env.sh           # 安装 JDK21/Node/MySQL/Redis/Nginx + Python 依赖
bash 02-build.sh              # 构建前端 + 后端 jar
bash 03-install-services.sh   # 注册并启动 算法服务(8001) + 后端(8080)
bash 04-import-mysql.sh       # 导入数据库
```

### 4. 验证

```bash
systemctl status recsys-algo recsys-backend   # 两个服务 active (running)
curl -s http://127.0.0.1:8001/docs -o /dev/null -w "%{http_code}\n"   # 200
```

浏览器打开 `http://<服务器公网IP>` —— 系统首页直接呈现 ✔

## 三、常用运维

| 操作 | 命令 |
|---|---|
| 查看后端日志 | `journalctl -u recsys-backend -f` |
| 查看算法日志 | `journalctl -u recsys-algo -f` |
| 重启服务 | `systemctl restart recsys-backend recsys-algo` |
| 停止服务 | `systemctl stop recsys-backend recsys-algo` |

## 四、常见问题

- **页面能开但登录/推荐报错**：多为算法服务未启动 → `systemctl status recsys-algo`，查看日志
- **封面上传漏了**：`/opt/recsys/recommender/data/covers` 缺失会导致图书/课程封面不显示，补传后无需重启（静态资源即时生效）
- **数据库导入报错**：确认本机导出时用了 `--databases recsys`；服务器 04 脚本幂等（重复执行安全）
- **域名**：如需绑定域名（如 `recsys.example.com`），在 DNS 解析后把 `nginx-recserver.conf` 中 server_name 改为域名并 `nginx -t && systemctl reload nginx`
- **HTTPS**：配置域名后可运行 `apt install certbot && certbot --nginx` 免费签发

## 五、安全提示

- 服务器防火墙默认已放行 80；**不建议**对外网开放 3306（同机应用内网访问即可）
- 上线后请修改 MySQL root 密码与 `application.yml` 中对应配置（同时改 `03` 脚本前不涉及）
- 定时备份：`mysqldump -uroot -p<密码> --databases recsys | gzip > backup_$(date +%F).sql.gz`