# Cohabit API 契约（v1）

> 状态：**已批准 / 冻结（2026-11-15；M1 按此实现）**
> 适用：Vue 3 SPA ↔ Django 5 + DRF；前端类型、service 层、OpenAPI、测试用例共用本契约。
> 权威顺序：`02-组寝状态机.md`（状态/并发/权限） > `03-数据字典与问卷.md`（字段/枚举/算法） > 本文（HTTP 面） > `开发手册(v2).md` §7（概览）。
> 与手册冲突时以本文 §11 的差异登记为准；未登记的冲突视为文档缺陷，先改文档再写代码。
> 配套文件：`docs/openapi.yaml`（机器可读契约）、`docs/ER-v2.md`（数据模型）。
> 实现澄清（2026-11-15，Lead 裁决，已记入 §12）：匹配目标画像 <100 用 `409 TARGET_PROFILE_INCOMPLETE`；跨院/跨性别/目标不存在统一 `404 PROFILE_NOT_FOUND`。不改已批准的主干契约。

## 0. 范围与非目标

**范围**

- 学生端全部 API：认证、我的资料/画像/联系方式、问卷配置、用户与匹配、寝室（广场/详情/成员/转让）、组寝请求、通知、举报/拉黑、健康检查。
- 管理端不提供学生 API；除 `GET /api/admin/stats` 外，管理动作走 Django Admin（Session + CSRF），不在本文展开。
- 请求/响应字段、状态前置条件、错误码、HTTP 状态、分页、限频、隐私边界。

**非目标**

- 邮件/短信真实发送（开发期验证码固定 `123456`，DEBUG 返回 `dev_code`）。
- 用户照片上传、富文本、聊天/IM；联系方式只在请求详情按状态解锁。
- 导出、统计报表、消息推送、WebSocket；通知走 20 秒轮询。
- 密码找回/邮箱变更；本期由 Admin 后台处理。
- URL 版本号；v1 冻结后 breaking change 走 `/api/v2`。

## 1. 通用约定

### 1.1 基址、内容类型、时间

| 项 | 约定 |
| --- | --- |
| Base URL | 开发 `http://localhost:8000/api`（Vite 代理 `/api`）；生产同域 `/api` |
| 内容类型 | 请求/响应 `application/json; charset=utf-8`；无文件上传 |
| 认证 | `Authorization: Bearer <access>`；access 仅存前端内存 |
| 刷新 | `POST /api/auth/refresh` 走 HttpOnly Cookie；不把 refresh 返回 body |
| 时间 | DB 存 UTC；API 输出 ISO 8601 UTC（`2026-11-15T08:00:00Z`）；前端本地化展示 |
| 日期 | 不带时区的日期不使用；所有业务时间点都是 datetime |
| 空值 | 可选字段缺省时省略；明确“无”用 `null` 的字段在 schema 标注 |
| 命名 | JSON 字段 `snake_case`；枚举值 `UPPER_SNAKE_CASE`；路径参数用 `:uid` / `:code` / `:id` |

### 1.2 认证与 Cookie

| 项 | 规则 |
| --- | --- |
| access | JWT，30 分钟；只存 Pinia 内存，不写 localStorage/sessionStorage |
| refresh | JWT，7 天；Cookie 名 `refresh`；`HttpOnly; Secure(生产); SameSite=Lax; Path=/api/auth/; Max-Age=604800` |
| 登录/注册 | 响应 body 返回 `access`；`Set-Cookie: refresh=...` |
| 刷新 | 浏览器自动带 Cookie；轮换 refresh（旧 token 入黑名单），返回新 `access` 并更新 Cookie |
| 注销 | 清 Cookie + refresh 黑名单 + 前端清内存/轮询；204 |
| 401 | 前端 Axios 单航班刷新：同一时刻只发一个 refresh，其余排队；成功后重放一次原请求；失败清内存并跳登录 |
| 启动 | 页面刷新先静默 refresh 恢复会话；失败再判未登录 |
| CSRF/来源 | refresh/logout 校验 `Origin`/`Referer` ∈ `ALLOWED_ORIGINS`；`SameSite=Lax`；Django Admin 继续 CSRF |
| CORS | 不启用；开发 Vite proxy `/api`、`/admin`、`/static` 到 8000；生产 Nginx 同域 |
| 地址 | 开发统一 `http://localhost:5173`，不要与 `127.0.0.1` 混用（Cookie 不共享） |

### 1.3 标识符

| 标识 | 形态 | 用途 |
| --- | --- | --- |
| `uid` | 10 位数字字符串，保留前导零（`0834215769`） | 用户对外标识、搜索、匹配、请求目标 |
| `code` | 9 位数字字符串（`482913756`） | 寝室对外编号、分享页、详情 |
| `id` | 内部自增整数 | 请求、转让、通知、举报；只在本人可见资源中使用 |
| `type` | `INVITE` / `APPLY` | 组寝请求类型 |
| `status` | 见 02/03 枚举 | 字符串枚举，不接受小写 |

规则：

- 对外分享/详情寝室用 `code`；房主管理动作（锁定/解散/转让/移除）用内部 `id`，前端先从 `GET /api/rooms/mine` 或详情取得。
- 用户标识统一 `uid`；不要用 email 作为对外标识。
- 非参与者访问请求统一 404 `CONNECTION_NOT_FOUND`，不暴露存在性。

### 1.4 分页、筛选、排序

列表统一：

```json
{
  "count": 42,
  "next": "http://localhost:8000/api/connections?page=2",
  "previous": null,
  "results": []
}
```

| 项 | 约定 |
| --- | --- |
| 分页参数 | `page`（从 1 开始）、`page_size`（默认 20，最大 50） |
| 响应 | `count/next/previous/results`；`next/previous` 可为绝对 URL |
| 排序 | 默认按业务定义（见各端点）；不接受任意字段排序，避免注入/索引问题 |
| 筛选 | 白名单 query 参数；未知参数忽略还是 400？**v1 忽略未知参数**，但前端只传文档内参数 |
| 空结果 | `count=0, results=[]`，不是 404 |

> 实现注意：`config/api.py` 的 `max_page_size` 必须是 **50**；当前脚手架已改为 50。

### 1.5 幂等、并发与重试

- 写动作重复提交：不重复扣减/写通知；返回 409（`DUPLICATE_REQUEST`、`ALREADY_CONFIRMED`、`INVALID_STATE` 等），前端刷新状态而不是当系统错误。
- 创建类唯一性由 DB 部分唯一索引兜底（见 03 §1.10）。
- 并发控制以 service 层 `select_for_update` 行锁为准；`ConnectionRequest.version` 只作审计/乐观锁辅助，不在 HTTP 暴露 `If-Match`。
- 客户端超时重试：对 `POST` 只在网络错误时重试一次；收到 409 表示第一次可能已成功，必须 GET 刷新。
- 服务端不保证“同一请求体得到同一响应”；以资源当前状态为准。

### 1.6 统一错误

```json
{
  "code": "ROOM_FULL",
  "message": "房间已满员",
  "detail": {"room_code": "482913756"}
}
```

