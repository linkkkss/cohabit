# seed 数据规格（seed_demo）

> 状态：M4 交付物（2026-11-15，v2）｜作者：P5（product-qa）｜写权限：本文件
> 用途：给 P1 实现 `python manage.py seed_demo` 的**字段级规格**，并作为 QA 验收种子数据的依据。
> 上游契约：[03 数据字典与问卷](03-数据字典与问卷.md) §11（40 人 / 6 寝 / 8 请求）、§1（字段与约束）、§2（画像 JSON）、§3–§7（题库）、§9（通知）；[02 组寝状态机](02-组寝状态机.md) §4（寝室不变量）、§3（请求）；[04 API 契约](04-API契约.md) §3（Schema）、§1.7（隐私）。
> 本文件**不含代码**；P1 按此实现，P5 用本文 §10 自检。

## 0. 范围与原则

| 项 | 规定 |
| --- | --- |
| 覆盖 | 40 名学生、6 间寝室、8 条组寝请求、2 条转让、通知、2 条时间窗、1 个邀请码、2 条举报、2 对拉黑（+审计抽样） |
| 不覆盖 | 真实姓名/真实邮箱/真实联系方式；不覆盖 M3 之后的举报处置流程、Admin 报表 |
| 依据 | 字段与枚举一律以 03 §1 为准；状态机与不变量以 02 §3/§4 为准；不得在本文件发明字段 |
| 确定性 | 禁止 `random`/`faker`/时间抖动；所有值由固定表或索引推导；时间相对 `now` 取整到分钟 |
| 可重复 | `--reset` 后重复执行，对象数量、uid、code、状态分布完全一致（时间按当时 `now` 平移） |
| 隐私 | 所有联系方式为合成值；通知 payload 不含 contact/email/token；日志不打印密码 |
| 安全 | `settings.DEBUG=False` 时拒绝执行，除非显式 `--force`；生产库即使 `--force` 也拒绝（见 §1.3） |

## 1. 命令契约

### 1.1 调用方式

```bash
python manage.py seed_demo            # 空库/无 seed 数据时创建
python manage.py seed_demo --reset    # 删除本命令创建的种子数据后重建（默认演示用法）
python manage.py seed_demo --force    # 仅 DEBUG=False 时需要，显式确认非生产
```

### 1.2 执行顺序（单事务）

1. 校验环境（§1.3）。
2. `--reset` 时按 §1.4 顺序删除种子数据；没有 `--reset` 且检测到种子数据 → 退出码 2，不写入。
3. 创建学院常量（不建表，仅字符串）、管理员、40 名学生。
4. 创建 `ContactInfo`、`Profile`（先写原始 JSON，再调用**与服务端同一纯函数** `recompute_profile` 计算 `dims/completeness`）。
5. 创建 6 间 `Room` + `RoomMember`（含归档/解散历史成员）。
6. 创建 8 条 `ConnectionRequest`（按时间从旧到新，保证 `created_at < updated_at` 语义合理）。
7. 创建 2 条 `RoomTransfer`。
8. 创建 `Notification`（按事件时间）、`Report`、`Block`、`AuditLog`（抽样）。
9. 创建 2 条 `TimeWindow`、1 个 `InviteCode`。
10. 事务提交前执行 §10 断言；任一失败 → 回滚并退出码 1。
11. 打印计数摘要（§12）。

### 1.3 守卫

| 条件 | 行为 |
| --- | --- |
| `settings.DEBUG is False` 且无 `--force` | `CommandError`：`seed_demo 拒绝在非 DEBUG 环境执行（如确需，使用 --force）`，退出码 1 |
| `settings.DEBUG is False` 且有 `--force`，但检测到 `ENV=production` 或 `DATABASE_URL` 含非本地主机 | 拒绝，退出码 1 |
| 数据库未迁移（缺表） | 直接抛错，提示先 `migrate` |
| 已有种子数据且无 `--reset` | 退出码 2，提示“已存在种子数据；使用 --reset 重建” |
| 非种子用户/寝室/请求存在 | 不删除、不修改；只操作 §1.4 定义的范围 |

### 1.4 删除范围与顺序（`--reset`）

按外键依赖从子到父，且**只删种子对象**：

1. `Notification`（user ∈ 种子用户）
2. `Report`（reporter ∈ 种子用户）
3. `Block`（任一侧 ∈ 种子用户）
4. `RoomTransfer`（room.code ∈ 100000001–100000006）
5. `ConnectionRequest`（initiator 与 target 均 ∈ 种子用户，或 room.code ∈ 种子寝室）
6. `RoomMember`（同上）
7. `Room`（code ∈ 100000001–100000006）
8. `AuditLog`（actor/meta 指向种子对象，且 `request_id` 为空）
9. `Profile`（user ∈ 种子用户）
10. `ContactInfo`（user ∈ 种子用户）
11. `InviteCode`（code=COHAB2026）
12. `TimeWindow`（college ∈ 两学院）
13. `User`（uid ∈ `0000000001`–`0000000040`，或 email=`admin@cohabit.local`）

> 禁止 `Model.objects.all().delete()`；禁止按 `created_at` 批量删除。非种子数据必须原样保留（自检：删除前后非种子对象计数不变）。

## 2. 字段清单（逐模型）

> 只列**种子必须赋值的字段**；未列字段用模型默认值。约束列引用 03 §1 / 02 §4。

### 2.1 User（41 行 = 40 学生 + 1 管理员）

| 字段 | 学生取值 | 管理员 | 约束 |
| --- | --- | --- | --- |
| `uid` | `0000000001`…`0000000040`（按 §3 表） | `0000000099` | 10 位数字，unique |
| `email` | `demo001@stu.edu.cn`…`demo040@stu.edu.cn` | `admin@cohabit.local` | lower，unique |
| `password` | `Demo1234!`（`set_password`） | `Admin1234!` | 8–64 |
| `nickname` | 小算01…小算20 / 小外01…小外20 | 管理员 | 1–20 |
| `gender` | 男=`MALE`，女=`FEMALE`（§3） | `MALE` | 注册后不可改 |
| `grade` | 1–4（§3 规则） | 1 | 1–5 |
| `college` | `计算机学院` / `外国语学院` | `计算机学院` | 1–50 |
| `major` | 计算机：`软件工程`/`计算机科学`；外国语：`英语`/`日语` | `软件工程` | ≤50 |
| `role` | `STUDENT` | `ADMIN` | 枚举 |
| `status` | `ACTIVE` | `ACTIVE` | 枚举 |
| `is_staff` | `False` | `True` | — |
| `is_active` | `True` | `True` | — |
| `last_login` | `None` | `None` | 不伪造登录 |

> 学生不建 `UserProfile` 之外的账号；管理员**不建** `Profile`/`ContactInfo`（不参与匹配）。

### 2.2 ContactInfo（40 行）

