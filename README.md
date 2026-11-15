# Cohabit · 校园舍友匹配

Cohabit 帮同学院同学在组寝前把作息、整洁、社交边界等讲清楚，通过画像匹配 + 双向确认找到合拍的室友，而不是随机分配。

## 技术栈

- 前端：Vue 3 + Vite 7 + TypeScript + Pinia + Vue Router + Tailwind CSS 4 + ECharts
- 后端：Django 5.2 + DRF + SimpleJWT + PostgreSQL 16 + Django Admin（Jazzmin）
- 交付：**本地优先**；功能完善后再上云（Nginx + Gunicorn + HTTPS）

## 目录约定

```text
cohabit/
├── README.md                 # 本文件
├── docs/                     # 开发手册、02/03、开发日记、后续 API/ER
└── 0.cohabit/                # 网站工程根；业务代码只写这里
    ├── backend/              # Django 工程
    └── frontend/             # Vue 3 SPA
```

> `docs/` 只放须知与契约，不写网站代码；网站代码、依赖、构建产物全部在 `0.cohabit/` 内。

## 文档入口

- **[开发手册 v2（单一事实来源）](<docs/开发手册(v2).md>)** ← 先读这份
- [组寝状态机（02）](<docs/02-组寝状态机.md>) ｜ [数据字典与问卷（03）](<docs/03-数据字典与问卷.md>)（已批准，2026-11-15）
- [开发日记](<docs/开发日记.md>)（每日任务与完成情况）
- 下一步产出：API 契约/OpenAPI、ER v2（路线图见手册 §15.2）
- 历史文档（v1，仅作参考，冲突时以 v2 为准）：
  - [Cohabit 开发手册（v1）.md](<Cohabit开发手册（v1）.md>)
  - [数据模型（Django）.md](<数据模型（Django）.md>)
  - [视觉设计规范（Hinge NFAQ 风格）.md](<视觉设计规范（Hinge NFAQ 风格）.md>)
  - [er-diagram.png](er-diagram.png) ｜ [runtime-architecture.png](runtime-architecture.png)

## 当前阶段

**网站脚手架与环境验证（2026-11-15）**：`0.cohabit/` 下已搭好 Django 5 + DRF 与 Vue 3 + Vite 的前后端骨架、路由、设计 token 和页面框架；后端依赖已装、`manage.py check` 通过，前端依赖已装、`npm run build` 通过，PostgreSQL 16.16 已在本机 5433 初始化。尚未写业务模型与真实接口；首次 migrate 被自定义 `accounts.User` 拦住，不能先用默认 `auth.User` 建表。

> 开发手册、状态机 02、数据字典/问卷 03 已获用户批准（按文档执行）。网站代码只写 `0.cohabit/`，`docs/` 只放契约与记录。

## 本地启动（依赖已装，2026-11-15 验证）

### 后端（Django 8000）

```powershell
cd D:\cohabit\0.cohabit\backend
# Python 3.12.15 的 .venv 与 requirements/dev.txt 已安装；重建时再执行：
# uv venv --python 3.12 .venv
# uv pip install -r requirements\dev.txt
# 本地 .env 已创建（被 .gitignore 忽略）；首次部署/新机器从 .env.example 复制。
# 首次 migrate 前，P1 必须先按 docs/03 落地自定义 User（accounts.User）；
# 脚手架阶段不要执行 migrate/seed_demo，否则会先用默认 auth.User 建表。
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver 8000
```

- PostgreSQL 16.16 便携版在 `D:\tools\pgsql16`，数据目录 `D:\cohabit\0.cohabit\.pgdata`，端口 `5433`，连接串见 `backend/.env` 的 `DATABASE_URL`；启动：`D:\tools\pgsql16\bin\pg_ctl.exe -D D:\cohabit\0.cohabit\.pgdata -o "-p 5433" start`。
- 已创建并验证角色 `cohabit`、数据库 `cohabit_dev`；`manage.py shell` 实测 Django 可连接 `127.0.0.1:5433/cohabit_dev`。
- 健康检查：`GET http://127.0.0.1:8000/api/health/`；
- API 文档：`/api/docs/`，schema：`/api/schema/`。

### 前端（Vite 5173）

```powershell
cd D:\cohabit\0.cohabit\frontend
# node_modules 已安装；重装时执行 npm install
copy .env.example .env.local
npm run dev
# 生产构建已验证：npm run build
```

- 开发时通过 Vite proxy 转发 `/api`、`/admin`、`/static`、`/media` 到 `http://127.0.0.1:8000`，不引入 CORS；
- 未启动后端时，可在 `.env.local` 设 `VITE_ALLOW_PREVIEW=true`，登录页进入前端预览模式（仅查看页面框架）。

## 当前门槛与下一步

- **首次 migrate 门槛**：后端当前仍用 Django 默认 `User`，`AUTH_USER_MODEL` 未设置。P1 必须按 `docs/03-数据字典与问卷.md` 落地自定义 `accounts.User` 后，才能执行 `migrate`/`seed_demo`；脚手架阶段禁止先用默认 `auth.User` 建表。
- 环境已验证：后端 `manage.py check` 0 问题；前端 `npm run build` 成功；PostgreSQL 16.16 角色/数据库可连接。网络代理已恢复，依赖安装不再阻塞。
- 下一步（按手册 §15.2）：P1 自定义 User + 首次迁移 → 04 API/OpenAPI、ER v2；团队计划与 D1 开工获批前不写业务模型。