- `code` 供前端分支；`message` 中文可直接展示；`detail` 为对象或 `null`。
- 字段校验错误：

```json
{
  "code": "VALIDATION_ERROR",
  "message": "请求参数不合法",
  "detail": {
    "fields": {"capacity_pref": ["只能是 2、4 或 6"]}
  }
}
```

- 不返回堆栈、SQL、内部路径；500 带 `request_id`（响应体或 `X-Request-ID`）。
- 错误响应不得包含联系方式、邮箱、真名、token；即使动作涉及这些表。
- HTTP 状态只表达类别，具体原因看 `code`；完整表见 §8。

### 1.7 隐私边界（硬规则）

1. 联系方式（QQ/微信/手机号）**只**在 `GET /api/connections/:id` 且当前用户是参与者、状态 ∈ `{CONTACT_SHARED, CONFIRMING, CONFIRMED}` 时返回；再过 `show_*` 开关。
2. 列表、通知、审计、日志、错误 `detail` 一律不出现 contact 值、邮箱、真名、token。
3. 公开寝室页只返回编号/标题/人数/容量/状态/学院/成员昵称/默认头像/标签；无画像明细、无联系方式。
4. 非同院/同性别/非参与者访问用户/寝室/请求 → 404 或 403（按 §8），不泄露存在性。
5. 举报只进 Admin 人工处理；不自动封禁、不通知被举报人。

### 1.8 时间窗

- 时间窗按学院配置；无记录 = 关闭。
- **只约束组寝写操作**：创建请求、accept、decline、cancel、confirm、锁定/解锁、退出/移除、解散、转让。
- 注册/登录、资料/问卷编辑、举报、拉黑、通知已读**不受**窗口影响。
- Admin 运维动作不受窗口限制，但必须审计。
- 关闭后写操作返回 `409 WINDOW_CLOSED`；读接口正常。

### 1.9 限频（落地值）

| 场景 | 限制 | 超限 |
| --- | --- | --- |
| 发起组寝请求 | 在途 ≤3；每 24h ≤10；被拒后对同一目标双向 24h 冷却 | 429 `RATE_LIMITED` / `COOLDOWN` |
| 登录 | 同邮箱 + IP 15 分钟 5 次失败 | 429 `RATE_LIMITED` |
| 发送验证码 | 同邮箱 60s 1 次、每日 10 次 | 429 `RATE_LIMITED` |
| 注册 | 同 IP 每小时 5 次 | 429 `RATE_LIMITED` |
| UID 搜索/画像查看 | 每用户每小时 60 次 | 429 `RATE_LIMITED` |
| 创建寝室 | 每用户每日 5 次（仅统计 confirm 建寝） | 429 `RATE_LIMITED` |
| 举报 | 每用户每日 10 次 | 429 `RATE_LIMITED` |
| 刷新 token | 每 refresh 每分钟 30 次 | 429 `THROTTLED` |

- 429 带 `Retry-After`（秒）；业务型限制提示具体原因，不泄露他人数据。
- 限频只在**创建请求**时检查；accept/decline/cancel/confirm 不限频。

## 2. 认证流程

```text
① POST /api/auth/send-code {email, purpose:"REGISTER"}
② POST /api/auth/register {...} → 201 {user, access} + Set-Cookie refresh
③ 后续请求 Authorization: Bearer access
④ access 过期 → 401 TOKEN_EXPIRED
   Axios 单航班 POST /api/auth/refresh（Cookie）→ {access} + 新 Cookie
   成功重放原请求；失败清内存 → 跳登录
⑤ POST /api/auth/logout → 204 + 清 Cookie + blacklist
```

- 开发期不真发邮件；`DEBUG=true` 时 `send-code` 响应带 `dev_code`（固定 `123456`）。
- 注册成功即登录，返回 access；`user` 为 `UserMe` 精简版（不含 contact）。
- 邮箱不区分大小写；存储前 `lower()`；重复注册 409 `EMAIL_TAKEN`。
- 邀请码：`INVITE_REQUIRED=true` 时必填；**未填 → 403 `INVITE_REQUIRED`**；提供但不存在/过期/停用/耗尽 → 统一 400 `INVITE_INVALID`（不区分原因，避免枚举）；开发环境默认 false。
- 登录失败统一 401 `INVALID_CREDENTIALS`，不区分邮箱不存在/密码错。
- 禁用用户登录 403 `ACCOUNT_DISABLED`；已有 access 的写操作也拒绝。

### 2.1 `POST /api/auth/send-code`

| 项 | 内容 |
| --- | --- |
| 认证 | 无 |
| 请求 | `{"email":"demo001@stu.edu.cn","purpose":"REGISTER"}`；purpose 枚举 `REGISTER`（v1 仅此用途） |
| 成功 | 生产：`204 No Content`；`DEBUG=true`：`200 {"dev_code":"123456"}`（仅调试便利，二选一，不并存） |
| 错误 | 400 `VALIDATION_ERROR`；429 `RATE_LIMITED` |
| 隐私 | 无论邮箱是否存在都返回同样结果（防枚举） |

### 2.2 `POST /api/auth/register`

| 项 | 内容 |
| --- | --- |
| 认证 | 无 |
| 请求 | `email, code, password, nickname, gender, grade, college, major, invite_code?` |
| 成功 | 201 `{user, access, expires_in:1800}` + refresh Cookie |
| 错误 | 400 `VALIDATION_ERROR`、`CODE_INVALID`、`CODE_EXPIRED`、`INVITE_INVALID`；403 `INVITE_REQUIRED`；409 `EMAIL_TAKEN`；429 `RATE_LIMITED` |
| 副作用 | 创建 User + 空 Profile + ContactInfo；写审计 `USER_REGISTERED`（可选） |

字段：

| 字段 | 类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `email` | string | 是 | 邮箱格式；不限制域名（开发期）；lower；唯一 |
| `code` | string(6) | 是 | 邮箱验证码；开发期 `123456` |
| `password` | string | 是 | 8–64；Django 校验器；不返回 |
| `nickname` | string | 是 | 1–20 字；去首尾空白；不做唯一 |
| `gender` | enum | 是 | `MALE` / `FEMALE`；注册后学生不可改 |
| `grade` | int | 是 | 1–5 |
| `college` | string | 是 | 1–50 字；用于匹配/广场/时间窗 |
| `major` | string | 否 | ≤50 字；空字符串 |
| `invite_code` | string | 条件 | `INVITE_REQUIRED=true` 时必填；8–12 位 |

### 2.3 `POST /api/auth/login`

请求 `{email,password}`；成功 200 `{user,access,expires_in}` + Cookie；错误 401 `INVALID_CREDENTIALS`、403 `ACCOUNT_DISABLED`、429 `RATE_LIMITED`。

### 2.4 `POST /api/auth/refresh`