| 字段 | 规则 |
| --- | --- |
| `qq` | 全部为 `None`，除 §9.3 指定用户（如小算09=`123456789`）；值是 5–12 位数字 |
| `wechat` | 全部 `None`，除 §9.3 指定用户（合成值，如 `demo_09`） |
| `phone` | 一律 `None`（避免任何真实手机号形态） |
| `show_qq` | 默认 `True`；仅对已填 `qq` 的用户有意义 |
| `show_wechat` | 默认 `False` |
| `show_phone` | 默认 `False` |

> 演示需要“解锁后能看到联系方式”，故至少 4 名自由用户填写 `qq` 且 `show_qq=True`（§9.3）。

### 2.3 Profile（40 行）

| 字段 | 规则 |
| --- | --- |
| `user` | 1:1 对应 40 名学生 |
| `hard_answers` | 11 个 key 全填，枚举见 03 §3；值来自 §9.1 cohort 表 |
| `soft_answers` | 6 个 key 全填，1–5 整数；来自 §9.1 |
| `red_lines` | 0–3 个，枚举见 03 §5；覆盖要求见 §9.4 |
| `red_lines_confirmed` | 全部 `True`（否则 completeness 不可能 100） |
| `tags` | 3–6 个，见 03 §6；分组覆盖见 §9.5 |
| `prompts` | 2–3 条，key 见 03 §7；覆盖见 §9.6 |
| `dims` | **不手写**，由 `recompute_profile` 生成；6 个 key，0–100 整数 |
| `completeness` | **不手写**，必须为 `100` |
| `questionnaire_version` | `"v1"` |

### 2.4 Room（6 行）

| 字段 | 规则 |
| --- | --- |
| `code` | 固定 `100000001`…`100000006`（9 位数字，unique） |
| `title` | 默认 `"{owner.nickname}的寝室"`；允许 §4 表中的自定义标题，≤30 字 |
| `owner` | 见 §4；必须同时存在一条 `RoomMember(role=OWNER, status=ACTIVE)`（归档/解散房间为历史 OWNER 行） |
| `capacity` | 2/4/6（§4） |
| `member_count` | 非归档/非解散：等于 ACTIVE 成员数；`ARCHIVED`：保留归档快照（6）；`DISSOLVED`：`0`（02 §4 不变量） |
| `gender` | 创建者性别快照（同寝室成员同性别） |
| `college` | 创建者学院快照（同寝室成员同学院） |
| `major` | 创建者专业快照 |
| `tags` | 成员标签并集去重，≤8；无标签时 `[]` |
| `status` | `RECRUITING`/`FULL`/`LOCKED`/`ARCHIVED`/`DISSOLVED`（§4） |
| `archived_at` | `ARCHIVED` 必填；`DISSOLVED` 同步写入（02 §4 解散流程） |
| `dissolved_at` | `DISSOLVED` 必填 |
| `created_at` | 与 §4 时间偏移一致，早于所有成员加入时间 |

### 2.5 RoomMember（20 行）

| 字段 | 规则 |
| --- | --- |
| `room` | §4 |
| `user` | §4 |
| `role` | 每间房恰好 1 个 `OWNER`，其余 `MEMBER` |
| `status` | 非终态房 `ACTIVE`；#5 `ARCHIVED`；#6 `LEFT` |
| `left_at` | 归档=归档时间；解散=解散时间；ACTIVE=`None` |
| `reason` | #5 `ARCHIVED`；#6 `DISSOLVED`；ACTIVE=`""` |

> 部分唯一索引（03 §1）必须在种子数据上成立：一人一个 ACTIVE 寝室、一房一人、一房一个 ACTIVE OWNER。
> 归档/解散成员**不占名额**、不能回到同一房间（R-13），但可加入其他房间/新建（03 §11）。

### 2.6 ConnectionRequest（8 行）

| 字段 | 规则 |
| --- | --- |
| `type` | 全部 `INVITE`（`room=NULL`，人-人） |
| `initiator` / `target` | §5；同学院同性别 |
| `room` | 仅 CONFIRMED 两条指向已建寝室（#1/#2），其余 `NULL` |
| `status` | `PENDING`×2、`CONTACT_SHARED`×2、`CONFIRMING`×2、`CONFIRMED`×2 |
| `message` | ≤200 字；演示友好文案，见 §5 |
| `capacity_pref` | 2/4/6；`room=NULL` 时必填（§5） |
| `contact_shared_at` | 非 PENDING 必填；`CONFIRMING/CONFIRMED` 必有 |
| `initiator_confirm_at` | `CONFIRMING`：发起方已确认；`CONFIRMED`：双方均非空 |
| `target_confirm_at` | 同上；`CONFIRMING` 时 `NULL` |
| `expires_at` | PENDING `now+48h`；CONTACT_SHARED `contact_shared_at+7d`；CONFIRMING `first_confirm+48h`；CONFIRMED `NULL` |
| `closed_by` | 全部 `NULL`（无关闭态） |
| `close_reason` | 全部 `""`（`CONFIRMED` 按 03 §1 为空） |
| `created_at` | §5 偏移；早于 `contact_shared_at` |

### 2.7 RoomTransfer（2 行）

| 字段 | 规则 |
| --- | --- |
| `room` / `from_owner` / `to_member` | §6；`to_member` 必须是该房 ACTIVE MEMBER |
| `status` | `PENDING`×1、`EXPIRED`×1 |
| `expires_at` | PENDING `now+24h`；EXPIRED `now-24h` |
| `decided_at` | PENDING `NULL`；EXPIRED `NULL`（过期由 cron/懒判定） |
| `created_at` | PENDING `now-1h`；EXPIRED `now-2d` |

### 2.8 Notification（约 70–90 行，每人 0–5 条）

| 字段 | 规则 |
| --- | --- |
| `user` | 种子用户；每用户总数 ≤5（超出按 §7.3 规则跳过） |
| `type` | 03 §9 枚举；覆盖率见 §7.1（≥10 种） |
| `title` | 用 03 §9 模板渲染（昵称/编号替换） |
| `payload` | 仅允许：`connection_id`/`room_code`/`room_title`/`nickname`/`reason`/`counts`/`capacity`/`days`；**禁止** `contact`/`email`/`token`/`qq`/`wechat`/`phone` |
| `read_at` | 已读=事件时间+1h；未读=`NULL`；混合比例见 §7.2 |
| `created_at` | 事件发生时间（不晚于 `now`） |

### 2.9 TimeWindow（2 行）

| 字段 | 规则 |
| --- | --- |
| `college` | `计算机学院`、`外国语学院` 各 1（unique） |
| `start_at` | `now-1d` 的 00:00 |
| `end_at` | `now+7d` 的 23:59 |
| `note` | `M1 演示窗口（seed）` |

### 2.10 InviteCode（1 行）

| 字段 | 规则 |
| --- | --- |
| `code` | `COHAB2026`（8–12 位、大写、无 0/O/1/I） |
| `note` | `M1 演示邀请码` |
| `max_uses` | `0`（不限） |
| `used_count` | `0` |
| `expires_at` | `now+30d` |
| `is_active` | `True` |
| `created_by` | 管理员 |

