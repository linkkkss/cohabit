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
├── docs/                     # 开发手册、02/03/04、OpenAPI、ER、开发日记
└── 0.cohabit/                # 网站工程根；业务代码只写这里
    ├── backend/              # Django 工程
    └── frontend/             # Vue 3 SPA
```

> `docs/` 只放须知与契约，不写网站代码；网站代码、依赖、构建产物全部在 `0.cohabit/` 内。

## 文档入口

- **[开发手册 v2（单一事实来源）](<docs/开发手册(v2).md>)** ← 先读这份
- [组寝状态机（02）](<docs/02-组寝状态机.md>) ｜ [数据字典与问卷（03）](<docs/03-数据字典与问卷.md>)（已批准，2026-11-15）
- [API 契约（04）](<docs/04-API契约.md>) ｜ [OpenAPI 3.0.3](<docs/openapi.yaml>) ｜ [ER v2](<docs/ER-v2.md>)（已批准，2026-11-15）
- [开发日记](<docs/开发日记.md>)（每日任务与完成情况）
- 产品材料：[视觉与组件规范（05）](<docs/05-视觉与组件规范.md>) ｜ [验收清单（06）](<docs/06-验收清单.md>) ｜ [演示脚本（07）](<docs/07-演示脚本.md>) ｜ [seed 规格](<docs/seed-spec.md>)
- 当前进度：**基础层 + 画像/匹配已完成（2026-11-15）**；团队 `cohabit-m1` 的 t1–t11 全部完成（实际覆盖手册 M1–M3），后端 151 tests、前端 build 182 modules 通过；**M4 组寝闭环已完成并通过验收（2026-11-15）**（`cohabit-m4`：通知→寝室→连接→seed→前端→QA；后端全量 **544 passed**、前端 build **242 modules**；验收记录见 [06 验收清单](<docs/06-验收清单.md>) §14，结论“M4 通过，P0/P1=0”）；**M5 管理与打磨已完成并通过验收（2026-11-16）**（`cohabit-m5`：举报/拉黑、定时维护、Admin 导出/级联、账号注销/health/stats、设置/规则/隐私、移动端与空态；后端全量 **704 passed**、前端 build **266 modules**；验收记录见 [06 验收清单](<docs/06-验收清单.md>) §15，结论“M5 通过，P0/P1=0”）
- 历史文档（v1，仅作参考，冲突时以 v2 为准）：
  - [Cohabit 开发手册（v1）.md](<Cohabit开发手册（v1）.md>)
  - [数据模型（Django）.md](<数据模型（Django）.md>)
  - [视觉设计规范（Hinge NFAQ 风格）.md](<视觉设计规范（Hinge NFAQ 风格）.md>)
  - [hinge 参考截图](<hinge参考截图/>)（2026-11-15 补充）
  - [er-diagram.png](er-diagram.png) ｜ [runtime-architecture.png](runtime-architecture.png)

## 当前阶段

**M1 基础层已完成（2026-11-15）**：`0.cohabit/` 下 Django 5 + DRF 与 Vue 3 + Vite 骨架、依赖、`manage.py check`、`npm run build`、PostgreSQL 16.16 均已验证；04 API 契约、OpenAPI、ER v2 已获用户批准。M1 团队 `cohabit-m1` 完成 t1–t11：自定义 `accounts.User` 与首次迁移、认证 API、画像/匹配算法、领域模型、合并迁移、画像/匹配 API、前端认证外壳、问卷/画像/匹配页、视觉/验收/seed 材料、邀请码、`PUT /api/me`。后端全量 pytest **151 passed**，check/makemigrations --check/migrate/ruff 全绿；前端 build **182 modules**；浏览器走查 onboarding→match→profile 通过。验收记录见 [06 验收清单 §13](<docs/06-验收清单.md>)。

**M4 组寝闭环已完成并通过验收（2026-11-15）**：`cohabit-m4` 完成通知、寝室状态机/API、连接三入口与两步确认、seed/Admin、连接与寝室前端页面、匹配详情发起邀请、R-13 回寝拒绝与 confirm 响应快照修复。后端全量 pytest **544 passed**，check/makemigrations --check/ruff 全绿；前端 build **242 modules**；Q2 在隔离库 `cohabit_m4_qa` 完成 API 171 项、UI 22 项、FA-04 全链路 13 项，结论 **M4 通过（P0/P1=0）**，记录见 [06 验收清单 §14](<docs/06-验收清单.md>)。演示库已执行 `seed_demo --reset`（41 用户/6 寝/8 请求/79 通知）。

**M5 管理与打磨已完成并通过验收（2026-11-16）**：`cohabit-m5` 完成 t1–t10：举报/拉黑 API 与副作用、定时维护命令（归档/过期/提醒/清理/转让/`member_count` 修复）、Admin 筛选/动作/6+2 类 CSV 导出/强制解散/删除保护/联系方式审计、账号注销与禁用级联、`/api/health` DB 探测与 `/api/admin/stats`、设置/规则/隐私页、通知中心与安全入口、移动端/404/空态、S-06 学生端角色守卫、创建寝室 5 次/日限频。后端全量 pytest **704 passed**，check/makemigrations --check/ruff 全绿；前端 build **266 modules**（含 `vue-tsc`）；Q3 在隔离库 `cohabit_m5_qa` 完成 API **432/432**、UI 375/768/1280 走查（46 张截图、console 0 error），结论 **M5 通过（P0/P1=0）**，记录见 [06 验收清单 §15](<docs/06-验收清单.md>)；演示脚本已更新为 [07 M5 v3](<docs/07-演示脚本.md>)。已知 P2：WK-03 窗口关闭横幅留待 M6；P3：Admin 经 Vite 代理登录受 CSRF 限制，演示走直连 8000。

> 开发手册、02、03、04/OpenAPI/ER 均已获用户批准（按文档执行）。网站代码只写 `0.cohabit/`，`docs/` 只放契约与记录。

## 本地启动（依赖已装，2026-11-15 验证）

### 后端（Django 8000）

```powershell
cd D:\cohabit\0.cohabit\backend
# Python 3.12.15 的 .venv 与 requirements/dev.txt 已安装；重建时再执行：
# uv venv --python 3.12 .venv
# uv pip install -r requirements\dev.txt
# 本地 .env 已创建（被 .gitignore 忽略）；首次部署/新机器从 .env.example 复制。
# 首次 migrate 已由 accounts.User（t1）完成；重建数据库后直接 migrate，不要再先用默认 auth.User。
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

- **migrate 已解锁**：自定义 `accounts.User` 已由 t1 落地并执行首次迁移；重建数据库后可直接 `migrate`，不得回退到默认 `auth.User`。
- 环境已验证：后端 `manage.py check` 0 问题；前端 `npm run build` 成功；PostgreSQL 16.16 角色/数据库可连接。
- 下一步（按手册 §15.2）：M1、M4、M5 均已完成并通过验收（704 tests / build 266 modules / 06 §15）；用户手动提交 Git 后进入 **M6 本地冻结**（全链路演示脚本、种子数据、构建产物、缺陷清单；5 分钟演示一次过、`pytest`/`build` 全绿、文档同步）。