| 项 | 内容 |
| --- | --- |
| 认证 | refresh Cookie；Origin/Referer 校验 |
| 请求 | 无 body |
| 成功 | 200 `{access,expires_in:1800}` + 轮换后的 Set-Cookie |
| 错误 | 401 `TOKEN_INVALID`/`TOKEN_EXPIRED`；403 `FORBIDDEN`（来源非法）；429 `THROTTLED` |
| 副作用 | 旧 refresh 黑名单；不延长 refresh 绝对上限（7 天滚动） |

### 2.5 `POST /api/auth/logout`

认证：Cookie 或 access；成功 204；清 Cookie + refresh 黑名单；重复调用 204。

## 3. 资源 Schema

> 只列 HTTP 面字段；数据库细节见 03。所有 `avatar_key` ∈ 6 个默认头像（`avatar-01`…`avatar-06`）。

### 3.1 `UserSummary`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `uid` | string | 10 位数字 |
| `nickname` | string | 昵称 |
| `avatar_key` | string | 默认头像 key |
| `gender` | enum | `MALE/FEMALE`（同性别场景可省略） |
| `college` | string | 学院 |
| `major` | string | 可空，默认 `""` |
| `grade` | int | 1–5 |

### 3.2 `UserMe`

`UserSummary` +：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `role` | enum | `STUDENT/ADMIN` |
| `status` | enum | `ACTIVE/DISABLED` |
| `profile_completeness` | int | 0–100 |
| `questionnaire_version` | string | 当前 `v1` |
| `room` | `RoomSummary` \| null | 我的 ACTIVE 寝室；无则 null |
| `unread_count` | int | 未读通知数 |

### 3.3 `ContactInfo`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `qq` | string \| null | 5–12 位数字 |
| `wechat` | string \| null | 微信号 |
| `phone` | string \| null | 中国大陆 11 位 |
| `show_qq` / `show_wechat` / `show_phone` | bool | 仅本人 GET `/api/me/contact` 返回 |

> 请求详情中的 `contact` 只返回**已解锁且 show_* 为 true** 的字段；未填/关闭的字段省略（不返回 null 占位）。

### 3.4 `Profile`

| 字段 | 类型 | 可写 | 说明 |
| --- | --- | --- | --- |
| `hard_answers` | object | 是 | 11 个 key；选项字符串 |
| `soft_answers` | object | 是 | 6 个 key；int 1–5 |
| `red_lines` | string[] | 是 | 0–9 个 id |
| `red_lines_confirmed` | bool | 是 | 显式确认 |
| `tags` | string[] | 是 | 0–8 个固定标签 |
| `prompts` | object | 是 | 0–3 个；key 固定 6 个 |
| `dims` | object | 否 | 六维 0–100，服务端算 |
| `completeness` | int | 否 | 0–100，服务端算 |
| `questionnaire_version` | string | 否 | `v1` |

### 3.5 `Questionnaire`

```json
{
  "version": "v1",
  "hard": [
    {"key": "smoke", "title": "你吸烟吗？", "options": [{"value": "no", "label": "不吸", "score": 100}]}
  ],
  "soft": [
    {"key": "clean", "title": "你对整洁的要求", "min": 1, "max": 5, "labels": ["很随意", "..."]}
  ],
  "red_lines": [
    {"id": "smoke", "label": "吸烟", "description": "..."}
  ],
  "tags": [{"group": "作息", "name": "早睡早起"}],
  "prompts": [{"key": "weekend", "title": "周末通常怎么过？", "max_length": 120}]
}
```

> 完整题目、选项分值、标签分组以 03 §3–§7 为准；前端不硬编码，启动时拉取。

### 3.6 `RoomSummary`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | string | 9 位数字 |
| `title` | string | ≤30 字 |
| `capacity` | int | 2/4/6 |
| `member_count` | int | ACTIVE 成员数 |
| `status` | enum | `RECRUITING/FULL/LOCKED/ARCHIVED/DISSOLVED` |
| `gender` | enum | 快照 |
| `college` | string | 快照 |
| `major` | string | 可空 |
| `tags` | string[] | ≤8 |
| `owner` | `UserSummary` | 房主 |
| `member_preview` | `UserSummary[]` | 最多 6 个；列表页用 |
| `can_apply` | bool | 当前用户是否可申请（服务端算） |
| `my_role` | `OWNER/MEMBER/null` | 当前用户在本寝角色 |
| `pending_transfer` | `RoomTransferSummary` \| null | 仅房主/成员可见 |

### 3.7 `RoomDetail`

`RoomSummary` +：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `members` | `RoomMember[]` | 完整成员列表（昵称/uid/角色/加入时间） |
| `actions` | object | `can_lock/can_unlock/can_dissolve/can_leave/can_remove/can_transfer/can_edit` |
| `created_at` | string | 创建时间 |
| `archived_at` / `dissolved_at` | string \| null | 终态时间 |

`RoomMember`：`uid,nickname,avatar_key,role,status,created_at`；`status` 仅返回 ACTIVE（历史成员不返回）。

### 3.8 `RoomTransferSummary`

`id,status,from_owner:UserSummary,to_member:UserSummary,expires_at,created_at`。

### 3.9 `ConnectionSummary`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 内部 id |
| `type` | enum | `INVITE/APPLY` |
| `status` | enum | 7 个状态 |
| `direction` | enum | `inbox/sent`（相对当前用户） |
| `initiator` | `UserSummary` | 发起人 |
| `target` | `UserSummary` | 目标 |
| `room` | `RoomSummary` \| null | APPLY/房主邀请时有 |
| `message` | string | 可空 |
| `contact_shared_at` | string \| null | accept 时间 |
| `expires_at` | string | 当前状态截止时间 |
| `actions` | object | 见 §5.1 |

列表**不含** `contact`、`initiator_confirm_at/target_confirm_at`。

### 3.10 `ConnectionDetail`

`ConnectionSummary` +：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `initiator_confirm_at` / `target_confirm_at` | string \| null | 第二步确认时间 |
| `closed_by` | `UserSummary` \| null | 关闭操作者；系统为空 |
| `close_reason` | string | `CONFIRMED` 为空；其他见 02 |
| `contact` | object \| null | 仅解锁状态；`{qq?,wechat?,phone?,unlocked:true}`；否则 null |
| `version` | int | 审计辅助 |

### 3.11 `MatchScore`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `target` | `UserSummary` + `completeness` + `tags` + `headline?` | 候选人 |
| `score` | int | 0–100 |
| `base` | float | 1 位小数 |
| `tag_bonus` | int | 0–6 |
| `red_penalty` | int | 0–30 |
| `dims` | object | `{a,b,dim_score}` 六维 |
| `reasons` | string[] | 3 条 |
| `conflicts` | object[] | 双向红线 |
| `version_warning` | string \| null | 跨问卷版本提示 |

### 3.12 `Notification`

`id,type,title,payload,read_at,created_at`；`payload` 只含 id/昵称/房间号/原因/人数/时间，不含联系方式。

### 3.13 `Report` / `Block` / `Health`

- `Report`: `id,target_type,target_id,reason,status,handled_by?,created_at`。
- `Block`: `uid,nickname,avatar_key,created_at`。
- `Health`: `{status:"ok",version:"0.1.0",db:"ok",time:"..."}`；DB 不可用 503 `{status:"degraded",db:"error"}`。