### 2.11 Report（2 行）

| 字段 | 规则 |
| --- | --- |
| #1 | `reporter=小算07`、`target_type=USER`、`target_id=小算08.id`、`reason="言语不当（演示数据）"`、`status=OPEN`、`handled_by=NULL` |
| #2 | `reporter=小外19`、`target_type=ROOM`、`target_id=#4.id`、`reason="描述与实际不符（演示数据）"`、`status=RESOLVED`、`handled_by=admin` |
| 约束 | `target_id` 是内部 `id`，**不是 uid/code**；seed 必须先查 id 再写；`reason` ≤200 |

### 2.12 Block（4 行 = 2 对互拉黑）

| 对 | 行 |
| --- | --- |
| 小算07 ↔ 小算08 | 07→08、08→07 |
| 小外19 ↔ 小外20 | 19→20、20→19 |

> 03 §11 写“2 对”；本规格实现为 2 对互拉黑共 4 行，计数摘要按“2 对（4 行）”输出。若 03 口径按行计，则删去反向 2 行（P1 以本文件为准，QA 按 §10 断言）。

### 2.13 AuditLog（抽样 10 行，可选但建议）

| 动作 | 对象 | 数量 |
| --- | --- | --- |
| `ROOM_CREATED` | #1、#2 | 2 |
| `MEMBER_JOINED` | #2 的 12/13 | 2 |
| `ROOM_LOCKED` | #4 | 1 |
| `ROOM_ARCHIVED` | #5 | 1 |
| `ROOM_DISSOLVED` | #6 | 1 |
| `TRANSFER_REQUESTED` | #1 转让 | 1 |
| `ROOM_UPDATED` | #1 改标题/标签 | 1 |
| `USER_REGISTERED` | 小算01 | 1 |

> `meta` 只放编号/昵称/状态；`actor` 为管理员或房主；`request_id` 留空（非 HTTP 触发）。

## 3. 账号矩阵（40 学生）

规则：

- 计算机学院：`小算01`–`小算20`，`demo001`–`demo020`；男 01–10、女 11–20。
- 外国语学院：`小外01`–`小外20`，`demo021`–`demo040`；男 01–10、女 11–20。
- `uid`：`0000000001`–`0000000020` 对应计算机 01–20；`0000000021`–`0000000040` 对应外国语 01–20。
- `grade = ((n-1) % 4) + 1`（n 为学院内序号）→ 每院每年级 5 人，全库每年级 10 人。
- `major`：序号奇数=`软件工程`/`英语`，偶数=`计算机科学`/`日语`。
- 密码统一 `Demo1234!`。

| uid | 昵称 | 邮箱 | 性别 | 学院 | 年级 | 专业 | 寝室 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0000000001 | 小算01 | demo001@stu.edu.cn | 男 | 计算机学院 | 1 | 软件工程 | #1 房主 |
| 0000000002 | 小算02 | demo002@stu.edu.cn | 男 | 计算机学院 | 2 | 计算机科学 | #1 |
| 0000000003 | 小算03 | demo003@stu.edu.cn | 男 | 计算机学院 | 3 | 软件工程 | #3 房主 |
| 0000000004 | 小算04 | demo004@stu.edu.cn | 男 | 计算机学院 | 4 | 计算机科学 | #3 |
| 0000000005 | 小算05 | demo005@stu.edu.cn | 男 | 计算机学院 | 1 | 软件工程 | #3 |
| 0000000006 | 小算06 | demo006@stu.edu.cn | 男 | 计算机学院 | 2 | 计算机科学 | #3 |
| 0000000007 | 小算07 | demo007@stu.edu.cn | 男 | 计算机学院 | 3 | 软件工程 | 无 |
| 0000000008 | 小算08 | demo008@stu.edu.cn | 男 | 计算机学院 | 4 | 计算机科学 | 无 |
| 0000000009 | 小算09 | demo009@stu.edu.cn | 男 | 计算机学院 | 1 | 软件工程 | 无（演示对象） |
| 0000000010 | 小算10 | demo010@stu.edu.cn | 男 | 计算机学院 | 2 | 计算机科学 | 无（冲突演示） |
| 0000000011 | 小算11 | demo011@stu.edu.cn | 女 | 计算机学院 | 3 | 软件工程 | #5 历史房主（归档） |
| 0000000012 | 小算12 | demo012@stu.edu.cn | 女 | 计算机学院 | 4 | 计算机科学 | #5（归档） |
| 0000000013 | 小算13 | demo013@stu.edu.cn | 女 | 计算机学院 | 1 | 软件工程 | #5（归档） |
| 0000000014 | 小算14 | demo014@stu.edu.cn | 女 | 计算机学院 | 2 | 计算机科学 | #5（归档） |
| 0000000015 | 小算15 | demo015@stu.edu.cn | 女 | 计算机学院 | 3 | 软件工程 | #5（归档） |
| 0000000016 | 小算16 | demo016@stu.edu.cn | 女 | 计算机学院 | 4 | 计算机科学 | #5（归档） |
| 0000000017 | 小算17 | demo017@stu.edu.cn | 女 | 计算机学院 | 1 | 软件工程 | 无 |
| 0000000018 | 小算18 | demo018@stu.edu.cn | 女 | 计算机学院 | 2 | 计算机科学 | 无 |
| 0000000019 | 小算19 | demo019@stu.edu.cn | 女 | 计算机学院 | 3 | 软件工程 | 无 |
| 0000000020 | 小算20 | demo020@stu.edu.cn | 女 | 计算机学院 | 4 | 计算机科学 | 无 |
| 0000000021 | 小外01 | demo021@stu.edu.cn | 男 | 外国语学院 | 1 | 英语 | #4 房主 |
| 0000000022 | 小外02 | demo022@stu.edu.cn | 男 | 外国语学院 | 2 | 日语 | #4 |
| 0000000023 | 小外03 | demo023@stu.edu.cn | 男 | 外国语学院 | 3 | 英语 | #4 |
| 0000000024 | 小外04 | demo024@stu.edu.cn | 男 | 外国语学院 | 4 | 日语 | 无 |
| 0000000025 | 小外05 | demo025@stu.edu.cn | 男 | 外国语学院 | 1 | 英语 | 无 |
| 0000000026 | 小外06 | demo026@stu.edu.cn | 男 | 外国语学院 | 2 | 日语 | 无 |
| 0000000027 | 小外07 | demo027@stu.edu.cn | 男 | 外国语学院 | 3 | 英语 | 无 |
| 0000000028 | 小外08 | demo028@stu.edu.cn | 男 | 外国语学院 | 4 | 日语 | 无 |
| 0000000029 | 小外09 | demo029@stu.edu.cn | 男 | 外国语学院 | 1 | 英语 | 无 |
| 0000000030 | 小外10 | demo030@stu.edu.cn | 男 | 外国语学院 | 2 | 日语 | 无 |
| 0000000031 | 小外11 | demo031@stu.edu.cn | 女 | 外国语学院 | 3 | 英语 | #2 房主 |
| 0000000032 | 小外12 | demo032@stu.edu.cn | 女 | 外国语学院 | 4 | 日语 | #2 |
| 0000000033 | 小外13 | demo033@stu.edu.cn | 女 | 外国语学院 | 1 | 英语 | #2 |
| 0000000034 | 小外14 | demo034@stu.edu.cn | 女 | 外国语学院 | 2 | 日语 | #6 历史房主（解散） |
| 0000000035 | 小外15 | demo035@stu.edu.cn | 女 | 外国语学院 | 3 | 英语 | #6（解散） |
| 0000000036 | 小外16 | demo036@stu.edu.cn | 女 | 外国语学院 | 4 | 日语 | 无 |
| 0000000037 | 小外17 | demo037@stu.edu.cn | 女 | 外国语学院 | 1 | 英语 | 无 |
| 0000000038 | 小外18 | demo038@stu.edu.cn | 女 | 外国语学院 | 2 | 日语 | 无 |
| 0000000039 | 小外19 | demo039@stu.edu.cn | 女 | 外国语学院 | 3 | 英语 | 无 |
| 0000000040 | 小外20 | demo040@stu.edu.cn | 女 | 外国语学院 | 4 | 日语 | 无 |

> `grade` 校验：每院 1–4 年级各 5 人；`major` 每院两专业各 10 人。

## 4. 寝室矩阵（6 间）

| # | code | 学院/性别 | 容量 | 状态 | member_count | 成员（角色/成员状态） | 标题 | 标签（≤8） | 时间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 100000001 | 计算机/男 | 4 | RECRUITING | 2 | 小算01 OWNER/ACTIVE、小算02 MEMBER/ACTIVE | 小算01的寝室 | 早睡早起、自习搭子 | created now-10d |
| 2 | 100000002 | 外国语/女 | 6 | RECRUITING | 3 | 小外11 OWNER、小外12、小外13 | 小外11的寝室 | 阅读、咖啡续命、安静独处 | created now-14d |
| 3 | 100000003 | 计算机/男 | 4 | FULL | 4 | 小算03 OWNER、04、05、06 | 小算03的寝室 | 健身、早起学习、食堂党 | created now-25d |
| 4 | 100000004 | 外国语/男 | 4 | LOCKED | 3 | 小外01 OWNER、02、03 | 小外01的寝室 | 二次元、电影迷、奶茶党 | created now-5d；锁定 now-2d |
| 5 | 100000005 | 计算机/女 | 6 | ARCHIVED | 6（快照） | 小算11 OWNER（历史）、12–16；全部 `ARCHIVED` | 小算11的寝室 | 猫派、阅读、物品归位 | created now-45d；archived now-30d |
| 6 | 100000006 | 外国语/女 | 2 | DISSOLVED | 0 | 小外14（历史房主）、15；`LEFT/DISSOLVED` | 小外14的寝室 | 音乐现场、摄影 | created now-40d；dissolved now-20d；archived_at=dissolved_at |

要点：

- **#5 归档成员**：`RoomMember.status=ARCHIVED`、`reason=ARCHIVED`、`left_at=now-30d`；不占一人一寝名额（R-16），不能重进 #5（R-13），可进入/创建其他房间。
- **#6 解散**：`room.member_count=0`、`status=DISSOLVED`、`archived_at=dissolved_at=now-20d`；成员 `LEFT/DISSOLVED`；03 §11 已对齐为 `0/2 DISSOLVED`（容量 2、历史成员 2 人，当前计数为 0，02 §4 规定解散时归零）。
- 每间非终态房恰 1 个 ACTIVE OWNER；`member_count == count(ACTIVE)`。
- #4 LOCKED：`member_count=3 < capacity=4`，满足“LOCKED 必未满”。
- 标签为成员标签并集去重后取前 8（按 TAG_ORDER），保证 ≤8。

## 5. 请求矩阵（8 条 = 每院 4 条，各状态 1 条）

| # | 学院 | 类型 | 发起 → 目标 | 容量 | 状态 | 房间 | 时间 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 计算机 | INVITE | 小算01 → 小算02 | 4 | CONFIRMED | #1 | created now-10d；shared now-10d；双方 confirm now-10d/now-9d；expires NULL | #1 由这条请求建立 |
| 2 | 计算机 | INVITE | 小算17 → 小算18 | 4 | CONFIRMING | NULL | created now-2d；shared now-2d；发起方 confirm now-1d；expires now+24h | 待目标确认 |
| 3 | 计算机 | INVITE | 小算19 → 小算20 | 6 | CONTACT_SHARED | NULL | created now-3d；shared now-3d；expires now+4d | 已解锁联系方式 |
| 4 | 计算机 | INVITE | 小算11 → 小算12 | 4 | PENDING | NULL | created now-1h；expires now+48h | 归档用户仍可发起（无 ACTIVE 寝） |
| 5 | 外国语 | INVITE | 小外11 → 小外12 | 6 | CONFIRMED | #2 | created now-14d；shared now-14d；双方 confirm now-14d/now-13d；expires NULL | #2 由这条请求建立 |
| 6 | 外国语 | INVITE | 小外16 → 小外17 | 4 | CONFIRMING | NULL | created now-2d；shared now-2d；发起方 confirm now-1d；expires now+24h | 待目标确认 |
| 7 | 外国语 | INVITE | 小外18 → 小外19 | 2 | CONTACT_SHARED | NULL | created now-6d；shared now-6d；expires now+1d | 7 天有效期临近 |
| 8 | 外国语 | INVITE | 小外04 → 小外05 | 4 | PENDING | NULL | created now-1h；expires now+48h | 双方自由用户 |

文案（`message`，均 ≤200 字）：

| # | message |
| --- | --- |
| 1 | 我们作息和整洁习惯都挺接近，想一起组个 4 人寝。 |
| 2 | 看了你的作息和标签，感觉挺合拍，想聊聊看。 |
| 3 | 我比较安静、爱整理，想找同样早睡的室友。 |
| 4 | 想了解一下你的作息，方便的话聊聊？ |
| 5 | 同学院同作息，想一起把寝室定下来。 |
| 6 | 你列表里也选了早起，想认识一下。 |
| 7 | 喜欢阅读和咖啡，想找安静的室友。 |
| 8 | 我作息规律、爱干净，想先聊聊。 |

校验：

- 所有 `initiator` 与 `target` 同院同性别；目标无 ACTIVE 寝（02 §4 候选规则）。
- 每人同时 open（PENDING/CONTACT_SHARED/CONFIRMING）≤3；每 24h 发起 ≤10（此处最多 1 条）。
- 无“同一对两条 open”；`CONFIRMED` 两条的双方恰好是 #1/#2 的 ACTIVE 成员。
- `contact_shared_at` 严格早于 `expires_at`；`target_confirm_at` 仅 CONFIRMED 有值。
- `capacity_pref` 与建寝容量一致（#1=4、#2=6）。