## 4. 端点

> 所有受保护端点默认要求 access；下表“权限”指登录后的对象级规则。
> 写动作成功默认 200 + 更新后资源；创建 201；删除/无 body 204；错误见 §8。
> 每个写动作都在同一事务写通知 + 审计；响应不返回通知/审计明细。

### 4.1 我的

| 方法/路径 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/me` | 本人 | 用户 + 完整度 + 寝室摘要 + 未读数 |
| `PUT /api/me` | 本人 | 改昵称/年级/学院/专业；**性别不可改** |
| `DELETE /api/me` | 本人 | 逻辑删除；禁用级联（房主强制解散、成员退出、关闭在途请求），成功 204 |
| `GET /api/me/profile` | 本人 | 完整画像（含 dims/completeness） |
| `PUT /api/me/profile` | 本人 | 全量替换问卷字段；服务端重算 dims/completeness |
| `PATCH /api/me/profile` | 本人 | 局部更新；`red_lines/tags/prompts` 提供即整体替换 |
| `GET /api/me/contact` | 本人 | 唯一返回本人 contact 的接口（含 show_*） |
| `PUT /api/me/contact` | 本人 | 改 contact + show_* |
| `GET /api/questionnaire` | 登录 | v1 题目配置；可缓存 |

**GET /api/me 示例**

```json
{
  "uid": "0834215769",
  "nickname": "小满",
  "avatar_key": "avatar-01",
  "gender": "FEMALE",
  "college": "计算机学院",
  "major": "软件工程",
  "grade": 2,
  "role": "STUDENT",
  "status": "ACTIVE",
  "profile_completeness": 100,
  "questionnaire_version": "v1",
  "room": null,
  "unread_count": 3
}
```

**PUT /api/me 请求**

```json
{"nickname":"小满","grade":2,"college":"计算机学院","major":"软件工程"}
```

- 只更新提供的字段；`gender` 出现即 403 `GENDER_IMMUTABLE`。
- 修改学院/年级不自动改历史寝室快照；后续组寝写操作按新值校验。
- 有 ACTIVE 寝室或 open 请求时改学院：v1 允许保存，但后续请求可能 `WRONG_COLLEGE`；前端提示风险。**实现不额外加锁**（与 02 X-49 一致）。

**DELETE /api/me**

- 不因有 ACTIVE 寝室或 open 请求返回 409；按 02 X-35/X-51 做禁用级联：
  - 有 open 请求 → `CANCELLED` + `USER_DISABLED`；
  - 房主 → 强制解散房间（房间 `DISSOLVED`、成员 `LEFT(reason=DISSOLVED)`、在途请求关闭）；
  - 普通成员 → `LEFT(reason=USER_DISABLED)`；
  - 再逻辑删除：`status=DISABLED,is_active=false,email=anon+id@deleted.local`。
- 成功 204；之后 token 失效。

**PUT/PATCH /api/me/profile**

请求：`hard_answers,soft_answers,red_lines,red_lines_confirmed,tags,prompts`；响应 `Profile`。

- 完整度 <100 允许保存；只影响匹配/组寝门槛。
- 客户端传 `dims/completeness` 忽略并重算，不报错；传非 `v1` 的 `questionnaire_version` → 400 `QUESTIONNAIRE_VERSION_UNSUPPORTED`。
- `red_lines` 变更若未显式带 `red_lines_confirmed=true`，服务端置 false。
- 校验错误 `detail.fields`；错误码见 03 §10。

**GET/PUT /api/me/contact**

```json
{"qq":"12345678","wechat":"xiao_man","phone":null,"show_qq":true,"show_wechat":true,"show_phone":false}
```

- `qq` 5–12 位数字；`wechat` ≤40；`phone` 11 位；`null` 表示清空。
- 不影响已解锁请求的历史可见性；修改后下次 GET 生效。

### 4.2 用户与匹配

| 方法/路径 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/users/:uid` | 同院同性别；未被拉黑 | 公开画像摘要；越权 404 |
| `GET /api/match` | 同院同性别；画像 100 | 候选列表 + 分数；`major/tags/min_score/page/page_size` |
| `GET /api/match/:uid` | 同上 | 单人详情 + 分数 |
| `POST /api/match/:uid/score` | 同上 | 只计算，不落库；用于“测试”按钮；限频 60/h |

**GET /api/users/:uid** 响应：

```json
{
  "uid":"0519283746","nickname":"阿迟","avatar_key":"avatar-03","gender":"MALE",
  "college":"计算机学院","major":"计算机科学与技术","grade":2,
  "tags":["早睡","自习搭子","猫派"],
  "headline":"周末我更愿意在图书馆待一天，晚上回来打两把游戏。",
  "prompts":{"weekend":"..."},
  "completeness":100
}
```

- 不返回 contact、email、dims、red_lines。
- `headline` = 第一条 prompt（按 `weekend/small_thing/vibe/...` 顺序）截断 60 字；无则 null。

**GET /api/match query**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `major` | string | 模糊/精确？v1 精确匹配（前端下拉） |
| `tags` | string | 逗号分隔；候选至少含全部标签（AND） |
| `min_score` | int | 0–100；按 `score` 过滤 |
| `page/page_size` | int | 分页 |

响应 `Paginated<MatchScore>`；排序 `score DESC → completeness DESC → updated_at DESC → uid ASC`。

- 候选池 9 条硬过滤见 03 §8.2；已确认室友/在途请求对方默认排除。
- 画像 <100 的当前用户 → 403 `PROFILE_INCOMPLETE`；目标画像 <100 不进入列表；单查/评分 → 409 `TARGET_PROFILE_INCOMPLETE`（`detail.completeness`）。
- 被拉黑 → 403 `BLOCKED`；跨院/跨性别/目标不存在 → 404 `PROFILE_NOT_FOUND`（不泄露目标存在性）。

**POST /api/match/:uid/score**：无 body；200 `MatchScore`；不写通知/审计；限频。

### 4.3 寝室（学生端）

> **没有公开的 `POST /api/rooms`，也没有 `POST /api/rooms/:code/join`。**
> 寝室只能由 `type=INVITE, room=null` 的双方 confirm 创建；加入只能由 `INVITE(room≠null)` 或 `APPLY` 的双方 confirm 发生（02 §4.3/§4.4）。
>
> **路由约束**：`GET /api/rooms/:code` 使用 `<str:code>`，只接受 9 位数字 code；`PATCH/动作 /api/rooms/:id` 使用 `<int:id>`，只接受内部主键。两者 URL 形状相同但 converter 不同，Django 路由必须按 `mine` → 公开/详情 `str:code` → 管理 `int:id` 的顺序注册，避免 `GET /api/rooms/482913756` 被 id 路由误吞或 `PATCH /api/rooms/abc` 落不到详情路由。