## 6. 转让矩阵（2 条）

| # | 房间 | from_owner → to_member | 状态 | created | expires | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | #1 | 小算01 → 小算02 | PENDING | now-1h | created+24h（≈now+23h） | 目标为 ACTIVE MEMBER；不解锁联系方式 |
| 2 | #2 | 小外11 → 小外12 | EXPIRED | now-2d | created+24h（< now） | 过期不改 owner；目标与原房主不变 |

## 7. 通知

### 7.1 覆盖类型（≥10 种，12 种）

| 类型 | 来源事件 | 收件人 | 条数 |
| --- | --- | --- | --- |
| `CONNECTION_RECEIVED` | 8 条请求创建 | 各 target | 8 |
| `CONTACT_SHARED` | 6 条非 PENDING 请求被同意 | 各 initiator | 6 |
| `CONFIRM_PENDING` | 2 条 CONFIRMING | 未确认方 | 2 |
| `CONFIRMED` | 2 条 CONFIRMED | 双方 | 4 |
| `ROOM_FULL` | #3 满员 | #3 全体 4 人 | 4 |
| `ROOM_LOCKED` | #4 锁定 | #4 全体 3 人 | 3 |
| `ROOM_ARCHIVED` | #5 归档 | 全体 6 人 | 6 |
| `ROOM_DISSOLVED` | #6 解散 | 全体 2 人 | 2 |
| `TRANSFER_RECEIVED` | 转让 #1 | 小算02 | 1 |
| `TRANSFER_EXPIRED` | 转让 #2 | 小外11 | 1 |
| `MEMBER_JOINED` | #2 加入 12、13 | 既有成员（11；11+12） | 3 |
| `WINDOW_CLOSING` | 时间窗 7 天提醒（days=7） | 每院全体 | 40 |

合计约 80 条；每用户 0–5 条（WINDOW_CLOSING 占 1 条，其余按事件最多 4 条）。若某用户将超过 5 条，按 §7.3 跳过并计入 `skipped_notifications`。当前 seed 实际 79 条：小外11 的第 6 条 `WINDOW_CLOSING` 被上限跳过，`skipped=1`，12 类覆盖不受影响。

### 7.2 已读/未读混合

- 规则：事件时间早于 `now-7d` 的通知 → 已读（`read_at = created_at + 1h`）；其余未读。
- 保证至少 10 个用户同时有已读与未读；`小算09`、`小算10`、`小算01` 各至少有 1 条未读，便于演示角标。

### 7.3 上限与去重

- 每用户 ≤5 条；溢出时按事件时间从旧到新跳过，记录 `skipped_notifications`。
- `WINDOW_CLOSING` 去重键 = `(college, days)`；seed 写 `days=7`，若同日 cron 已写则跳过（写入前查询）。
- `title` 必须按 03 §9 模板；`payload` 键必须是 03 §9 允许的键，禁止联系方式。
- 通知与业务数据同一事务；seed 失败时一起回滚。

## 8. 时间窗 / 邀请码 / 举报 / 拉黑 / 审计

- 时间窗：两院各 1 条，`start_at=now-1d 00:00`、`end_at=now+7d 23:59`，写操作全部开放；`seed_demo` 每次重建都相对当次 `now`，避免窗口过期。
- 邀请码：`COHAB2026`，`max_uses=0`，`used_count=0`，`expires_at=now+30d`，`is_active=True`。
- 举报：见 §2.11（1 OPEN + 1 RESOLVED）。
- 拉黑：见 §2.12（2 对互拉黑）。拉黑对不得出现在任何 open 请求中（当前选择不含）。
- 审计：见 §2.13；`AuditLog.meta` 只放编号/昵称/状态，不放 contact。

## 9. 画像填充规格

### 9.1 六个 cohort（按学院内序号 `n` 轮转：`cohort = ((n-1) % 6) + 1`）

| cohort | 名称 | hard_answers（11 项） | soft_answers（6 项） |
| --- | --- | --- | --- |
| C1 | 早睡整洁安静 | smoke=no, sleep_time=23_00, wake_time=7_8, late_return=rarely, snore=no, pet=no_pet, visitor_freq=never, alcohol=never, game_noise=never, ac_temp=medium, clean_freq=daily | clean=5, social=2, noise=4, boundary=4, spend=3, sleep_regular=5 |
| C2 | 夜猫子 | smoke=no, sleep_time=00_01, wake_time=8_9, late_return=sometimes, snore=mild, pet=ok, visitor_freq=sometimes, alcohol=social, game_noise=sometimes, ac_temp=warm, clean_freq=weekly | clean=2, social=4, noise=2, boundary=2, spend=2, sleep_regular=2 |
| C3 | 均衡型 | smoke=no, sleep_time=23_00, wake_time=7_8, late_return=rarely, snore=no, pet=ok, visitor_freq=rarely, alcohol=never, game_noise=headphones, ac_temp=medium, clean_freq=2_3_week | clean=4, social=3, noise=4, boundary=4, spend=3, sleep_regular=4 |
| C4 | 社交活跃 | smoke=no, sleep_time=00_01, wake_time=8_9, late_return=sometimes, snore=no, pet=ok, visitor_freq=often, alcohol=social, game_noise=sometimes, ac_temp=medium, clean_freq=2_3_week | clean=3, social=5, noise=2, boundary=2, spend=4, sleep_regular=3 |
| C5 | 高整洁 | smoke=no, sleep_time=23_00, wake_time=7_8, late_return=rarely, snore=no, pet=no_pet, visitor_freq=rarely, alcohol=never, game_noise=headphones, ac_temp=cool, clean_freq=daily | clean=5, social=2, noise=5, boundary=5, spend=2, sleep_regular=4 |
| C6 | 边界清晰 | smoke=no, sleep_time=23_00, wake_time=7_8, late_return=rarely, snore=no, pet=ok, visitor_freq=rarely, alcohol=never, game_noise=never, ac_temp=medium, clean_freq=2_3_week | clean=4, social=3, noise=4, boundary=5, spend=3, sleep_regular=4 |

### 9.2 覆盖要求

| 要求 | 落实 |
| --- | --- |
| 40 人全部 `completeness=100` | 11 hard + 6 soft + red_lines_confirmed=true + 3–6 tags + 2–3 prompts |
| dims 六维 | 由 `recompute_profile` 计算；每维 0–100；抽样预期见 §9.7 |
| 红线样本 ≥6 人覆盖 9 条 | §9.4 |
| 标签样本 ≥10 人覆盖 6 分类 | §9.5（40 人全覆盖六类，≥3 对共享标签） |
| prompt 样本 ≥10 人覆盖 6 key；1 条 100–120 字 | §9.6 |

### 9.3 个性覆盖（演示相关）

| 用户 | 覆盖 |
| --- | --- |
| 小算09（demo009，演示对象） | C1 略调：`clean_freq=2_3_week`、`social=3`（与演示新用户相近但不完全一致，分数约 90–98）；`tags=早睡早起/自习搭子/猫派`；`prompts=P-01/P-03`；`ContactInfo.qq=123456789, show_qq=True` |
| 小算10（demo010，冲突演示） | C3 但 `smoke=yes`（`boundary` 略降）；`tags=夜猫子/游戏搭子/奶茶党`；`ContactInfo` 全空 |
| 小算01（寝室 #1 房主） | C3；`tags=早睡早起/自习搭子/整理`；`qq=100000001, show_qq=True`；`prompts=P-02/P-03` |
| 小外11（寝室 #2 房主） | C3；`tags=阅读/咖啡续命/安静独处`；`qq=100000011, show_qq=True` |
| 小算18（长 prompt） | `prompts` 含 P-03，文本长度 100–120 字（见 §9.6） |
| 小外16、小外17 | `red_lines` 覆盖 snore/pet/visitor_freq/alcohol（§9.4） |

### 9.4 红线覆盖（6 人覆盖 9 条）

| 用户 | red_lines |
| --- | --- |
| 小算09 | smoke |
| 小算10 | late_return, game_noise |
| 小算17 | snore, pet |
| 小算18 | visitor_freq, alcohol |
| 小外04 | ac_dc, clean_low |
| 小外16 | smoke, visitor_freq |

并集 = 9 条；全部 `red_lines_confirmed=True`；未列出用户 `red_lines=[]`。

### 9.5 标签分配

| cohort | 标签（3–4 个，含六类覆盖） |
| --- | --- |
| C1 | 早睡早起、自习搭子、猫派 |
| C2 | 夜猫子、游戏搭子、奶茶党 |
| C3 | 阅读、食堂党、物品归位 |
| C4 | 社牛、喜欢聚餐、一起运动 |
| C5 | 洁癖、随手收拾、需要私人空间 |
| C6 | 安静独处、耳机党、电影迷 |

补充：每院序号 1、7、13、19 追加一个情绪/生活标签（如 `咖啡续命`、`健身`、`徒步`、`摄影`），保证每人 3–4 个、≤8。覆盖校验：六类（作息/整洁/社交/兴趣/生活/边界）各有 ≥10 人；≥3 对用户共享 ≥2 个标签（C1、C3 人群天然满足）。

### 9.6 Prompt 分配（6 key，每人 2–3 条）

| key | 示例文本（演示用，可复用） |
| --- | --- |
| P-01 weekend | 周末我更愿意在图书馆待一天，晚上回来打两把游戏。 |
| P-02 small_thing | 关于我的一件小事：我习惯把第二天要穿的衣服提前放好。 |
| P-03 vibe | 理想的寝室氛围是安静、干净、互相报备，晚上十一点后不外放。 |
| P-04 cannot_accept | 我最不能接受室友在室内吸烟，以及不打招呼带人回来过夜。 |
| P-05 visitor_expect | 如果室友带朋友回来，我希望提前半天说一声，尽量在公共区域。 |
| P-06 sleep_summary | 用一句话介绍我的作息：十一点前睡、七点半起，周末会补觉。 |

分配规则：`prompts = [PROMPT_ORDER[i % 6], PROMPT_ORDER[(i+2) % 6]]`；i 为全院序号（0 起），每人 2 条；序号 3/9/15 追加第 3 条（`PROMPT_ORDER[(i+4)%6]`）。`小算18` 的 P-03 使用**长文本**（107 字，QA 按 100–120 校验）：

> 理想的寝室氛围是安静、干净、互相报备。晚上十一点后不外放，带朋友回来提前半天说一声；公共区域轮流打扫，谁的东西谁收拾。遇到作息冲突先商量，不冷战，也不在群里阴阳怪气。周末可以一起做饭，但别把公共区域当成自己的房间。

### 9.7 dims 抽样预期（用于自检，不硬编码）

| 用户 | cohort | sleep | clean | social | noise | boundary | spend |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 小算09 | C1 调 | ≈92 | ≈91 | ≈50 | ≈83 | ≈73 | 50 |
| 小算10 | C3 调（smoke=yes） | ≈74 | ≈74 | 50 | ≈80 | ≈65 | 50 |
| 小算01 | C3 | ≈74 | ≈74 | 50 | ≈80 | ≈75 | 50 |
| 小外11 | C3 | ≈74 | ≈74 | 50 | ≈80 | ≈75 | 50 |

> 数值由 03 §8 公式与 §9.1 取值推算，允许 ±1 舍入；QA 以“公式实现一致 + 分值有序（C1 与小算09 最高、小算10 冲突最低）”为准，不逐位比对。

## 10. 不变量与自检断言（事务提交前执行）

| # | 断言 | 期望 |
| --- | --- | --- |
| I-01 | `User` 学生数 / 管理员数 | 40 / 1；邮箱唯一；uid 唯一且长度 10 |
| I-02 | 每用户 ACTIVE `RoomMember` 数 | ≤1；40 个学生中 12 人（#1 2 + #2 3 + #3 4 + #4 3）在非终态房间，其余 28 人无 ACTIVE 寝（含 #5 归档 6 人、#6 解散 2 人） |
| I-03 | 非终态房间 `member_count` | 等于 ACTIVE 成员数；#1=2、#2=3、#3=4、#4=3 |
| I-04 | `ARCHIVED` #5 | `member_count=6`；成员全 `ARCHIVED`；无 ACTIVE 成员 |
| I-05 | `DISSOLVED` #6 | `member_count=0`；成员全 `LEFT/DISSOLVED`；`dissolved_at` 非空 |
| I-06 | 每非终态房 ACTIVE OWNER 数 | 恰好 1 |
| I-07 | 寝室 code | 6 个，唯一，`^[0-9]{9}$`，固定 100000001–100000006 |
| I-08 | 状态枚举 | `RECRUITING`×2、`FULL`×1、`LOCKED`×1、`ARCHIVED`×1、`DISSOLVED`×1 |
| I-09 | 请求总数/状态 | 8；PENDING 2、CONTACT_SHARED 2、CONFIRMING 2、CONFIRMED 2 |
| I-10 | 每院请求数 | 4 / 4 |
| I-11 | 同一对 open 请求 | 0 条重复；`initiator` 在途 ≤3；24h 发起 ≤10 |
| I-12 | CONFIRMED 成员一致性 | #1 双方 ∈ #1 ACTIVE 成员；#2 同理 |
| I-13 | 请求时间字段 | PENDING `expires≈+48h`；CONTACT_SHARED `expires≈shared+7d`；CONFIRMING 有 `initiator_confirm_at` 且 `target_confirm_at IS NULL`；CONFIRMED 双方 confirm 非空 |
| I-14 | 转让 | 2 条；PENDING 目标为 ACTIVE MEMBER；EXPIRED `expires_at < now`；owner 未被改动 |
| I-15 | 通知 | 每用户 ≤5；全部用户为种子用户；类型 ≥10；payload 不含 `qq/wechat/phone/contact/email/token`（正则扫描） |
| I-16 | 画像 | 40 条 `completeness=100`；hard 11 key、soft 6 key、tags 3–8、prompts 2–3；`red_lines_confirmed=True` |
| I-17 | dims | 6 key、整数 0–100；与服务端纯函数重算一致（允许客户端不传） |
| I-18 | 时间窗 | 2 条，`college` 唯一，`start_at < end_at`，覆盖 now |
| I-19 | 邀请码 | `COHAB2026`，`max_uses=0`，`is_active=True` |
| I-20 | 举报/拉黑 | 2 条举报（OPEN/RESOLVED 各 1）；2 对互拉黑 4 行；`target_id` 为内部 id |
| I-21 | 隐私 | 通知/审计/错误字符串中无联系方式；`ContactInfo` 的 `phone` 全空 |
| I-22 | 非种子数据 | `--reset` 前后非种子 User/Room 计数不变 |