| 方法/路径 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/rooms` | 同院同性别 | 广场：仅 `RECRUITING` 且有空位；`major/capacity/tags/page` |
| `GET /api/rooms/mine` | 本人 | 我的寝室 + 待处理申请 + pending 转让；无房 `room:null` |
| `GET /api/rooms/:code` | 同院同性别或本寝成员 | 详情；非本寝且学院/性别不符 404 |
| `PATCH /api/rooms/:id` | 房主 | 改 `title/tags`；`capacity` 出现即 409 `CAPACITY_IMMUTABLE` |
| `POST /api/rooms/:id/lock` | 房主 | `RECRUITING→LOCKED`；关闭该寝 open 请求 |
| `POST /api/rooms/:id/unlock` | 房主 | `LOCKED→RECRUITING`；不通知，只审计 |
| `POST /api/rooms/:id/dissolve` | 房主 | 解散；成员 `LEFT/DISSOLVED` |
| `POST /api/rooms/:id/leave` | 非房主 ACTIVE 成员 | 退出；房主 409 `OWNER_MUST_TRANSFER_OR_DISSOLVE` |
| `DELETE /api/rooms/:id/members/:uid` | 房主 | 移除 ACTIVE 非房主成员 |
| `POST /api/rooms/:id/transfer` | 房主 | 发起转让；目标为 ACTIVE 成员 |
| `POST /api/room-transfers/:id/accept` | 目标成员 | 接受；角色交换 |
| `POST /api/room-transfers/:id/decline` | 目标成员 | 拒绝 |
| `POST /api/room-transfers/:id/cancel` | 房主 | 取消 |
| `GET /api/public/rooms/:code` | 无 | 公开摘要；归档/解散 404 |

**GET /api/rooms** query：`major?`、`capacity?`（2/4/6）、`tags?`（逗号分隔，AND）、`page/page_size`；响应 `Paginated<RoomSummary>`；仅 `RECRUITING` 且有 `member_count<capacity`；排除拉黑、跨院/跨性别。

**GET /api/rooms/mine** 响应：

```json
{
  "room": {
    "code":"482913756","title":"小满的寝室","capacity":4,"member_count":2,
    "status":"RECRUITING","gender":"FEMALE","college":"计算机学院","tags":["早睡"],
    "owner":{"uid":"0834215769","nickname":"小满","avatar_key":"avatar-01"},
    "members":[{"uid":"0834215769","nickname":"小满","role":"OWNER","status":"ACTIVE","created_at":"..."}],
    "actions":{"can_lock":true,"can_unlock":false,"can_dissolve":true,"can_leave":false,"can_remove":true,"can_transfer":true,"can_edit":true}
  },
  "pending_applications": [
    {"id":123,"type":"APPLY","status":"PENDING","initiator":{"uid":"...","nickname":"..."},"message":"...","expires_at":"..."}
  ],
  "pending_transfer": null
}
```

- 无寝：`{"room":null,"pending_applications":[],"pending_transfer":null}`。
- `pending_applications` 仅房主可见；只含 `APPLY`/房主邀请的 open 请求；不含 contact。

**PATCH /api/rooms/:id** 请求 `{"title":"...","tags":[...]}`；`title` ≤30；`tags` ≤8；只房主；终态 409 `INVALID_STATE`。响应 `RoomDetail`。

**成员/房主动作**：请求无 body；成功 200 `RoomDetail` 或 `RoomMember` 列表；状态错误按 §8；副作用见 02 §4.5–§4.9。

**转让**：

- `POST /api/rooms/:id/transfer` body `{"to_uid":"..."}`；成功 201 `RoomTransferSummary`；同寝已有 PENDING → 409 `TRANSFER_EXISTS`。
- accept/decline/cancel 无 body；成功 200 `RoomTransferSummary`；过期 409 `TRANSFER_EXPIRED`；非目标 403 `FORBIDDEN`。
- 只允许同一时间一笔 PENDING；转让不影响房主/成员数。

**GET /api/public/rooms/:code** 响应：

```json
{
  "code":"482913756","title":"小满的寝室","capacity":4,"member_count":2,
  "status":"RECRUITING","college":"计算机学院","tags":["早睡"],
  "members":[{"nickname":"小满","avatar_key":"avatar-01"},{"nickname":"阿迟","avatar_key":"avatar-03"}]
}
```

- 无鉴权；`ARCHIVED/DISSOLVED` → 404 `ROOM_NOT_FOUND`；不返回 uid、contact、画像、dims。

### 4.4 组寝请求

| 方法/路径 | 权限 | 说明 |
| --- | --- | --- |
| `POST /api/connections` | 登录、画像 100、无寝、窗口开 | 创建邀请/申请 |
| `GET /api/connections` | 参与者 | 收件/发件；`role=inbox|sent`、`status` 可叠加 |
| `GET /api/connections/:id` | 参与者 | 详情；满足状态时含 contact |
| `POST /api/connections/:id/accept` | 目标 | 第一步同意；`PENDING→CONTACT_SHARED` |
| `POST /api/connections/:id/decline` | 目标 | `PENDING→DECLINED` |
| `POST /api/connections/:id/cancel` | 发起人(PENDING)/任一方(已 accept) | 撤回/结束了解 |
| `POST /api/connections/:id/confirm` | 双方 | 第二步确认；第一次→CONFIRMING，第二次→CONFIRMED |

**POST /api/connections** 请求：

```json
{"type":"INVITE","target_uid":"0519283746","capacity_pref":4,"message":"看到你也早睡，想认识一下～"}
```

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `type` | enum | `INVITE` / `APPLY` |
| `target_uid` | string | 10 位数字；不能自己；必须同院同性别；不能有 ACTIVE 寝/被拉黑 |
| `room_id` | int | `INVITE(room≠null)`、`APPLY` 必填；目标必须为房主；`INVITE(room=null)` 必须省略 |
| `capacity_pref` | int | 仅 `INVITE(room=null)` 必填；2/4/6；其他必须省略 |
| `message` | string | 可选；≤200 字；纯文本 |

组合校验（否则 400 `INVALID_TYPE` / `CAPACITY_INVALID`）：

- `INVITE + room=null + capacity_pref∈{2,4,6}`：人-人建寝邀请；
- `INVITE + room≠null + capacity_pref=null`：房主邀请入寝；
- `APPLY + room≠null + capacity_pref=null`：申请入寝。

成功 201 `ConnectionDetail`（不含 contact，因为还未 accept）；副作用：N-01 通知目标；审计 `CONNECTION_CREATED`。

错误：`WINDOW_CLOSED`、`PROFILE_INCOMPLETE`、`SELF_REQUEST`、`WRONG_GENDER`、`WRONG_COLLEGE`、`BLOCKED`、`ALREADY_IN_ROOM`、`TARGET_IN_ROOM`、`TARGET_PROFILE_INCOMPLETE`、`DUPLICATE_REQUEST`、`ROOM_FULL/LOCKED/ARCHIVED/DISSOLVED`、`INVALID_TARGET`、`RATE_LIMITED`、`COOLDOWN`（03 的 `REJOIN_NOT_ALLOWED` 用 `INVALID_STATE` + `detail.reason`）。

**GET /api/connections**

query：`role=inbox|sent`（默认 inbox）、`status=PENDING|CONTACT_SHARED|CONFIRMING|CONFIRMED|DECLINED|CANCELLED|EXPIRED`（可重复/逗号）、`page/page_size`。

响应 `Paginated<ConnectionSummary>`；排序 `updated_at DESC,id DESC`；列表不含 contact 和 confirm 时间。

**GET /api/connections/:id**

- 非参与者 → 404 `CONNECTION_NOT_FOUND`。
- `contact` 仅在状态 ∈ `{CONTACT_SHARED,CONFIRMING,CONFIRMED}` 且 `show_*` 为 true 时返回；否则 `null`。
- 关闭后立即隐藏（即使 cron 未跑）。
- `actions`：见 §5.1。

**accept**：仅 `target`；`PENDING`→`CONTACT_SHARED`；`contact_shared_at=now`；`expires_at=now+7d`；N-02 仅通知 initiator；审计 `CONNECTION_ACCEPTED`。响应 `ConnectionDetail`（此时含 contact，给双方）。

**decline**：仅 `target`；`PENDING`→`DECLINED`；`close_reason=DECLINED`；N-05 通知 initiator；审计。

**cancel**：

| 当前状态 | 操作者 | close_reason |
| --- | --- | --- |
| `PENDING` | 仅 initiator | `INITIATOR_CANCEL` |
| `CONTACT_SHARED` / `CONFIRMING` | 任一方 | `END_UNDERSTANDING` |

目标对 PENDING cancel → 403 `FORBIDDEN`；成功 200 + 状态；N-06 通知另一方。

**confirm**：

- 双方各一次；第一次：`CONTACT_SHARED→CONFIRMING`，写本人 `*_confirm_at`，`expires_at=now+48h`，N-03 通知对方；审计 `CONNECTION_CONFIRMED_STEP1`。
- 第二次：
  - `INVITE(room=null)`：建寝；`capacity=capacity_pref`；`owner=initiator`；`gender/college` 快照；`title="{nickname}的寝室"`；`tags` 合并去重≤8；`member_count=2`；`status=FULL if capacity==2 else RECRUITING`；双方 `ACTIVE/OWNER|MEMBER`；
  - `INVITE(room≠null)` / `APPLY`：锁 Room，重读空位，加入；`member_count+1`；满员转 FULL 并清理该寝其余 open 请求；
  - 关闭双方其余 open 请求 `AUTO_CANCELLED`；
  - 通知 N-04 `CONFIRMED`（双方）；若容量 2 另发 N-08 `ROOM_FULL`；审计 `ROOM_CREATED`/`MEMBER_JOINED`。
- 响应 `ConnectionDetail` + `room`（已成立）；错误：`ALREADY_CONFIRMED`、`INVALID_STATE`、`REQUEST_CLOSED`、`REQUEST_EXPIRED`、`WINDOW_CLOSED`、`ROOM_FULL`、`ROOM_LOCKED`、`ROOM_ARCHIVED`、`ROOM_DISSOLVED`、`TARGET_IN_ROOM`、`WRONG_GENDER`、`WRONG_COLLEGE`。

### 4.5 通知

| 方法/路径 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/notifications` | 本人 | 列表；`unread=true` 筛选；分页 |
| `GET /api/notifications/unread-count` | 本人 | `{count}`；20s 轮询 |
| `POST /api/notifications/:id/read` | 本人 | 标记已读；重复 200 |
| `POST /api/notifications/read-all` | 本人 | 全部已读；`{updated}` |