失败处理：任一断言失败 → 抛出 `CommandError` 并回滚，退出码 1；日志只打印断言 # 与计数，不打印 PII。

## 11. 演示账号表（与 [07 演示脚本](07-演示脚本.md) 对齐）

| 账号 | 密码 | 用途 | 关键前提 |
| --- | --- | --- | --- |
| `demo041@stu.edu.cn` | `Cohabit2026!`（现场注册自定） | 演示注册/问卷/匹配 | 不写入 seed；彩排残留需删除或换 042。注意 Django 密码相似校验：`Demo1234!` 对新邮箱 `demo041.*` 可能被判“与邮箱相似”，现场用 `Cohabit2026!` |
| `demo009@stu.edu.cn`（小算09） | `Demo1234!` | 被邀请对象 / 演示匹配最高分 | 画像 100、无寝、`qq=123456789`、`show_qq=True` |
| `demo010@stu.edu.cn`（小算10） | `Demo1234!` | 红线冲突候选 | 画像 100、无寝、`smoke=yes` |
| `demo001@stu.edu.cn`（小算01） | `Demo1234!` | 房主对照 / 广场寝室 #1 | #1 房主、`RECRUITING 2/4` |
| `admin@cohabit.local` | `Admin1234!` | 备用管理端 | `role=ADMIN`、`is_staff=True` |

> 演示新用户 A 的建议答案（与 07 一致）：smoke=no、sleep_time=23_00、wake_time=7_8、late_return=rarely、snore=no、pet=ok、visitor_freq=rarely、alcohol=never、game_noise=headphones、ac_temp=medium、clean_freq=2_3_week；soft clean=4/social=2/noise=4/boundary=4/spend=3/sleep_regular=4；red_lines=[smoke]；tags=早睡早起/自习搭子/猫派；prompts=P-01/P-03。

## 12. 输出与 reset 行为

### 12.1 成功输出样例

```text
seed_demo: ok
  users=41 (students=40, admin=1)
  profiles=40 (completeness=100 all)
  contact_infos=40 (with_qq=4)
  rooms=6 (RECRUITING=2 FULL=1 LOCKED=1 ARCHIVED=1 DISSOLVED=1)
  room_members=20 (ACTIVE=12 ARCHIVED=6 LEFT=2)
  requests=8 (PENDING=2 CONTACT_SHARED=2 CONFIRMING=2 CONFIRMED=2)
  transfers=2 (PENDING=1 EXPIRED=1)
  notifications=79 (read=23 unread=56; types=12; skipped=1)
  windows=2 invite_codes=1 reports=2 blocks=4 audits=10
  elapsed=7.2s
```

> 数字可有 ±2 偏差（通知跳过/审计抽样），但 `users/rooms/requests/transfers/windows/reports/blocks` 必须与上表一致；QA 以 §10 断言为准。`elapsed` 随机器/数据库状态变化，2026-11-15 本机实测 7.2–7.3s（隔离库）与 10.1s（首次迁移后冷库）。

### 12.2 `--reset` 幂等

- 连续执行两次 `--reset`：第二次输出与第一次除 `elapsed`/`now` 偏移外一致；对象计数相同。
- 不带 `--reset` 再执行：退出码 2，不产生任何写入。
- 种子删除后重跑：uid 与 room code 完全一致（固定表）。

## 13. P1 交接清单

- [ ] 命令位于 `backend/apps/<app>/management/commands/seed_demo.py`（app 由 P1 定，建议 `adminops` 或 `profiles`），用 `BaseCommand`。
- [ ] 复用服务端 `recompute_profile`（同一纯函数），不复制公式。
- [ ] 所有枚举值引用 03 的常量（HARD_KEYS/SOFT_KEYS/TAG_ORDER/PROMPT_ORDER/RED_LINE 映射），不写字面量散落。
- [ ] `--reset` 删除范围严格按 §1.4；提供 `--dry-run`（可选）只打印计数。
- [ ] 事务包裹 + §10 断言 + 失败回滚 + 退出码（0/1/2）。
- [ ] 不打印密码/联系方式；日志只打印计数。
- [ ] 与 P2 对齐通知事件时间与 title 模板（03 §9）。
- [ ] 在 README/手册 §9 增加一行用法（需 captain 批准，P5 不改手册）。
- [ ] 自测：`pytest` 中新增 `test_seed_demo`（调用 command，断言 §10 的 I-01…I-22 关键项）。
- [ ] 演示前 `seed_demo --reset` 由 P5 执行并截图计数。

## 14. 与 03 §11 的对照（一致性证明）