- 排序 `created_at DESC,id DESC`；列表含 `payload`（非敏感）。
- 通知不存在/非本人 → 404 `NOTIFICATION_NOT_FOUND`（新增；不泄露存在性）。
- 已读 90 天/未读 180 天清理；不影响审计。

### 4.6 安全（举报/拉黑）

| 方法/路径 | 权限 | 说明 |
| --- | --- | --- |
| `POST /api/reports` | 登录 | `target_type,target_id,reason`；201 |
| `GET /api/blocks` | 本人 | 拉黑列表；分页 |
| `POST /api/blocks` | 本人 | `{uid}`；幂等 204；取消双方在途请求 |
| `DELETE /api/blocks/:uid` | 本人 | 取消拉黑；幂等 204 |

**POST /api/reports**：`target_type ∈ {USER,ROOM,CONNECTION}`；`target_id` 内部 id；`reason` 1–200 字；同一目标重复举报允许（限频 10/日）；不自动封禁；不通知被举报人。

**拉黑副作用**：立即关闭双方 open 请求（`close_reason=BLOCKED`），匹配/广场/搜索双向不可见；已成立寝室保留（X-30），需退出/解散才能分开。

### 4.7 健康与管理

| 方法/路径 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/health` | 无 | DB/版本；DB 故障 503 |
| `GET /api/admin/stats` | staff | 可选看板：用户/寝室/请求/举报计数 |

## 5. 动作矩阵

### 5.1 连接请求

| 状态 | initiator 可做 | target 可做 | 说明 |
| --- | --- | --- | --- |
| `PENDING` | cancel | accept / decline | 目标不能 cancel（403） |
| `CONTACT_SHARED` | cancel / confirm | cancel / confirm | 双方可结束了解 |
| `CONFIRMING` | cancel（若自己未确认）/ confirm（若自己未确认） | 同左 | 已确认方不能再 confirm；可 cancel |
| `CONFIRMED` | 无 | 无 | 终态 |
| `DECLINED/CANCELLED/EXPIRED` | 无 | 无 | 终态 |

`actions` 字段（服务端按当前用户算）：

```json
{"can_accept":false,"can_decline":false,"can_cancel":true,"can_confirm":true,"can_view_contact":true}
```

### 5.2 寝室

| 状态 | 房主 | ACTIVE 成员 | 加入 |
| --- | --- | --- | --- |
| `RECRUITING` | 编辑/锁定/解散/转让/移除 | 退出 | 可（confirm） |
| `FULL` | 编辑/解散/转让/移除 | 退出 | 不可 |
| `LOCKED` | 编辑/解锁/解散/转让/移除 | 退出 | 不可 |
| `ARCHIVED` | 只读 | 只读 | 不可 |
| `DISSOLVED` | 只读 | 只读 | 不可 |

- 锁定只允许 `RECRUITING`；解锁只允许 `LOCKED`；容量不可改。
- 房主不能退出；必须先转让或解散。
- 归档成员 `ARCHIVED` 不占一人一寝；不可回流同一房间。

### 5.3 转让

| 状态 | 目标成员 | 房主 | 系统 |
| --- | --- | --- | --- |
| `PENDING` | accept / decline | cancel | 24h 过期 |
| `ACCEPTED` | 无 | 无 | 角色已交换 |
| `DECLINED` | 无 | 无 | — |
| `CANCELLED` | 无 | 无 | 解散/归档/目标离开触发 |
| `EXPIRED` | 无 | 无 | — |

## 6. 关键响应示例

### 6.1 登录

```json
{
  "user": {"uid":"0834215769","nickname":"小满","avatar_key":"avatar-01","gender":"FEMALE","college":"计算机学院","major":"软件工程","grade":2,"role":"STUDENT","status":"ACTIVE"},
  "access": "eyJ...",
  "expires_in": 1800
}
```

### 6.2 已解锁请求详情

```json
{
  "id": 123,
  "type": "INVITE",
  "status": "CONTACT_SHARED",
  "direction": "inbox",
  "initiator": {"uid":"0519283746","nickname":"阿迟","avatar_key":"avatar-03"},
  "target": {"uid":"0834215769","nickname":"小满","avatar_key":"avatar-01"},
  "room": null,
  "message": "看到你也早睡，想认识一下～",
  "contact_shared_at": "2026-11-15T10:12:00Z",
  "expires_at": "2026-11-22T10:12:00Z",
  "initiator_confirm_at": null,
  "target_confirm_at": null,
  "closed_by": null,
  "close_reason": "",
  "contact": {"qq":"12345678","wechat":"achi_0926","unlocked":true},
  "actions": {"can_accept":false,"can_decline":false,"can_cancel":true,"can_confirm":true,"can_view_contact":true},
  "version": 1
}
```

### 6.3 匹配结果

```json
{
  "target": {"uid":"0519283746","nickname":"阿迟","avatar_key":"avatar-03","college":"计算机学院","major":"计算机科学与技术","grade":2,"tags":["早睡","自习搭子","猫派"],"completeness":100,"headline":"..."},
  "score": 87,
  "base": 85.0,
  "tag_bonus": 4,
  "red_penalty": 0,
  "dims": {"a":{"sleep":90,"clean":80,"social":40,"noise":70,"boundary":80,"spend":50},"b":{"sleep":85,"clean":85,"social":35,"noise":65,"boundary":75,"spend":55},"dim_score":{"sleep":95,"clean":95,"social":95,"noise":95,"boundary":95,"spend":95}},
  "reasons": ["你们的作息节奏很接近，早睡/早起冲突会少很多。","整洁习惯高度一致，公共区摩擦会少很多。","都有「猫派」标签，容易聊到一起。"],
  "conflicts": [],
  "version_warning": null
}
```

### 6.4 错误

```json
{"code":"ROOM_FULL","message":"房间已满员","detail":{"room_code":"482913756"}}
```

## 7. 状态前置条件与副作用速查

| 动作 | 前置 | 事务内写 | 通知 | 审计 |
| --- | --- | --- | --- | --- |
| 创建请求 | 窗口开、画像 100、双方无寝、同院同性别、未拉黑、无限频 | 请求 + 通知 + 审计 | N-01 | `CONNECTION_CREATED` |
| accept | target、PENDING、窗口开、双方无寝 | 状态/时间；通知/审计 | N-02 | `CONNECTION_ACCEPTED` |
| decline | target、PENDING | 状态；通知/审计 | N-05 | `CONNECTION_DECLINED` |
| cancel | 见 §4.4 | 状态/原因；通知/审计 | N-06 | `CONNECTION_CANCELLED` |
| confirm 第一次 | 参与者、CONTACT_SHARED、窗口开 | 本人时间/状态；通知/审计 | N-03 | `CONNECTION_CONFIRMED_STEP1` |
| confirm 第二次 | 双方已确认、窗口开、房间可加入 | 建寝/入寝 + 成员 + 清理其他请求 + 通知/审计 | N-04/N-07/N-08 | `CONNECTION_CONFIRMED` + `ROOM_CREATED`/`MEMBER_JOINED` |
| 锁定 | 房主、RECRUITING、窗口开 | 状态 + 关闭请求 + 通知/审计 | N-10/N-06 | `ROOM_LOCKED` |
| 解锁 | 房主、LOCKED、窗口开 | 状态；审计 | 无 | `ROOM_UNLOCKED` |
| 退出/移除 | 成员/房主、窗口开、非终态 | 成员 + member_count + 房间状态回退 + 取消转让 + 通知/审计 | N-09/N-17 | `MEMBER_LEFT`/`MEMBER_REMOVED` |
| 解散 | 房主、非终态、窗口开 | 房间 + 成员 + 清理请求/转让 + 通知/审计 | N-11/N-06/N-17 | `ROOM_DISSOLVED` |
| 归档 | cron、窗口结束 | 房间 + 成员 + 清理请求/转让 + 通知/审计 | N-12/N-06/N-17 | `ROOM_ARCHIVED` |
| 转让发起/接受/拒绝/取消 | 见 02 §6 | 转让 + 角色（接受）+ 通知/审计 | N-13～N-17 | 对应 action |

## 8. 错误码总表

> HTTP 状态表达类别；同一 code 只对应一个状态。`detail` 为对象或 `null`。
> `VALIDATION_ERROR` 的 `detail.fields` 为字段级错误；`PROFILE_INCOMPLETE` 的 `detail.missing` 为缺失区块。

| HTTP | code | 典型场景 |
| --- | --- | --- |
| 400 | `VALIDATION_ERROR` | 缺字段/类型错/长度/格式 |
| 400 | `UNKNOWN_FIELD` | 画像等写入体出现未定义顶层字段；`detail.fields.{field}.code` |
| 400 | `INVALID_TYPE` | `INVITE+room+capacity_pref`、`APPLY+capacity_pref` 等组合非法 |
| 400 | `CAPACITY_INVALID` | `capacity_pref` 不是 2/4/6 |
| 400 | `SELF_REQUEST` | 自己邀请/申请自己 |
| 400 | `INVALID_TARGET` | APPLY 目标非房主、room INVITE 发起人非房主、转让目标非本寝成员 |
| 400 | `CODE_INVALID` | 邮箱验证码错误 |
| 400 | `CODE_EXPIRED` | 验证码过期 |
| 400 | `INVITE_INVALID` | 邀请码不存在/过期/停用/耗尽（统一） |
| 401 | `AUTH_REQUIRED` | 未登录/无 token |
| 401 | `TOKEN_INVALID` / `TOKEN_EXPIRED` | access 无效/过期 |
| 401 | `INVALID_CREDENTIALS` | 登录邮箱/密码错 |
| 403 | `FORBIDDEN` | 已登录但动作不允许 |
| 403 | `NOT_OWNER` | 非房主执行房主动作 |
| 403 | `NOT_MEMBER` | 非本寝成员执行成员动作 |
| 403 | `ACCOUNT_DISABLED` | 账号被禁用 |
| 403 | `GENDER_IMMUTABLE` | 学生自改性别 |
| 403 | `WRONG_GENDER` | 性别不匹配 |
| 403 | `WRONG_COLLEGE` | 学院不匹配 |
| 403 | `BLOCKED` | 双方存在拉黑 |
| 403 | `INVITE_REQUIRED` | 生产环境注册未填邀请码 |
| 404 | `CONNECTION_NOT_FOUND` | 请求不存在或当前用户非参与者 |
| 404 | `ROOM_NOT_FOUND` | 寝室不存在/不可见/已归档/已解散（公开页） |
| 404 | `TRANSFER_NOT_FOUND` | 转让不存在或非本寝 |
| 404 | `USER_NOT_FOUND` | 用户不存在/已禁用（创建请求） |
| 404 | `PROFILE_NOT_FOUND` | 画像不存在/匹配目标不在候选池（不泄露存在性） |
| 404 | `NOTIFICATION_NOT_FOUND` | 通知不存在/非本人 |
| 409 | `INVALID_STATE` | 当前状态不允许该动作；`detail.reason` 可含 `REJOIN_NOT_ALLOWED` |
| 409 | `REQUEST_CLOSED` | 请求已终态 |
| 409 | `REQUEST_EXPIRED` | 懒过期刚关闭 |
| 409 | `ALREADY_CONFIRMED` | 本人已确认过 |
| 409 | `ALREADY_IN_ROOM` | 自己已有 ACTIVE 寝室 |
| 409 | `TARGET_IN_ROOM` | 对方已有 ACTIVE 寝室 |
| 409 | `DUPLICATE_REQUEST` | 双方已有在途请求（任一方向） |
| 409 | `ROOM_FULL` | 寝室已满 |
| 409 | `ROOM_LOCKED` | 寝室已锁定 |
| 409 | `ROOM_ARCHIVED` / `ROOM_DISSOLVED` | 寝室已归档/解散 |
| 409 | `WINDOW_CLOSED` | 时间窗未开放/已关闭 |
| 409 | `PROFILE_INCOMPLETE` | 本人完整度 <100 |
| 409 | `TARGET_PROFILE_INCOMPLETE` | 对方完整度 <100 |
| 409 | `OWNER_MUST_TRANSFER_OR_DISSOLVE` | 房主不能直接退出 |
| 409 | `CANNOT_REMOVE_OWNER` | 不能移除房主 |
| 409 | `TRANSFER_EXISTS` | 同寝已有 PENDING 转让 |
| 409 | `TRANSFER_EXPIRED` | 转让已过期 |
| 409 | `CAPACITY_IMMUTABLE` | 试图改容量 |
| 409 | `EMAIL_TAKEN` | 注册邮箱已存在 |
| 429 | `RATE_LIMITED` | 业务限频 |
| 429 | `COOLDOWN` | 被拒 24h 冷却 |
| 429 | `THROTTLED` | DRF 全局限流 |
| 500 | `INTERNAL_ERROR` | 未预期异常；带 request_id |
| 500 | `ROOM_CODE_GENERATION_FAILED` | 9 位码重试 5 次仍碰撞 |

## 9. OpenAPI 与契约冻结

- 机器可读契约：`docs/openapi.yaml`（OpenAPI 3.0.3）；与本文冲突以本文为准，并同步修 YAML。
- 生成命令：`python manage.py spectacular --file docs/openapi.yaml --validate`（P1 接入后）。
- 前端类型：P3 从 OpenAPI 生成 `src/types/api.d.ts`；不要手写重复类型。
- 变更流程：改 02/03/04 → 改 OpenAPI → 评审 → 前端类型/调用 → 测试；D11 起 API 冻结。
- 契约测试：P2 用 DRF `APIClient` 覆盖 §10 的 A 组；P5 做端到端。

## 10. 契约验收清单

| 编号 | 检查 |
| --- | --- |
| A-01 | 所有受保护端点无 token → 401 `AUTH_REQUIRED` |
| A-02 | 非参与者 GET 连接详情 → 404 `CONNECTION_NOT_FOUND` |
| A-03 | 未解锁状态详情 `contact=null`；列表永不出现 contact |
| A-04 | `PUT /api/me` 带 `gender` → 403 `GENDER_IMMUTABLE` |
| A-05 | 画像提交未知顶层字段/未知 key/非法选项 → 400 + `detail.fields`（顶层未知字段为 `UNKNOWN_FIELD`） |
| A-06 | 创建请求组合非法 → 400 `INVALID_TYPE`/`CAPACITY_INVALID` |
| A-07 | 重复创建 → 409 `DUPLICATE_REQUEST`；重复 confirm → 409 `ALREADY_CONFIRMED` |
| A-08 | 容量 2 建寝 → `status=FULL`；容量 4 → `RECRUITING` |
| A-09 | 满员加入 → 409 `ROOM_FULL`；锁定加入 → 409 `ROOM_LOCKED` |
| A-10 | 房主退出 → 409 `OWNER_MUST_TRANSFER_OR_DISSOLVE` |
| A-11 | 窗口关闭创建/accept/confirm → 409 `WINDOW_CLOSED`；资料/问卷仍可写 |
| A-12 | 分页 `page_size>50` → 服务端按最大 50 截断，返回 200，不报错 |
| A-13 | 公开寝室页归档/解散 → 404；不返回 contact/uid |
| A-14 | 注册重复邮箱 → 409 `EMAIL_TAKEN`；邀请码错误统一 400 `INVITE_INVALID` |
| A-15 | 限频超限 → 429 + `Retry-After` |

## 11. 与手册 §7 的差异登记

| # | 差异 | 依据 | 处理 |
| --- | --- | --- | --- |
| D-01 | 删除 `POST /api/rooms`；建寝只能由 `INVITE(room=null)` 双方 confirm | 02 §4.3 | 手册 §7.2 该行改为“不提供”；前端不提供“直接建寝”表单 |
| D-02 | 新增 `PATCH /api/me/profile` | 03 §2.3 | 手册 §7.2 补一行；PUT 仍保留全量 |
| D-03 | `POST /api/blocks` 幂等 204，重复拉黑不报错 | 本契约 | 前端无需分支 |
| D-04 | 非参与者/越权统一 404，不用 `NOT_PARTICIPANT` | 02 §10.2 | 手册 §7.4 备注已有；错误码表不再返回 `NOT_PARTICIPANT` |
| D-05 | `INVITE_CODE_INVALID` 统一为 `INVITE_INVALID` | 手册 §7.4 | 03 §1.3.4 已同步 |
| D-06 | 分页上限 50（脚手架已修正） | 手册 §7.1 | `config/api.py` 的 `max_page_size=50` 已改 |
| D-07 | `RoomMember` 用 `created_at`，不设 `joined_at` | 03 §1.5.2 | 02 §5.1/§5.3 的“joined_at”字样已修正 |
| D-08 | 举报不提供列表；处理结果可选 `SYSTEM` 通知 | 03 §1.8.2 | 手册 §7.2 不新增端点 |

## 12. 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0-draft | 2026-11-15 | 首版：认证/我的/匹配/寝室/请求/通知/安全/错误/限频/验收 |
| v1.1-draft | 2026-11-15 | 实现澄清：匹配单查目标画像 <100 → `TARGET_PROFILE_INCOMPLETE`；跨院/跨性别/目标不存在 → `PROFILE_NOT_FOUND`（不泄露存在性）；同步 03 §8.7/§10.2、06 M-08 |
| v1.2-draft | 2026-11-15 | 实现澄清：画像写入未知顶层字段 → 400 `UNKNOWN_FIELD`；补 §8/A-05，同步 03 §10.2/§13.4 |