| 03 §11 要求 | 本规格 | 位置 |
| --- | --- | --- |
| 40 人、两院各 20、每院 10 男 10 女 | §3 表（40 行） | §3 |
| 昵称小算/小外 01–20、邮箱 demo001–040、密码 Demo1234! | §3 | §3 |
| 管理员 admin@cohabit.local / Admin1234!、role=ADMIN、is_staff | §2.1 | §2.1 |
| uid 10 位固定 0000000001–40 | §2.1、§3 | §2.1 |
| 年级 1–4 且各年级 ≥5 | `((n-1)%4)+1`，每院每年级 5 | §3 |
| 专业：软件工程/计算机科学、英语/日语 | §3 表 | §3 |
| 画像 40 人完整 100、六维、3–6 标签、0–3 红线、2–3 prompt | §9.1–§9.6 | §9 |
| 红线样本 ≥6 人覆盖 9 条 | 6 人覆盖 9 条 | §9.4 |
| prompt 样本 ≥10 人覆盖 6 key、含 100–120 字长文本 | 40 人全覆盖 6 key；小算18 长文本 | §9.6 |
| 标签样本 ≥10 人覆盖 6 分类、≥3 对共享 | C1–C6 全覆盖；C1/C3 多对共享 | §9.5 |
| 空态用新注册账号，不写 seed | demo041 现场注册 | §11 |
| 6 寝（每院 3）：#1 4/2 RECRUITING 男、#2 6/3 RECRUITING 女、#3 4/4 FULL、#4 4/3 LOCKED、#5 6/6 ARCHIVED、#6 0/2 DISSOLVED（历史成员 2） | §4 表 | §4 |
| 非终态每间 1 ACTIVE OWNER；member_count 与 ACTIVE 一致 | §4、I-03、I-06 | §4/§10 |
| 归档/解散保留历史房主、不占名额 | #5/#6 历史 OWNER 行 | §4 |
| 8 请求（每院 4；PENDING 2/CONTACT_SHARED 2/CONFIRMING 2/CONFIRMED 2） | §5 表 | §5 |
| 转让 2（PENDING 1/EXPIRED 1） | §6 | §6 |
| 通知每用户 0–5、混合已读未读、10+ 类型 | §7（12 类，≤5/人） | §7 |
| 时间窗每院 1，昨天 00:00 → +7d 23:59 | §2.9/§8 | §2.9 |
| 邀请码 COHAB2026 max_uses=0 | §2.10 | §2.10 |
| 举报 2（OPEN/RESOLVED） | §2.11 | §2.11 |
| 拉黑 2 对 | §2.12（2 对=4 行） | §2.12 |
| expires 相对 now：PENDING +48h、CONTACT_SHARED 自 shared 起 +7d、CONFIRMING 自首次确认起 +48h | §5 | §5 |
| 不创建违规数据；CONFIRMED 与寝室成员一致 | §5、I-11、I-12 | §5/§10 |
| 通知 payload 无 contact | §2.8、I-15 | §2.8/§10 |
| 命令：DEBUG 守卫、--reset、依赖顺序、recompute、计数输出、失败回滚、不随机、不动非 seed、生产禁止 | §1 | §1 |

### 14.1 已知差异与对齐记录

1. **#6 的 “0/2”**：03 §11 已与 02 §4 对齐，`DISSOLVED` 的 `member_count=0`，历史成员仍为 2 人（`LEFT/DISSOLVED`）；本规格按 0 执行，展示时用“解散前 2 人”。
2. **拉黑“2 对”的口径**：03 未说明按行还是按对；本规格按 2 对互拉黑（4 行）实现并计数。
3. **通知类型数**：03 要求 10+；本规格覆盖 11 类事件型 + 1 类窗口提醒（`WINDOW_CLOSING` 由 seed 直接写入，需与 cron 去重键 `(college, days)` 对齐；若 P2 认为应由 cron 生成，可删除这 40 条并将覆盖类型降为 11）。
4. **03 §9 跳转路径** `/app/connections/{id}`、`/app/rooms/{code}` 与前端实际路由 `/connections`、`/rooms/:code` 不一致；通知 payload 不依赖该路径，前端跳转按实际路由映射（见 06 的说明）。
5. **`expires_at` 可空**：M4 修复后 `ConnectionRequest.expires_at` 允许 `NULL`（迁移 `connections/0002_expires_at_nullable`），仅 `CONFIRMED` 为 `NULL`；PENDING/CONTACT_SHARED/CONFIRMING 必须有值。seed 的 2 条 CONFIRMED 已按此落库，历史 CONFIRMED 数据由迁移清空。

### 14.2 M4 实测记录（2026-11-15）

| 项 | 结果 |
| --- | --- |
| 命令 | `manage.py seed_demo --reset`（开发库）；`migrate` + `seed_demo`（隔离库 `cohabit_m4_qa`） |
| 输出 | users=41 / profiles=40 / contacts=40 / rooms=6 / members=20 / requests=8 / transfers=2 / notifications=79（read23 unread56 types12 skipped1）/ windows=2 / invite=1 / reports=2 / blocks=4 / audits=10 |
| 自检 | §10 I-01..I-22 全通过；CONFIRMED 两行 `expires_at IS NULL` 且 `room_id` 非空；其余状态 `expires_at` 非空 |
| 隔离库 API 验收 | `.walkthrough/qa_m4_api.py` 171 passed / 0 failed / 0 defects（fresh seed 后） |
| 全量测试 | `pytest -q` 544 passed（隔离测试库 `test_cohabit_qa_m4`） |
| 与规格差异 | 仅通知 79 条（第 80 条被每人上限跳过，skip=1），无其他计数差异；`elapsed` 随环境变化 |

### 14.3 M5 实测记录（2026-11-16）

| 项 | 结果 |
| --- | --- |
| 命令 | `migrate` + `seed_demo --reset`（隔离库 `cohabit_m5_qa`，9.1s）；测试库 `test_cohabit_m5_qa` |
| 输出 | users=41 (students=40, admin=1) / profiles=40 (100%) / contact_infos=40 (with_qq=4) / rooms=6 (RECRUITING=2 FULL=1 LOCKED=1 ARCHIVED=1 DISSOLVED=1) / room_members=20 (ACTIVE=12 ARCHIVED=6 LEFT=2) / requests=8 (2/2/2/2) / transfers=2 (PENDING=1 EXPIRED=1) / notifications=79 (read23 unread56 types12 skipped1) / windows=2 / invite_codes=1 / reports=2 / blocks=4 / audits=10 |
| 自检 | §10 I-01..I-22 全通过；与 M4 实测计数逐项一致 |
| 隔离库 API 验收 | `.walkthrough/qa_m5_api.py` **432 checks / 432 passed / 0 failed / 0 defects**（fresh seed；含 W-01..10、R-15..21、T-08、S-06..15、A-11/A-13、FA-08、隐私扫描） |
| 全量测试 | `pytest -q` **704 passed**（252.41s，测试库 `test_cohabit_m5_qa`） |
| M5 数据面校验 | 归档快照 #5：`member_count=6`、6 名 ARCHIVED 成员；`repair_member_count` dry-run 不再重算终态房（drift=0，§S-15）；公开页对 ARCHIVED/DISSOLVED 均 404；CSV 导出不含 email/QQ/微信/手机号/token |
| 与规格差异 | 仅通知 79 条（第 80 条被每人上限跳过，skip=1），无其他计数差异 |
| 运维提示 | 若先建过额外 ADMIN 账号，`seed_demo --reset` 自检 `#I-01 admin != 1` 会失败；先 `manage.py flush --no-input` 再 reset（本轮已按此恢复基线） |

## 15. 变更记录

| 日期 | 版本 | 变更 | 作者 |
| --- | --- | --- | --- |
| 2026-11-15 | v1 | M1 首版：命令契约、字段清单、40 人/6 寝/8 请求矩阵、画像 cohort、通知覆盖、22 条自检断言、03 对照表 | P5 |
| 2026-11-15 | v2 | M4 实测同步：通知 79（skip=1）、CONFIRMED `expires_at NULL`（迁移 0002）、demo041 密码建议改 `Cohabit2026!`、输出 elapsed 实测、新增 §14.2 验收记录 | P5 |
| 2026-11-16 | v3 | M5 实测同步：隔离库 `cohabit_m5_qa` 计数不变；API 432/432、全量 704 passed；新增 §14.3（含归档快照/修复口径与额外 ADMIN 时 flush 提示） | P5 |
