# MEMORY

本文件记录每次验证的输入、期望、实际与失败位置。只记事实，不记结论性评价。
维护规则见 AGENTS.md 第 8 节。

## 2026-11-04 首次搭建验证

环境：Windows，Python 3.13.12，Node 22，SQLite 本地库，CHECKPOINTER=memory。

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| U-01 | 规则引擎 39 岁男性 118/76 BMI22.9 睡眠7.5 运动4 | 总体低风险 | 低风险，非紧急 | 无 |
| U-02 | 收缩压 140 舒张压 90 | 心血管中风险并命中 CV_SBP_140 | 中风险，命中两条 140/90 规则 | 无 |
| U-03 | 收缩压 165 舒张压 102 | 心血管高风险，紧急程度需尽快就医 | 高风险，需尽快就医 | 无 |
| U-04 | BMI 23.9 与 24 与 28 | 低 中 高 三档 | 与预期一致 | 无 |
| U-05 | 睡眠时长缺失 | 睡眠维度信息不足，总体信息不足 | 与预期一致，缺失项列出平均睡眠时长 | 无 |
| U-06 | BMI 29 且心理量表缺失 | 总体仍为高 | 高，未被缺失维度拉低 | 无 |
| U-07 | 计划 6 天 | 校验失败并提示 7 到 30 天 | 失败，错误文案正确 | 无 |
| U-08 | 任务完成标准写"按处方每天 20 毫克" | 校验失败 | 失败，命中禁止表述 | 无 |
| U-09 | 文本"胸痛而且喘不上气" | 命中两条高危规则 | 命中 EM_CHEST_PAIN 与 EM_DYSPNEA | 无 |
| U-10 | 文本"最近睡眠不太好" | 不命中 | 空结果 | 无 |
| U-11 | 文本"体重140斤" | 体重 70 公斤 | 首次抽出 140，正则贪婪导致；修正为拒绝 斤 结尾后为 70 | tests/unit/test_data_collector.py 曾失败 |
| A-01 | 注册后重复注册同名 | 409 AUTH_USER_EXISTS | 符合 | 无 |
| A-02 | 刷新令牌使用两次 | 第二次 401 | 符合；曾因 sqlite 无时区比较报 TypeError，已加 as_utc | backend/app/services/auth_service.py |
| A-03 | 无令牌访问 /assessments | 401 AUTH_UNAUTHORIZED | 符合 | 无 |
| F-01 | 描述一串身体数据后发消息 | 返回 confirmation_required，画像确认 | 符合，systolic_bp 150 进入摘要 | 无 |
| F-02 | 确认画像后恢复 | 生成评估与计划草稿，再次要求确认 | 符合，plan_id 与 version_id 返回 | 无 |
| F-03 | 确认计划后恢复 | run_completed，计划 active，报告落库 | 符合，计划 active，报告 1 份 | 无 |
| F-04 | 同一任务同一天打卡两次 | 返回同一条记录，状态更新 | 符合，第二次 status 改为 partial | 无 |
| F-05 | 用户 B 读取用户 A 的计划 | 404 且不含内容 | 符合 | 无 |
| F-06 | 输入"现在突然胸痛，喘不上气" | 直接紧急提示，不进入普通流程 | 符合，回复含 120 与急诊 | 无 |
| F-07 | 计划确认后访问提醒 | 至少一条今日任务提醒 | 4 条 | 无 |
| M-01 | alembic upgrade head | 建表成功 | 成功；首次生成时 Text 未加前缀导致 NameError，已改 sa.Text | migrations/versions/ebfa31c139b9_initial_schema.py |
| M-02 | downgrade base 后再 upgrade head | 可重复执行 | 成功 | 无 |
| B-01 | 前端 vite build | 构建成功 | 成功，echarts 按需引入后主包体积下降 | 无 |
| B-02 | vue-tsc --noEmit | 无类型错误 | 无输出 | 无 |
| S-01 | uvicorn 启动并访问 / 与 /health/live | 200，返回前端页面 | 符合 | 无 |

汇总：`pytest` 56 项通过，前端类型检查通过，构建通过。

## 2026-11-04 用例按编号重组

把原来混在 `tests/api/test_flow.py` 的流程用例按 docs/impact 的编号拆开，公共流程片段移到 `tests/helpers.py`。

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| NH-02 | 档案填 1990-01-01 女 165 60 | BMI 22.0，版本递增 | 符合 | 无 |
| NH-03 | 只有身高体重后发起评估 | 总体信息不足，不是低风险 | 符合；初版断言写成了中或高，属用例错误 | tests/api/test_features.py 曾失败 |
| NH-03 | 补睡眠运动盐摄入吸烟与收缩压 150 | 总体中或高风险，五维齐全 | 高 | 无 |
| NH-04 | 计划确认后同日打卡两次 | 同一条记录，状态更新为 partial | 符合 | 无 |
| NH-04 | 计划调整一次 | 生成 2 号草稿，1 号保持 active | 符合 | 无 |
| NH-05 | 收缩压 148 132 128 分三天录入 | 趋势 3 点，latest 128，change -20 | 符合；首次三条同一时间戳导致顺序不定 | tests/api/test_features.py 曾失败 |
| NH-05 | 收缩压录入 400 | 422 拒绝 | 符合 | 无 |
| NH-06 | 报告详情与导出 | 含章节与免责说明，导出为 markdown | 符合 | 无 |
| NH-07 | 计划生效后访问提醒 | 至少一条 task_due，标记已读成功 | 符合 | 无 |
| RT-01 | 两次评估后按 page_size 1 翻页 | total 2，两页 id 不同 | 符合 | 无 |
| RT-02 | 调整后比对版本列表与详情 | 两边一致，active 版本等于 current_version_id | 符合 | 无 |
| RT-03 | 生成报告后改体重与腰围 | 历史报告内容不变 | 符合 | 无 |
| RT-04 | 连续访问提醒三次并标记已读 | 条数与 id 不变，read_at 有值 | 符合 | 无 |
| RT-05 | 用户 B 读用户 A 的计划任务报告会话 | 全部 404 RESOURCE_NOT_FOUND | 符合 | 无 |
| RT-05 | 无令牌访问业务接口 | 401 AUTH_UNAUTHORIZED | 符合 | 无 |
| E2E-01 | 注册到画像确认计划确认到报告 | 五维评估 active 计划 assessment 报告 | 符合 | 无 |
| E2E-02 | 计划生效打卡后取周期总结 | 完成数至少 1，完成率大于 0 | 符合 | 无 |
| E2E-03 | 高危文本 | 无 confirmation，含 120 与急诊，无评估与计划 | 符合 | 无 |
| E2E-04 | 两次中断两次恢复 | 评估计划报告各一条，重复确认计划返回 409 | 符合 | 无 |

## 2026-11-04 补 P0 缺口

对照 FDE 1.5.1 与 9.2 的页面清单，补四处未落地的功能。影响分析见 `docs/impact/2026-11-04-completion-gaps.md`。

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| NH-08 | 先授权健康数据处理再撤回 | 两条记录都在，最近一条为 revoked | 符合，标签回填为健康数据处理 | 无 |
| NH-08 | 提交 consent_type 为 ad_targeting | 422 | 符合 | 无 |
| NH-09 | 设备读数 quality_status 为 pending | 不进入评估快照 | 符合 | 无 |
| NH-09 | 设备读数 quality_status 为 verified | 进入评估快照 | 符合 | 无 |
| NH-09 | 单位与指标定义不符 | 构造时报错 | 符合，bpm 与 kg 混用被拒 | 无 |
| NH-10 | 测量时间写成三天后 | 422 INVALID_HEALTH_DATA | 符合；改动前是 500 INTERNAL_ERROR | app/services/tracking_service.py 曾抛裸 ValueError |
| NH-11 | 用错误密码登录 | 写一条审计，结果为 fail | 符合，审计里没有密码 | 无 |
| S-02 | 启动服务访问 / 与 /health/live | 200 | 符合 | 无 |
| S-03 | 登录后取周期总结 | 返回周期、完成率、提示 | 符合，任务 3 项完成 0 | 无 |
| S-04 | 提交身体感受反馈 | 200 并落库 | 符合 | 无 |
| S-05 | 未带令牌访问 /api/v1/plans | 401 | 符合 | 无 |
| B-03 | 前端类型检查与构建 | 无错误 | 通过，ProfileView 产物 13.08 kB | 无 |
| NH-09 | 同一适配器连续拉取两次 | 第二次写入 0 条 | 符合 | 无 |
| B-04 | 顶部提醒入口点击 | 进入健康首页查看未读 | 改动前跳到个人中心，那里没有提醒列表 | frontend/src/layouts/AppLayout.vue |
| M-03 | 初始迁移是否含授权与审计表 | 建表语句齐全 | 符合 | 无 |
| RT-02 | 先生效一份计划再生效第二份 | 旧计划与其版本都不再是 active | 改动前旧计划状态变了但版本仍是 active | app/services/plan_service.py |

汇总：`pytest` 69 项通过。

## 2026-11-04 部署配置

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| D-01 | 解析 docker-compose.yml | 四个服务三个命名卷 | 符合，日志锚点复用正常 | 无 |
| D-02 | 核对 compose 变量与环境示例 | 变量都有声明 | 符合，八个变量齐全 | 无 |
| D-03 | 下载 Docker Desktop 安装包 | 623MB | 六分钟到 13MB，代理限速，已提供续传脚本 | E:\Docker\installer |
| D-04 | 检查安装条件 | 可静默安装 | 当前会话非管理员，wsl.exe 被安全策略拦截 | 未执行安装 |
| D-05 | 核对 compose 变量与环境文件 | 八个变量都能取到 | 改动前 env 带 BOM，`POSTGRES_PASSWORD` 键名被污染 | deployment/.env |
| D-06 | 校验下载到的安装包 | 官方签名有效 | 签名 Valid，签发者 Docker Inc，版本 4.98.0.245422，623748528 字节 | 无 |
| D-07 | 用 ParseFile 解析四个 ps1 | 语法通过 | 报错，文件是无 BOM 的 UTF-8，5.1 按 GBK 解码吃掉了引号 | deployment/scripts |
| D-08 | 单独跑 fetch-installer.ps1 | 已下完时跳过 | 改动前会拿 416 后抛下载失败；curl 进度写 stderr 也会被 Stop 打断 | deployment/scripts/fetch-installer.ps1 |
| D-09 | docker 不在 PATH 时跑 start.ps1 | 明确报错 | 改动前 `$LASTEXITCODE` 为空会被当成成功 | deployment/scripts/start.ps1 |
| D-10 | prod 用默认密钥构造 Settings | 拒绝启动 | 已拦截；dev 与显式密钥两条分支正常 | 无 |
| M-04 | 临时库执行 upgrade head | 28 张表 | 符合，27 张业务表加 alembic_version | 无 |
| M-05 | 同一库执行 downgrade base | 只剩 alembic_version | 符合，无残留表 | 无 |
| M-06 | 降级后再 upgrade head | 可重复升降 | 符合 | 无 |
| M-07 | alembic check 比对模型与迁移 | 无差异 | 输出 No new upgrade operations detected | 无 |
| M-08 | Postgres 上 upgrade head 到 downgrade base 再 upgrade | 可重复升降 | 符合，两个版本依次应用与回滚，重建后 28 张表，check 仍无差异 | 无 |

## 2026-11-05 容器实跑

本机装好 Docker Desktop 4.98.0 之后第一次真起 compose，逐项记录。

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| C-01 | 拉基础镜像 | 四个都下来 | 改动前卡在 `auth.docker.io` 不可达，报 failed to fetch oauth token | 已补 pull-base-images.ps1 |
| C-02 | 构建镜像 | 两阶段都成功 | 符合，npm ci 5 秒，vite 产出 dist，pip 装完 77 秒 | 无 |
| C-03 | 起 redis | 绑定宿主 6379 | 改动前被本机原生 redis-server 占住，报 bind forbidden | 改成只 expose |
| C-04 | 起 backend | 绑定宿主 8080 | 改动前被上一会话遗留的 uvicorn 占住，已停止该进程 | 无 |
| C-05 | Postgres 上跑迁移 | 建出初始 schema | 符合，public 下 32 张表：27 业务表加 alembic_version 加 4 张检查点表 | 无 |
| C-06 | 检查点切 postgres | setup 成功 | 日志输出 checkpointer ready backend=postgres | 无 |
| C-07 | 容器内跑 smoke_check | 全流程通过 | 认证、档案、两段确认、35 个任务的计划、评估、报告、4 条提醒、高危拦截都走通 | 无 |
| C-08 | 校验接口中文 | 正常 UTF-8 | 计划标题 `14天健康管理计划` 长度 9，未被破坏 | 无 |
| C-09 | 越权访问 /health/services | 拒绝 | 普通账号返回 403 需要管理员权限 | 无 |
| C-10 | compose 三容器健康 | 全部 healthy | backend、postgres、redis 都是 healthy | 无 |
| C-11 | 重建镜像后重启 | 新代码生效，冒烟仍通过 | 符合，认证、两段确认、35 个任务、评估、报告、提醒、高危拦截全部走通 | 无 |

## 2026-11-05 资料解析

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| R-01 | 中文检验单文本 | 抽出台账里的指标 | 识别 9 项，总胆固醇不在指标表被忽略 | 无 |
| R-02 | 用 mg/dL 记的血脂血糖 | 换算成 mmol/L | 符合，140 转 7.78，158 转 4.09，42 转 1.09 | 无 |
| R-03 | 数值超出取值区间 | 丢弃 | 心率 999、体重 3、腰围 500 都不出现 | 无 |
| R-04 | 同一编码在两处出现 | 取原文靠前的一条 | 改动前按规则表顺序，尾部历史值会顶掉本次结果，已改成按位置取 | document_parser.parse_text |
| R-05 | 空白 PDF 上传 | 记 unsupported 并说明没有文字层 | 符合 | 无 |
| R-06 | 损坏的 PDF | 记 failed 不抛 500 | 符合 | 无 |
| R-07 | 重复确认同一份资料 | 不产生重复记录 | 首次 applied=2，第二次 applied=0 skipped=2 | 无 |
| R-08 | 确认资料里没有的编码 | 拒绝 | 422 INVALID_HEALTH_DATA | 无 |
| R-09 | 他人文件读识别结果与确认 | 404 | 符合 | 无 |
| R-10 | 容器内 Postgres 实测 | 迁移应用，指标可查 | 迁移 1a2e2622add0 应用成功，趋势接口返回 148 与 7.8 | 无 |

汇总：`pytest` 92 项通过。测试库改成每次运行前删除重建，`init_models` 只建缺失的表，不删库会跑在旧结构上。

## 2026-11-05 计划改期

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| S-01 | 未开始计划推后 3 天 | 起止日期与任务日期一起平移 | 符合，任务最早日期等于新开始日期，最晚不超过新结束日期 | 无 |
| S-02 | 改期后的版本记录 | 任务不变，旧版本置 superseded | 标题集合一致，新版本 active，旧版本 superseded | 无 |
| S-03 | 新开始日期早于今天 | 拒绝 | 422 INVALID_HEALTH_DATA | 无 |
| S-04 | 新开始日期与当前相同 | 拒绝 | 422 | 无 |
| S-05 | 已经开始两天后再改期 | 拒绝并提示逐条调整 | 409，消息含「已经开始」 | 无 |
| S-06 | 当前版本已有打卡再改期 | 拒绝 | 409，消息含「打卡」 | 无 |
| S-07 | 他人计划改期 | 404 | 符合 | 无 |

前端入口在 `PlansView.vue`，按开始日期不早于今天、当前版本任务全未打卡粗判是否显示，最终拦截以后端为准。`vue-tsc --noEmit` 与 `npm run build` 通过。

## 2026-11-05 单任务改期

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| T-01 | 把当天任务挪到明天 | 只改任务日期 | 符合，详情里任务日期变成新值 | 无 |
| T-02 | 提交与当前相同的日期 | 不报错也不重复处理 | 返回 200，日期不变 | 无 |
| T-03 | 改到昨天 | 拒绝 | 422 INVALID_HEALTH_DATA | 无 |
| T-04 | 改到计划结束日之后 | 拒绝 | 422，消息含「周期」 | 无 |
| T-05 | 已打卡任务再改日期 | 拒绝 | 409，消息含「打卡」 | 无 |
| T-06 | 整体改期后动旧版本任务 | 拒绝 | 409，消息含「旧版本」 | 无 |
| T-07 | 改他人任务日期 | 404 | 符合 | 无 |

`patch_task` 先把任务连同计划与版本一次查出，再做归属与版本校验。打卡按 `(task_id, checkin_date)` 唯一，日期挪走会让完成记录对到空日子，所以有打卡直接拒。`pytest` 99 项通过。

## 2026-11-05 任务提醒开关

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| W-01 | 新建计划后的今天任务 | 默认开启提醒并生成当天提醒 | 今天三个任务的 `reminder_enabled` 都是 true，`task_due` 条数与任务数一致 | 无 |
| W-02 | 关掉全部任务的提醒 | 清掉历史后不再生成 | 符合，清空后重新拉取为空 | 无 |
| W-03 | 只把其中一个任务的提醒打开 | 只补这一条 | 符合，条数 1 且 `related_object_id` 是打开的那个任务 | 无 |
| W-04 | 提交 25:00 作为提醒时间 | 拒绝 | 422 | 无 |
| W-05 | 提交 08:30 | 保存成功 | 符合 | 无 |

改动前 `reminder_enabled` 只是列和入参，`reminder_service.sync` 不读，开关等于摆设。现在只挡 `task_due`，计划级的两条提醒不受影响；复制版本沿用原任务的值。本机演示库是老结构，该列默认 false，重建库即可。`pytest` 102 项通过。

## 2026-11-05 重新评估闭环

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| X-01 | 调接口登记重新评估 | 写一条审计 | 改动前调用 `health_repo.audit`，该模块没有这个方法，抛 AttributeError 接口 500 | tracking_service.reassessment_request |
| X-02 | 把用户填的原因写进审计 | 能落库 | 改动前 `result=reason[:120]`，列是 varchar(16)，Postgres 报 value too long for type character varying(16) | 同上 |
| X-03 | 原因不足 2 字 | 拒绝 | 422 | 无 |
| X-04 | 正常登记 | 200 且审计 result 为 requested | 符合，容器 Postgres 上实测写入成功，length 9 | 无 |
| X-05 | 未登录调用 | 401 | 符合 | 无 |
| X-06 | 登记后按当前档案生成新评估 | 200，历史评估与报告不动 | 符合，容器里返回 200 并新写入一条评估，报告列表里前几次的报告都还在 | 无 |

这两个缺陷只在真库上暴露：SQLite 不校验 varchar 长度，`health_repo` 的错误又因为没人调用而潜伏，105 项用例全绿时它们都在。审计的 `result` 只能写 `success`、`fail`、`requested` 这类短词，原因写日志。前端把周期收尾入口接上了，计划结束或只剩两天时出现。

## 2026-11-05 计划状态与取消

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| Y-01 | 取消 active 计划 | 状态变 cancelled | 符合 | 无 |
| Y-02 | 取消后再打卡 | 拒绝 | 409，消息含「不能打卡」 | 无 |
| Y-03 | 已过结束日的计划取消 | 拒绝 | 409，消息含「已结束」 | 无 |
| Y-04 | 取消他人计划 | 404 | 符合 | 无 |

取消逻辑原先写在路由层，这次收进 `plan_service.cancel`，与 `adjust`、`shift` 分层一致，路由里清掉两个已不用的导入。前端把打卡、调整、取消按钮都按计划状态收口：非 active 计划只显示任务与只读标记，避免点了才弹 409。`pytest` 109 项通过。

## 2026-11-05 打卡清理提醒

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| Z-01 | 今天两个任务都有未读提醒，打卡其中一个 | 只有这条变已读 | 符合，另一个仍 read_at 为空 | 无 |
| Z-02 | 打卡后重复访问提醒列表 | read_at 不被改写 | 符合，两次值一致 | 无 |
| Z-03 | 另一个用户的一条未读提醒 | 不被本用户的同步动到 | 符合 | 无 |
| Z-04 | 容器 Postgres 上走完整流程 | 打卡后提醒落库标记 | 符合，两条未读变一条，提醒列表冒烟通过 | 无 |

原来 `sync` 只在生成时看打卡状态，已生成的「今日任务待完成」不会因为任务完成而消失。现在按 `user_id` 加当天去重键精确查未读行标 `read_at`，不删行，提醒页仍可查。首页今日任务也加了直接打卡按钮，打卡后重新拉数据。`pytest` 111 项通过。

## 2026-11-05 提醒中心

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| N-01 | 点顶部「待办提醒」 | 进提醒中心 | 改动前链回首页，未读数只在布局挂载时算一次，标已读不更新 | layouts/AppLayout.vue |
| N-02 | 在三个页面之间标已读 | 顶部数字同步 | 符合，列表与未读数都读同一份 store | 无 |
| N-03 | 布局与首页同时拉提醒 | 只发一次请求 | 符合，`load` 合并同一个 inflight Promise | 无 |
| N-04 | 两个并发 GET /reminders | 都 200 且不重复生成 | 符合，另在 `sync` 的 commit 上兜底 IntegrityError，撞 `dedup_key` 就回滚放弃本次写入 | 无 |
| N-05 | 容器 Postgres 实跑 | 冒烟通过，SPA 路由可达 | 符合，`/reminders` 返回 200 HTML，镜像内包含 RemindersView 与 store 的 chunk | 无 |

新增 `views/RemindersView.vue`、`stores/reminders.ts` 与 `/reminders` 路由。Dashboard 的未读列表与标已读也改走 store，不再自己拉一份。后端只加了并发写入兜底，接口字段没动。`pytest` 112 项通过。

## 2026-11-05 阶段跟踪报告

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| P-01 | 周期还没结束就生成报告 | 拒绝 | 409，消息带结束日期 | 无 |
| P-02 | 结束的周期生成报告 | 200，落总结与报告 | 符合，`report_type=tracking`，三个章节齐全，summary 的 `period_end` 为昨天 | 无 |
| P-03 | 重复点击生成 | 返回同一份 | 符合，report id 相同，`tracking_summaries` 只有一行 | 无 |
| P-04 | 取消的计划生成报告 | 拒绝 | 409 | 无 |
| P-05 | 他人计划生成报告 | 404 | 符合 | 无 |
| P-06 | 导出阶段报告 | 含完成率与任务数 | 符合，Markdown 里出现「任务完成率」 | 无 |
| P-07 | Postgres 上跑新迁移 | 约束建立 | 符合，`a7d3e5c9f1b2` 应用，`alembic check` 无差异，`downgrade -1` 后再 upgrade 正常 | 无 |
| P-08 | 容器内走完整链路 | 未结束 409，结束后 200 | 符合，演示账号实测两次调用同一 id，`tracking_summaries` 落一行 | 无 |

`build_tracking_report` 之前写完零调用，`tracking_summaries` 表建了不写，周期结束没有任何留存物。现在 `POST /plans/{id}/report` 把总结与报告一起落库，计划页收尾区有入口，个人中心的报告列表能回看与导出。`pytest` 117 项通过。

## 2026-11-05 身体感受历史

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| Q-01 | 提交两条感受后拉列表 | 倒序返回两条 | 符合，第二条在前，字段完整 | 无 |
| Q-02 | 把一条记录时间改到 40 天前 | 7 天窗口看不到，90 天窗口看得到 | 符合 | 无 |
| Q-03 | 另一个账号拉列表 | 空列表 | 符合 | 无 |
| Q-04 | 容器 Postgres 上提交并查询 | 两条都返回 | 符合，`days=7` 与 `days=90` 都是两条 | 无 |

原先只有写入没有读取，`feedbacks_between` 定义后零调用。现在 `GET /tracking/feedback` 按天数窗口返回，趋势页底部列出历史，随观察范围刷新。感受不参与风险分级的口径在接口注释与页面文案里都写了。`pytest` 120 项通过。

## 2026-11-05 紧急提示记录

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| V-01 | 该用户两条紧急事件，时间相差一天 | 新的在前 | 符合，第二条是昨天的「胸痛」 | 无 |
| V-02 | 命中规则是对象数组 | 原样带出 | 符合，`matched_rules[0].rule_id` 可读 | 无 |
| V-03 | 另一个账号拉列表 | 空列表 | 符合 | 无 |
| V-04 | 容器 Postgres 上用演示账号拉列表 | 返回真实触发记录 | 符合，8 条，级别都是紧急，`matched_rules` 为 `EM_CHEST_PAIN` 与 `EM_DYSPNEA` | 无 |
| V-05 | 容器内跑冒烟脚本 | 对话触发紧急提示后能查到这条 | 符合，脚本末行输出 `emergency-events 200 8 紧急` | 无 |

`emergency_events` 建表后只写不读，用户被提示过「立刻就医」却查不到任何记录。现在 `GET /profiles/me/emergency-events` 倒序返回最近 20 条，个人中心列出触发原因、时间与级别，并写明这不代表诊断、不改变当时的处置建议。返回体不带 `conversation_id` 与 `run_id`，避免把其他会话标识暴露到个人页。`pytest` 122 项通过。

顺带改了两处过期文案：个人页底部「演示环境使用模拟数据」与事实不符，改成模型不可用时回落到本地规则文案；`AGENTS.md` 里指向不存在的 `src/api/errors.ts`，改成实际存在的 `src/api/client.ts` 并写明前端不按 `code` 分支。

## 2026-11-05 知识来源台账

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| KB-01 | 启动后拉台账列表 | 条数与 knowledge 目录文件数一致 | 符合，8 条 | 无 |
| KB-02 | 查高血压指南那条 | 机构、版本、发布日期、维度都对 | 符合，中国高血压防治指南修订委员会、2024、2024-08-01、cardiovascular | 无 |
| KB-03 | 连续调两次同步 | 第二次不改库 | 符合，返回 0，行数仍是 8 | 无 |
| KB-04 | 未登录访问 | 401 | 符合 | 无 |
| KB-05 | 容器 Postgres 上重建镜像启动 | 台账落库且幂等 | 符合，首次 `knowledge_synced=8`，重启后 `knowledge_synced=0`，表内 8 行 | 无 |
| KB-06 | 报告页查看资料来源 | 列表可展开，字段可读 | 符合，镜像内 `ReportDetailView` chunk 含该区块，接口返回 8 条 | 无 |

`knowledge_sources` 建库时就有，字段与文件 YAML 头几乎一一对应，却一行没写过，报告里的「医学依据」只到标题与版本。现在启动时把文件头同步成台账，按 `source_id` 幂等，文件 sha256 变了才更新，`import_date` 记最近一次实际改动。报告页底部可展开台账，标明每份资料的机构、版本与发布日期。检索通道只多了一个 `load_document` 复用，chunk 结构没变。`pytest` 125 项通过。

## 2026-11-05 调整的确认出口与反馈

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| AD-01 | 调整后看详情 | 有待确认版本，能确认 | 改动前草稿无入口：后端不改 `current_version_id`，前端 `canApprove` 还要求 `pending_review`，确认按钮不出现，`approve()` 传的还是旧版本 | views/PlansView.vue |
| AD-02 | 确认待确认版本 | 版本生效，详情带调整信息 | 符合，`adjustment.status=approved`，`feedback` 为空 | 无 |
| AD-03 | 提交反馈后回读 | 详情带这句话 | 符合 | 无 |
| AD-04 | 同一条记录再提交一次 | 覆盖不追加 | 符合，只剩最后一句 | 无 |
| AD-05 | 对未生效版本提交反馈 | 拒绝 | 409 `RESOURCE_CONFLICT` | 无 |
| AD-06 | 放弃调整草稿 | 只作废这一版，计划仍在跑 | 符合，计划 `active`，`current_version_id` 不变，版本 `cancelled`，记录 `rejected` | 无 |
| AD-07 | 放弃初次计划草稿 | 计划取消 | 符合，计划 `cancelled` | 无 |
| AD-08 | 同一草稿放弃两次 | 拒绝 | 409 | 无 |
| AD-09 | 他人计划提交反馈 | 404 | 符合 | 无 |
| AD-10 | 容器 Postgres 上走完整流程 | 调整、确认、反馈、再调整、放弃 | 符合，`plan_adjustment_records` 两行：`approved` 带反馈，`rejected` 无反馈，两条 `confirmed_at` 都非空 | 无 |

`user_feedback` 之所以一直为空，不是没人写，是依赖的确认动作走不到。现在待确认版本从 `versions` 里找 `status=draft`，不再看计划状态；确认与放弃两个出口都给了，放弃调整不会把整个计划带走。`reject_version` 按来源分流，返回值从 `None` 改成一句结论供提示用，图流程的调用不看返回值所以不受影响。`pytest` 135 项通过。

## 2026-11-05 待确认版本可删任务

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| AF-01 | 调整后看待确认版本 | 返回任务清单 | 改动前 `detail` 只给当前版本任务，前端只能从 `versions` 推测草稿，拿不到草稿任务 | services/plan_service.py::detail |
| AF-02 | 删掉一条待确认任务 | 任务数减一 | 符合，35 条变 34 条 | 无 |
| AF-03 | 删完两条再确认 | 生效版本跟着减少 | 符合，33 条生效，删掉的两条不在其中，`pending_version` 变 null | 无 |
| AF-04 | 删到只剩一条再删 | 拒绝 | 409 `RESOURCE_CONFLICT` | 无 |
| AF-05 | 删已生效版本的任务 | 拒绝 | 409 | 无 |
| AF-06 | 删不存在的任务 | 404 | 符合 | 无 |
| AF-07 | 删他人计划的待确认任务 | 404 | 符合 | 无 |
| AF-08 | 容器 Postgres 上走完整流程 | 删两条后确认 | 符合，35 → 33，返回体 `pending_version` 为 null | 无 |

`adjust` 是原样复制任务，用户写「任务太多想减到两项」也不会有一条任务变少，原因只是记在库里。现在 `detail` 直接返回 `pending_version` 与它的任务清单，待确认视图里可以逐条删，确认后按删除后的结果生效。删的是草稿里的新行，原版本任务与打卡都不动。`pytest` 141 项通过。

## 2026-11-05 指标质量状态单一真相

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| MQ-01 | 设备读数入库后查库 | 列被写入，JSON 里不再有状态 | 改动前列恒 `valid`、状态藏在 `measurement_context`，过滤读 JSON | integrations/wearable.py::ingest |
| MQ-02 | `pending` 设备读数 | 不进评估快照 | 符合，按列判断 | 无 |
| MQ-03 | 手工录入不带状态 | 列写 `valid` | 符合 | 无 |
| MQ-04 | 请求体传非法状态 | 拒绝 | 422 `INVALID_HEALTH_DATA` | 无 |
| MQ-05 | 只改 JSON 不改列 | 不因 JSON 写了 verified 就放行 | 符合，按未核验处理 | 无 |
| MQ-06 | 容器 Postgres 上降级再升级 | 历史行按 JSON 回填到列 | 符合，`pending` 与 `verified` 各自归位，文件列同步改名回填 | 无 |

原来同一个状态存在列与 JSON 两处，列恒 `valid`，过滤读 JSON。谁按列过滤都会把消费级设备的估算值当已验证数据算进风险等级。现在列是唯一真相，`context` 退回纯设备上下文，接口传状态要过校验。迁移 `c4f8a1d6e2b9` 按方言分支回填历史行。`pytest` 153 项通过。

## 2026-11-05 文件准入状态

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| FA-01 | 正常 PDF 上传 | 记通过准入 | 符合，`admission_status=passed` | 无 |
| FA-02 | 文件头不符的 PDF | 拒绝且不落库 | 400 `FILE_REJECTED`，该用户无文件记录 | 无 |
| FA-03 | 历史行 | 从 skipped 回填为 passed | 符合 | 无 |
| FA-04 | 容器实测正常与伪造两种上传 | 与用例一致 | 符合，库里只有通过准入的两行 | 无 |

`scan_status` 固定写 `skipped`，看起来像没检查，其实扩展名、大小、文件头三道校验一直都有。改名为 `admission_status` 并写 `passed`，迁移 `d9b2c7e4a1f3` 同时改默认值与回填。

## 2026-11-05 登录失败聚合为安全事件

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| SI-01 | 连续 4 次错密码 | 不产生事件 | 符合 | 无 |
| SI-02 | 第 5 次错密码 | 产生一条 `login_bruteforce` | 符合，`severity=medium`、`status=open` | 无 |
| SI-03 | 继续错 3 次 | 不新增 | 符合，窗口内只有一条 | 无 |
| SI-04 | 两个账号各自连错 | 各一条互不覆盖 | 符合 | 无 |
| SI-05 | 普通用户访问事件接口 | 403 | 符合 | 无 |
| SI-06 | 管理员访问 | 200 且能读到该条 | 符合 | 无 |
| SI-07 | 容器实测 6 次错密码 | 只落一条 | 符合，改管理员后接口能读到 | 无 |
| SI-08 | 账号含下划线的两组失败 | 各自一条互不覆盖 | 符合，`u_a_b` 与 `uXaXb` 都只各自一条，去重改用 `startswith(..., autoescape=True)` | 无 |

第一次实现时阈值永远触发不了：本次失败的审计还没提交，统计差一条。现在统计前先 `flush`。`security_incidents` 从空壳变成有采集、有查询、有权限边界，且没有把越权 404 这种噪声拉进来。`pytest` 153 项通过。

## 2026-11-05 前端测试骨架

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| FT-01 | 已登录请求 `/conversations` | 头带 `Bearer a1`，返回 envelope 的 `data` | 符合 | 无 |
| FT-02 | 带令牌请求遇 401 | 刷新一次并重放原请求，共 3 次 fetch | 符合，令牌更新为 new，`/profiles/me` 出现两次 | 无 |
| FT-03 | 401 且刷新接口也 401 | 清空令牌并抛原请求错误，不重放 | 符合，2 次 fetch | 无 |
| FT-04 | 刷新成功但重放后再 401 | 不再刷新，直接抛错 | 符合，3 次 fetch 终止 | 无 |
| FT-05 | `retry: false` 遇 401 | 不尝试刷新 | 符合，1 次 fetch | 无 |
| FT-06 | 409 `RESOURCE_CONFLICT` | 错误码、状态、消息、detail 原样带出 | 符合 | 无 |
| FT-07 | 502 且响应体不是 JSON | 兜底 `INTERNAL_ERROR` 与「请求失败 502」 | 符合 | 无 |
| FT-08 | 两个页面同时调 `store.load()` | 只发一次请求，两者都拿到同一批数据 | 符合，`list` 调用 1 次，`loading` 期间为 true | 无 |
| FT-09 | 连续两次 `load()` | 第二次重新请求，不被 inflight 卡死 | 符合，2 次 | 无 |
| FT-10 | `load()` 失败后再调 | loading 归位，重试成功 | 符合，loading 为 false 后二次加载拿到 1 条 | 无 |
| FT-11 | 三条提醒两条未读，标已读其中一条 | 未读数 2 变 1，列表行 `read_at` 就地更新 | 符合 | 无 |
| FT-12 | 标已读接口报错 | 本地状态不动，异常向上抛 | 符合，未读数仍 2 | 无 |
| FT-13 | 标不存在的 id | 不报错，未读数不变 | 符合 | 无 |
| FT-14 | 两个请求同时收到 401 | 只调一次 `/auth/refresh`，各自重放 | 符合，刷新 1 次、fetch 5 次 | 无 |
| FT-15 | 并发 401 且刷新接口也 401 | 两路都失败，刷新只 1 次且不重放 | 符合，fetch 3 次，令牌清空 | 无 |
| FT-16 | 刷新成功后令牌再次过期 | 能再刷新一次，不被上次的 refreshTask 卡住 | 符合，第二次刷新后令牌为 new-2 | 无 |
| FT-17 | 变异：去掉 `if (!refreshTask)` 去重 | FT-14 与 FT-15 应失败 | 两项均失败，`expected 2 to be 1` | frontend/src/api/client.ts::refreshAccess |
| FT-18 | 变异：`finally` 里不把 `refreshTask` 归零 | FT-16 应失败 | 失败，另有 4 项连带失败 | frontend/src/api/client.ts::refreshAccess |

前端此前只有类型检查与构建两道静态关。`client.ts` 是全站唯一出口，`reminders` 的 `inflight` 合并只写在注释里，两条约束都没有测试守着。初版 spec 用 `tokens.save({...} as never)` 绕过缺字段，等于把「调用方少传字段」这个真实风险静默掉，改成完整 `TokenPayload` 工厂。`reminders` 的 `inflight` 是模块级变量，用例之间会残留，每个用例前 `vi.resetModules()` 重新 import。`npm test` 16 项通过，`vue-tsc` 与 `vite build` 均无变化。

并发刷新这组用例做过变异验证：去掉 `if (!refreshTask)` 去重，FT-14 与 FT-15 均报 `expected 2 to be 1`；把 `finally` 里的 `refreshTask = null` 去掉，FT-16 失败并连带 4 项失败。两处源码改动均已复原，`git diff` 为空。

## 2026-11-05 任务时间可以清空

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| T-08 | 已有时间的任务传 `scheduled_time=null` | 时间被清掉 | 改动前服务端用 `is not None` 判断，null 被当成没传，时间删不掉 | plan_service.patch_task |
| T-09 | 只改提醒开关，请求体不带时间字段 | 时间保持原值 | 符合 | 无 |
| T-10 | 前端把时间输入框清空后保存 | 请求体带 `scheduled_time: null` | 改动前 `editTime.value && ...` 让清空被判成没改，界面提示「日期、时间与提醒都没有变化」 | PlansView.reschedule |
| T-11 | 变异：服务端改回 `is not None` | T-08 应失败 | 失败，清空后仍是 08:30 | plan_service.patch_task |
| T-12 | 变异：前端改回「值非空才算改」 | T-10 对应单测应失败 | 失败，`expected false to be true` | views/planLogic.ts::buildTaskPatch |

任务没有时间表示任意时间，所以「清空」是合法操作。语义改成看字段是否出现：不出现是不改，显式传 null 是去掉。前后端两侧都有同一个坑，前端那句 `editTime.value &&` 和 后端那句 `is not None` 都得换掉，只改一侧会得到「点保存没反应」或者「点了报没变化」。

## 2026-11-05 测试库路径改成绝对路径

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| DB-01 | 从仓库根跑两次 pytest | 第二轮不受上一轮数据影响 | 改动前 `DATABASE_URL` 是 `./test_alwayshealthy.db`，实际落在仓库根；conftest 删的是 `backend/` 下那个，等于没清库，第二轮 `taskmover` 注册报 409，`other.json()['data']` 抛 TypeError | tests/conftest.py |
| DB-02 | 修完连跑两次全量 | 两轮都 156 项通过 | 符合，库文件固定落在 `backend/test_alwayshealthy.db` | 无 |

从 `backend/` 目录跑一直是好的，从仓库根跑才暴露，所以这个坑之前没被发现。凡是写死用户名的用例（`taskmover`、`shifttaker` 等六处）第二轮都会撞唯一键。

## 2026-11-05 计划页判定逻辑抽成纯函数

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| PL-01 | 三天任务乱序到达 | 按日期升序分组，同日内保持原序 | 符合 | 无 |
| PL-02 | 跨月跨年日期 | 仍按时间先后 | 符合 | 无 |
| PL-03 | 结束日与今天同一天 | 剩 0 天 | 符合 | 无 |
| PL-04 | 已结束、跨月、跨年边界 | 天数含负数都算对 | 符合 | 无 |
| PL-05 | 整体改期：draft / completed / cancelled | 一律不可改 | 符合 | 无 |
| PL-06 | 整体改期：开始日期在昨天 | 不可改 | 符合 | 无 |
| PL-07 | 整体改期：当天开始 | 可改 | 符合 | 无 |
| PL-08 | 整体改期：任一任务 completed / partial / skipped | 不可改 | 符合，三种都拦住 | 无 |
| PL-09 | 重新评估：completed 不论剩几天 | 可发起 | 符合 | 无 |
| PL-10 | 重新评估：active 剩 2 天 / 3 天 | 前者可，后者不可 | 符合 | 无 |
| PL-11 | 待确认版本配 draft 计划 | 不算调整草稿 | 符合，否掉会取消计划而不是作废版本 | 无 |
| PL-12 | 三个字段同时改 | 请求体三个字段都带 | 符合 | 无 |

`PlansView.vue` 里六处判定与任务分组原本是内联 computed，模板与逻辑缠在一起，只能靠点页面验。抽到 `views/planLogic.ts` 后由 29 条单测守着，组件只剩取值与渲染。抽的过程里发现 T-10 那个清空时间的缺陷，纯函数化本身就是为了让这种分支能被断言。

## 2026-11-05 CI

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| CI-01 | `pytest -q`，工作目录 `backend` | 156 项通过 | 符合，28.7 秒 | 无 |
| CI-02 | `npm ci`，工作目录 `frontend` | 锁文件与 package.json 一致，装完可跑 | 符合，158 个包 | 无 |
| CI-03 | 干净安装后跑 test / type-check / build | 三条都过 | 符合，45 项、无类型错误、构建 7.6 秒 | 无 |
| CI-04 | PyYAML 解析 `.github/workflows/ci.yml` | 两个 job，步骤顺序正确 | 符合 | 无 |
| CI-05 | 连续 push 两次 | 只跑最后一次 | 靠 `concurrency.cancel-in-progress` 实现，未实测 | 无 |
| CI-06 | 推送后第一次真实运行（run #1，`8125819`） | 两个 job 都绿 | 符合，backend 51 秒、frontend 25 秒，每一步 success | 无 |

测试写完却没人自动跑，等于靠记性。上一轮 conftest 路径那个问题只在「从仓库根连跑两次」时才暴露，人工很少这么跑，所以潜伏到现在。CI 用 Python 3.13（对齐 `backend/Dockerfile` 的 `python:3.13-slim`）与 Node 22（`vitest@5.1.0` 要求 `^22.12.0`）。依赖用 `npm ci` 不用 `npm install`：后者会顺手改锁文件，把锁文件漂移这个信号吞掉。

## 2026-11-05 档案保存没落库

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| PF-01 | PATCH 设职业为「教师」，再用另一个请求 GET | 能读到「教师」 | 改动前读回 None，`patch_profile` 只有 `flush()` 没有 `commit()`，请求结束事务被回滚 | profile_service.patch_profile |
| PF-02 | 清空生日、职业、体重 | 三个字段变 null | 改动前 `elif value is not None` 把显式 null 当没传，接口 200 但值不变 | profile_service.patch_profile |
| PF-03 | 清空生活方式里的睡眠时长 | 该键从 JSON 里消失 | 改动前 `merged.update` 会把老值覆盖成 null，键还留着 | profile_service.patch_profile |
| PF-04 | 只传 sex，不带其他字段 | 职业与睡眠时长保持 | 符合 | 无 |
| PF-05 | 已经是 null 的字段再清一次 | 档案版本不变 | 改动前每次保存都涨一版，因为 lifestyle 恒被当成改动 | profile_service.patch_profile |
| PF-06 | 真实改一个字段 | 版本 +1 | 符合 | 无 |
| PF-07 | 传空的 lifestyle | 版本不变，原值保留 | 符合 | 无 |
| PF-08 | 添加既往史后用另一个请求读 | 能读到该条记录 | 改动前 `add_history` 也只 flush，记录随事务丢弃 | profile_service.add_history |
| PF-09 | 变异：把 `commit()` 改回 `flush()` | PF-01 至 PF-07 应有失败 | 4 项失败，`assert None == '教师'` | profile_service.patch_profile |
| PF-10 | 前端清空某个生活方式项后保存 | 请求体带该键且值为 null | 改动前用 `if (form.value.sleep_hours)` 过滤，空值直接不进请求体 | views/profileLogic.ts::buildProfilePatch |
| PF-11 | 数值填非数字 | 报错提示，不静默清空 | 改动前 `Number('一百七')` 得 NaN，序列化成 null 后被当成清空 | 同上 |
| PF-12 | 变异：lifestyle 只发非空子键 | PF-10 相关断言应失败 | 3 项失败 | views/profileLogic.ts::buildProfilePatch |

会话依赖只 yield 不提交，写操作必须由 service 自己 commit。`profile_service` 是唯一全程零 commit 的 service，其余（plan 13 处、graph 7 处、auth 4 处）都有。前端与后端对「空值」的理解也不一致：前端省略键，后端用 `is not None` 过滤，两边合起来等于清空操作永远无效。`pytest` 166 项通过。

旧用例 `test_nh_03` 开头先写身高 175 体重 88（BMI 28.7）再断言「信息不足」，它一直是绿的，因为那次写入根本没落库。修好提交后 BMI 被正确算成「高」，用例才红。现在改成不预写档案，断言空档案下是信息不足。

## 2026-11-05 业务日期按东八区

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| TZ-01 | `2026-11-04T17:30Z`，即东八区 11-05 01:30 | 业务日期是 11-05 | 改动前前后端都用 UTC 日期，得到 11-04 | DashboardView 今日任务、PlansView today、后端 14 处 `date.today()` |
| TZ-02 | 东八区 23:30 | 仍是当天，不跳到明天 | 符合 | 无 |
| TZ-03 | 不带时区的 naive datetime（sqlite 取回） | 按 UTC 解释，不当本地时间再 +8 | 符合 | 无 |
| TZ-04 | 东五区 `2026-11-05T09:00-05:00` | 换算后是东八区 22:00，仍 11-05 | 符合 | 无 |
| TZ-05 | 前端清空测量时间后提交 | 提示「选择测量时间」 | 改动前 `new Date('').toISOString()` 抛 RangeError，提示里是英文 Invalid time value | TrendsView.submit |
| TZ-06 | 跑在 UTC 的 CI 上跑时区用例 | 仍然证明走东八区 | 用例显式传 +8 偏移，不依赖机器时区 | 无 |

`toISOString()` 是 UTC，`date.today()` 在容器里也是 UTC，两者在凌晨 0 点到 8 点都落后一天。受影响的是今日任务列表、距结束天数、改期最小日期、打卡日期、每日任务提醒。后端换成 `business_today()`（固定 +8，不依赖 tzdata），前端加 `utils/datetime.ts`，测试里 23 处同步换口径。`pytest` 172 项通过。

## 2026-11-05 档案年龄来源

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| AG-01 | 档案无年龄无生日 | 只提示填生日 | 符合 | 无 |
| AG-02 | 有生日 | 显示年龄并注明按生日算 | 符合 | 无 |
| AG-03 | 只有对话里报的年龄（`birth_date` 为空） | 也要显示，并提示补生日 | 改动前表单只编辑 `birth_date`，这个年龄在个人中心完全看不到 | ProfileView 基础信息 |
| AG-04 | GET 档案响应里有没有 `age_years` | 应该有这个键 | 改动前 `ProfileOut` 没有该字段，`get_profile` 传了也被 pydantic 默认的 `extra='ignore'` 静默丢掉，值从来没到过前端 | schemas/health.py::ProfileOut |

`get_profile` 返回的 `age` 是 `age_of(birth_date) or age_years`，两条来源合成一个值，前端靠 `birth_date` 有没有值判断来源即可，不需要后端加字段。没有开放「直接编辑年龄」的入口，避免生日与年龄两个来源打架。

## 2026-11-05 跨零点翻页与输入法回车

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| CD-01 | 23:50 挂载首页 | 日期是当天 | 符合 | 无 |
| CD-02 | 23:59:40 挂载，推到 00:00:10 后走 30 秒 | 日期翻到第二天 | 改动前 `today` 在 setup 时算一次，页面挂着永远不变 | DashboardView 今日任务、PlansView today |
| CD-03 | 08:00 挂载，走 60 秒 | 日期不变 | 符合，值没变就不写入，不触发重渲染 | 无 |
| CD-04 | 两个页面同时用 | 同一份日期，只起一个定时器 | 符合，`vi.getTimerCount()` 为 1 | 无 |
| CD-05 | 依次卸载 | 最后一个卸载后定时器清零 | 符合 | 无 |
| CD-06 | 卸载后改系统时间再挂载 | 立即对齐，不沿用旧值 | 符合 | 无 |
| IME-01 | 中文输入法组字时按回车 | 不发送 | 改动前 `@keydown.enter.exact.prevent` 一样触发，既打断选词又把半截输入发出去 | ChatView 输入框 |
| IME-02 | 普通回车 | 发送 | 符合 | 无 |
| IME-03 | Shift 加回车 | 换行不发送 | 符合 | 无 |

`useToday()` 是模块级单例，三十秒对一次 `localToday()`，另接 `visibilitychange` 对齐（后台标签页定时器会被节流）。引用计数控制启停，第一个挂载启动、最后一个卸载停止。定时器对齐到零点整的收益只有半分钟，没做。

## 2026-11-05 登录态过期与首屏读失败

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| SE-01 | 带令牌 401，`/auth/refresh` 也 401 | 回调调 1 次，两个令牌清空 | 改动前只清令牌不通知，`AppLayout` 的 `ensureUser` 抛出成未处理拒绝，后面的 `reminders.load()` 不执行 | api/client.ts::api、layouts/AppLayout.vue |
| SE-02 | 三个请求同时过期 | 回调只调 1 次 | 改动前一个请求弹一条，布局加页面能叠一屏 | api/client.ts::notifySessionExpired |
| SE-03 | 登录接口自己返回 401（密码错，请求不带令牌） | 回调不调 | 靠 `headers.Authorization` 判断，否则密码错一次就被当成过期、刚填的用户名被冲掉 | LoginView 调用方 |
| SE-04 | 刷新成功但重放仍 401 | 回调调 1 次 | 符合 | 无 |
| SE-05 | 重新登录（`tokens.save`）后再次过期 | 回调能再调，累计 2 次 | 一次性开关在 `tokens.save()` 里复位 | api/client.ts::tokens.save |
| SE-06 | 首页 `Promise.all` 里任一路挂掉 | 弹提示说读失败 | 改动前只有 `finally` 没有 `catch`，页面只剩「还没有评估结果」「还没有指标记录」这类空状态，文案在说「你没填」 | DashboardView.load、TrendsView.load |
| RD-01 | `?redirect=/plans` | 跳 `/plans` | 符合 | 无 |
| RD-02 | `?redirect=//evil.com` | 回首页 | 改动前 `router.push('//evil.com')`，浏览器当协议相对地址跳外站 | LoginView.submit |
| RD-03 | `?redirect=https://evil.com` 或 `javascript:` 开头 | 回首页 | 改动前原样进路由 | 同上 |
| RD-04 | 参数出现多次（vue-router 给数组） | 取第一个 | 改动前 `router.push(数组)` 行为不可预期 | 同上 |

会话过期的通知走回调注册（`setSessionExpiredHandler`），不让 api 层 `import router` 造成环。`stores/auth.ts` 里没人用的 `loggedIn` 一并删掉：它读的是 `localStorage`，不是响应式数据，这个 computed 没有依赖，算一次就永久缓存，真拿来当登录态用会在登录后一直显示未登录。

## 2026-11-05 前后端字段一致性守卫

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| CT-01 | 每个映射过的接口，逐条比 `types.ts` 字段与模型字段 | 前端字段全部存在于模型 | 改动前没人比这一层：`ProfileOut` 漏 `age_years`，pydantic `extra='ignore'` 静默丢掉，tsc 与 pytest 各自都绿 | tests/contract/test_frontend_types.py |
| CT-02 | `types.ts` 新增接口不登记 | 红，提示加进 `MAPPED` 或 `NO_MODEL` | 一开始就抓到被我漏掉的 `ReportSection` | 同上::test_every_interface_is_accounted_for |
| CT-03 | 表里登记的接口已从 `types.ts` 删掉 | 红，提示清表 | 符合 | 同上 |
| CT-04 | 解析出的接口数量 | 大于 20 | 符合，解析器被写法绊住时能发现 | 同上::test_types_file_is_found |
| CT-05 | `GET /profiles/me` | `age_years` 在响应里 | 符合（AG-04 的现场） | 同上::test_profile_response_keys |
| CT-06~10 | feedback / consents / knowledge / plans / assessments 五个 dict 响应 | 键与前端声明一致 | 符合，都加了非空断言，空列表不算通过 | 同上 |

解析器不引 TypeScript 编译器：去行注释、按 `export interface` 定位、大括号配对取 body、只在深度 0 抓 `key:`，泛型接口单列。只比一个方向（前端字段减模型字段为空），后端多给不算问题。变异验证：删 `ProfileOut.age_years`，CT-01 与 CT-05 同时红。`pytest backend` 173 → 205 项。

## 2026-11-05 图表改按需加载

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| CH-01 | 新账号第一次进 `/`，没有任何指标 | 不下载 echarts | 改动前静态引入，跟路由 chunk 一起请求 466.48 kB（gzip 157.25），下完只显示「还没有指标记录」 | DashboardView、TrendsView |
| CH-02 | 有指标时进首页 | 正常出图 | 符合，chunk 在组件挂载时才请求 | 同上 |
| CH-03 | 按需加载的那一瞬间 | 布局不塌 | 外层 `min-h-[260px]` 占位，`v-if` 从组件挪到外层 | 同上 |

首屏 JS 从约 590 kB（gzip 202.6）降到约 129 kB（gzip 50.6）。拆包本身让入口从 115.65 涨到 117.78 外加 2.63 kB 的 API chunk，合计多约 4.8 kB，换来 466 kB 移出首屏。这一层没有自动化覆盖：要真验得用浏览器测试统计首屏请求，当前没这套设施。

## 2026-11-05 确认阶段消息重复

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| CM-01 | 只走到画像确认 | 一条 confirm，以「已记录」开头 | 符合 | 无 |
| CM-02 | 再走到计划确认 | 两条 confirm，内容不同，第二条含「计划」 | 改动前第二条与第一条一字不差：`_stream()` 用 `values["reply"]` 补全，而 plan 这一段 assess/intervene/plan/plan_validator 都不写 reply，拿到的是 data_collector 的旧文案 | app/services/graph_service.py::_stream、_mark_waiting |

两个 `interrupt()` 本来就各自带了阶段 `message`，`_mark_waiting` 一直没用。改成 `fresh_reply or payload["message"]`：本段有新回复用新回复（保住画像阶段的「已记录：…」），没有就用阶段提示。变异验证：改回 `text = reply`，CM-02 红、CM-01 绿。后端 205 → 207 项。

## 2026-11-05 流式请求加固

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| SS-01~06 | 完整帧、半截帧、CRLF、多行 data、无 event、空块 | 切帧结果正确 | 改动前切帧写在 `readStream` 的 while 里，一条都没有单测 | api/stream.ts |
| SS-03 | 上游把分隔符改成 `\r\n\r\n` | 仍能切出事件 | 改动前 `indexOf('\n\n')` 一个都找不到（`\r\n\r\n` 里没有相邻两个 `\n`），整条流零事件、缓冲区涨到流结束 | 同上 |
| SS-09 | 流请求返回 401 | 续期后重放 | 改动前 `postStream` 走裸 fetch，没有 `api()` 那层续期。令牌 120 分钟一过，聊天直接失败，同页其他请求却都正常 | api/stream.ts::postStream |
| SS-10 | 401 且续期失败 | 抛后端中文 message | 改动前 `throw new Error(text)`，`text` 是整个 `{code,message,request_id}` 包，用户气泡里看到一串 JSON | api/stream.ts::readStream |
| SS-12 | 错误体不是 JSON | 退回「请求失败 502」 | 符合 | 无 |

切帧逻辑抽到 `utils/sse.ts`（`splitSseFrames` / `parseSseFrame`），先 CRLF 归一化再切，最后一段不完整的留在 `rest`。`refreshSession()` 从 client 导出复用模块级 `refreshTask`，并发仍只刷一次。变异验证：去掉归一化 SS-03 红，短路 401 分支 SS-09 红。前端 89 → 103 项。端到端在浏览器里跑了一次真实对话（DeepSeek + 真实 SSE），回复完整。顺带给 `TrendsView` 两栏 grid 加 `items-start`，左栏图表卡片不再被右栏撑高。

## 2026-11-05 导航高亮

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| NV-01 | 停在 `/trends` | 只有「趋势」亮 | 改动前首页永远亮着：`router-link-active` 是包含匹配，`/` 是所有路径的前缀 | frontend/src/utils/nav.ts |
| NV-02 | 停在 `/` | 只有首页亮 | 同上，且首页与所在栏目同时亮两个 | 同上 |
| NV-03 | 停在 `/plans/12` | 「计划」亮 | 符合（包含匹配本来对，但不能靠它） | 同上 |
| NV-04 | 停在 `/plansomething` | 计划不亮 | 符合，按 `/` 边界比，不是纯 `startsWith` | 同上 |
| NV-05 | 目标或当前路径带尾斜杠 | 判定不变 | 符合，两边都先裁尾斜杠 | 同上 |
| NV-06 | `route.path` 为空 | 按 `/` 处理 | 符合 | 同上 |
| NV-07 | 停在 `/login` | 一个都不亮 | 符合 | 同上 |

不再用 vue-router 的两个内置类，`isNavActive(currentPath, target)` 自己比：根路径只能精确相等，其余按「相等或 `/` 前缀」判，两边先裁尾斜杠。样式从 `.nav-item.router-link-active` 换成 `.nav-item.is-active`，两处 `RouterLink`（桌面侧栏与移动底栏）都绑 `:class`。变异验证：`isNavActive` 改回 `startsWith`，NV-01 与 NV-04 同时红。前端 103 → 110 项。

## 2026-11-05 流式超时与离开页面中止

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| ST-01 | 服务端连着不吐任何字节 | 45 秒后主动断开并说清原因 | 改动前 `reader.read()` 一直 pending，`fetch` 不会自己结束，页面永远转圈 | api/stream.ts::readWithIdle |
| ST-02 | 每 30 秒来一个事件，累计 60 秒 | 不断，两个事件都收到 | 符合，计时按「距上次收到数据」重置，不是总时长 | 同上 |
| AB-01 | `{name:'AbortError'}` | 认出来 | 符合 | utils/abort.ts |
| AB-02 | 普通 `Error` | 不算取消 | 符合 | 同上 |
| AB-03 | `null` / 字符串 | 不抛，返回 false | 符合 | 同上 |

`ChatView` 里模块级 `controller` 加 `startStream()`：重发与切页都先 `abort()` 掉上一条，否则晚到的 token 会拼进新消息；`onBeforeUnmount` 置 `destroyed` 再 abort，`finally` 里 `refreshMessages()` 加 `if (!destroyed)` 守卫，不在已卸载组件上发请求；`catch` 用 `isAbortError` 过滤，用户自己取消不弹红色提示。`reader.cancel()` 在超时分支里调，别让连接挂着。变异验证：`IDLE_TIMEOUT_MS` 45s 改 90s，ST-01 挂（`Test timed out in 5000ms`），复原。前端 110 → 115 项。

## 2026-11-05 前端可空性守卫

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| NC-01~24 | 每个映射接口，逐字段看模型注解里有没有 `None` | 有的必须在前端声明里允许 null | 一放开就抓到 `EvidenceSource` 的 `source_id`/`title`/`version`：规则引擎给的必填，LLM 拼进来的可能只有 `source_id`，模板里 `source.title` 拿到 null 直接 TypeError | tests/contract/test_frontend_types.py::test_frontend_allows_null_when_model_can |

`_top_level_fields` 从「返回字段名集合」改成「返回 {字段名: (类型文本, 是否可选)}」，顺带把上一次的 CT 用例跟着改。`_allows_none` 用 `get_args` 查 `NoneType`，`Any` 与无注解不算。只做一个方向：模型可为 None → 前端必须允许；反过来前端写得宽松不拦，那是声明保守不是缺陷。`Record<`、`{`、`unknown`、`any` 这类结构性类型跳过。改完 `vue-tsc` 报 `AssessmentView` 的 `:key="source.source_id"` 不接受 null，改成 `source.source_id || index`。后端 207 → 231 项。

## 2026-11-05 测试不再真的调用模型

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| OF-01 | `get_settings().llm_api_key` | 空 | 改动前读到 `backend/.env` 里的真密钥，`GraphDeps.use_llm=True`，整条评估链路都去打 DeepSeek：单用例五次调用、各 1.5~2 秒，一轮 563.10s | tests/conftest.py |
| OF-02 | 无密钥时 `try_complete` | 返回 `None`，不抛 | 符合，所有调用方靠这个约定回落到确定性文案 | app/integrations/llm_client.py |

CI 上一向是绿的、只要 25 秒，因为 `.env` 不入库、密钥为空；本地是唯一例外。`conftest.py` 在导入 `app.*` 之前加 `os.environ["LLM_API_KEY"] = ""`，环境变量优先级高于 `.env`，两边从此走同一条确定性路径。新增 `tests/unit/test_offline.py` 两条守卫：密钥被改回来就红、`try_complete` 的 `None` 约定不能变。本地 563.10s → 33.10s，后端 231 → 233 项。

## 2026-11-05 趋势图改手写 SVG

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| SG-01 | 没有指标点 | 不画空坐标系，给「暂无可画的数据」 | 符合 | components/chartGeometry.ts::buildChart |
| SG-02 | 容器宽度还没量出来 | 不画 | 符合，宽度小于左右留白直接返回空布局，刻度不会挤成一团 | 同上 |
| SG-03 | 混进 `NaN` | 过滤掉，路径里不出现 NaN | 符合，否则整条 `d` 作废、图整个不显示 | 同上 |
| SG-04 | 只有一次测量 | 点落在画布中间 | 符合，否则贴在左边缘看着像渲染坏了 | 同上 |
| SG-05 | 纵轴刻度 | 包住所有数据且首尾在画布内 | 符合，按 1/2/2.5/5/10 取整 | niceDomain |
| SG-06 | 所有值相同 | 纵轴撑开，线不贴底边 | 符合，上下各撑 10% | 同上 |
| SG-07 | 曲线首尾 | 就是第一个和最后一个测量值 | 符合 | smoothPath |
| SG-08 | 相邻两点的曲线 | 控制点不越出两点纵坐标 | 普通 Catmull-Rom 会在尖峰两侧鼓出去，等于画出没测到过的值；改单调三次贝塞尔后符合 | 同上 |
| SG-09 | 30 个点、宽 360 | 横轴标签抽稀到 8 个以内，首尾保留 | 符合，末尾用 `end` 锚点不被裁 | buildXTicks |
| SG-10 | 提示框选点 | 取横坐标最近的点，越界夹到首尾 | 符合 | nearestIndex |

`TrendChart.vue` 只管把数字拼进 SVG，颜色走 `currentColor` + CSS 变量（深浅主题不用在脚本里判断），`ResizeObserver` 跟住容器宽度重算坐标——SVG 不像 canvas 能整体缩放。悬停浮层两处防遮挡：贴左右边向内收，点靠近顶部（y < 64）翻到下方，因为最高点上方正是指标切换栏。删掉 `echarts` 依赖与 `defineAsyncComponent`（几 kB 的组件再拆请求不划算，`min-h` 占位一并删）。图表 466.48 kB（gzip 157.25）→ 5.85 kB（gzip 2.77），首屏 129 → 116.07 kB（gzip 50.6 → 45.43）。前端 115 → 133 项。

## 2026-11-05 契约守卫比类型宽度

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| TC-01~24 | 每个映射接口逐字段比「后端给的 JS 类型 ⊆ 前端声明」 | 装不下就红 | 放开后 24 个全过；唯一失败的 `ProfilePatchBody.lifestyle`（后端 `dict \| None`、前端 `Record<...>`）是请求体方向的假阳性 | tests/contract/test_frontend_types.py::test_frontend_type_width_matches_model |
| TC-25 | `MetricPoint.value` 改成 `string` | 红，报「后端 ['number']，前端写的是 'string'」 | 符合 | 同上 |
| TC-26 | `ProfilePatchBody.height_cm` 改成 `string \| null` | 红，报「前端可能发 ['null','string']，后端只接 ['null','number']」 | 符合 | 同上 |

注解归一到 `string`/`number`/`boolean`/`array`/`object`/`null`：`datetime`、`UUID`、`date` 都算 string，`Literal` 取成员类型，`dict` 与 `BaseModel` 都算 object，看不懂的给通配符不误报。前端按 `|` 拆，`Foo[]`/`Array<Foo>` 算 array，`Record<`/`{` 算 object，`MedicalHistory` 这种命名接口也算 object。响应体方向是「后端 ⊆ 前端」（前端写宽不算错），请求体（`REQUEST_INTERFACES`）反过来。另加两条钉住映射表本身的用例。后端 233 → 259 项。

## 2026-11-05 流式总时长封顶

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| ST-03 | 每 10 秒来一片、永不结束 | 180 秒到点断开并说清原因 | 改动前只有空闲计时，这种流永远不断；现在 `cancel()` 被调用，提示「回复超过 180 秒还没结束，已停止等待」 | api/stream.ts::postStream |
| ST-04 | 5 秒时用户主动 abort | 抛 `AbortError`，不套超时文案 | 符合，否则切页面会莫名弹红字 | 同上 |

`postStream` 自己持一个 `AbortController`，180 秒定时器到点 `abort()`——这样连「等待响应头」的阶段也管住（原来那一段完全没遮拦）。外部信号用 `addEventListener('abort', relayAbort)` 转接，`timedOut` 标记负责区分超时与用户取消。变异：`TOTAL_TIMEOUT_MS` 改 60 秒，ST-03 挂。前端 133 → 135 项。

## 2026-11-05 打包体积进 CI

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| BG-01 | `npm run size`，各项在预算内 | 退出 0，打印剩余余量 | firstLoad 48.7 / totalJs 84.0 / totalCss 4.8 / singleChunk 44.3，各剩 9.3 / 16.0 / 3.2 / 15.7 kB | frontend/scripts/check-bundle-size.mjs |
| BG-02 | 把 `firstLoad` 预算改成 10 kB | 退出 1 并指出超了多少 | 报 `firstLoad: 48.7 kB > 预算 10 kB` | 同上 |
| BG-03 | 单个路由 chunk 重新塞进一个图表库 | 红 | `singleChunk` 红线 60 kB，入口现在 44.3，塞不进 466 kB | bundle-budget.json |

「首屏」按 `dist/index.html` 里直接引用的文件算（entry + modulepreload），路由 chunk 不算——它们要等用户点进去才下。CI 在 build 之后加一步。`--report` 只打印不判，调预算时用。

## 2026-11-05 组件渲染测试起步

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| RT-01 | 空数据 | 显示「暂无可画的数据」，不渲染 `<svg>` | 符合 | components/TrendChart.spec.ts |
| RT-02 | 3 个点 | 3 个 `<circle>`，`path.chart-line` 以 `M … C` 开头 | 符合 | 同上 |
| RT-03 | 容器 400px | `svg[width]` 等于 400，末点贴右侧留白 | 改动前只有几何层用例，没人验宽度有没有真的传进去；变异成写死 640 后这条挂 | 同上 |
| RT-04 | `pointermove` 到中间点再 `pointerleave` | 提示框出现（含日期/数值/单位）后消失 | 符合 | 同上 |
| RT-05 | 鼠标贴最左 | 提示框 `left ≥ 64`，不被容器切掉 | 符合 | 同上 |
| RT-06 | 所有坐标标签 | `y` 落在画布内 | 符合 | 同上 |

`happy-dom` 没有布局也没有 `ResizeObserver`，测试里塞一个 `observe()` 时同步回调 400px 的 stub，组件会走完「实测宽度 → 重算 → 重渲染」整条路，比直接 mock `clientWidth` 更接近真实行为。引了 `@vue/test-utils`。前端 135 → 141 项。

聊天页同日补了 6 条（`views/ChatView.spec.ts`）：CV-01 用户消息先上屏 + token 逐字追加（deferred 卡住流看中间态）、CV-02 `run_error` 弹后端文案、CV-03 `node_progress` 显示后清掉、CV-04 卸载时 `signal.aborted` 变 true、CV-05 主动取消不弹提示、CV-06 普通失败仍要弹（防止把 05 做成「什么都不弹」）。`@/api` 与 `@/api/stream` 用 `vi.hoisted` + `vi.mock` 整体替掉。变异两处（去掉 `isAbortError` 过滤、删掉 `onBeforeUnmount` 的 abort）分别咬住 CV-05 与 CV-04。前端 141 → 147 项。

## 2026-11-05 契约守卫钻到元素层

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| TC-27 | `list[str]` / `list[ProfileOut]` / `dict[str, int]` | 元素分别是 string / object / number | 符合；`list[str \| None]` 与 `dict[str, Any]` 返回 None 表示不比 | tests/contract/test_frontend_types.py::_annotation_element |
| TC-28 | `string[]` / `MetricPoint[]` / `Array<number>` / `Record<string, number>` | 元素分别是 string / object / number / number | 符合 | 同上::_ts_element |
| TC-29 | `Trend.points` 改成 `string[]` | 红 | 报「元素类型后端是 object，前端声明 'string[]' 里是 string」 | 同上::test_frontend_type_width_matches_model |

两边都能定成单一类型时才比，联合与通配符跳过。24 个接口放开后全过，说明现有声明没漂移。后端 259 → 260 项。

## 2026-11-05 工作流自己收口

| 编号 | 输入 | 期望 | 实际 | 失败位置 |
|---|---|---|---|---|
| WT-01 | `astream` 永久挂起，预算 0.05 秒 | 一条 `run_error`（code `WORKFLOW_TIMEOUT`），`_fail` 收到同一码，上游真被取消 | 改动前后端没有任何时间上限：前端 180 秒断的只是浏览器这一侧，run 永远停在 running | app/services/graph_service.py::_stream |
| WT-02 | `astream` 抛 `ValueError` | code 是 `GRAPH_EXECUTION_ERROR`，不能说成超时 | 符合；`TimeoutError` 是 `OSError` 子类，`except TimeoutError` 必须写在 `except Exception` 前面 | 同上 |

`asyncio.timeout(settings.workflow_timeout_seconds)` 包住整个 `astream`，默认 150 秒，必须比前端那 180 秒短——先由后端收口才能把 `workflow_runs.status` 写对。`_fail` 加 `code` 参数区分超时与普通崩溃。`recursion_limit: 30` 只管节点步数，管不住「单个节点卡住」：LLM 单次 45 秒超时加一次重试，最坏一步就接近 90 秒。变异：超时分支的 code 改成 `GRAPH_EXECUTION_ERROR`，WT-01 挂。后端 260 → 262 项。

## 2026-11-05 功能增量：知识库、提醒时间闸、多维对比、报告导出

- **知识库**：从 8 篇扩到 14 篇，补血脂管理、糖尿病日常、心血管预防、减重实操、戒烟限酒、用药依从。都按「YAML 头 + `## ` 分节」与现有语料一致，检索器按 `## ` 切 chunk，每节自足。总 chunk 约 30 → 48。
- **提醒时间闸**：`reminder_service.sync` 的「今日任务待完成」之前一天内任何时候都顶，早上六点会把「晚上十点睡前少屏幕」当待完成催。加 `_time_passed(scheduled_time, now)`，未到点不生成、到点才催，content 带上「（设定时间 xx:xx）」。`timeutil` 加 `business_now()`（东八区时刻）。坏格式时间退回「已到点」不卡链路。
- **多维对比**：`chartGeometry.buildMultiChart` 支持多序列同图，Y 轴按全局 min/max 缩放、各序列独立铺横轴（不做日期对齐）。新增 `MultiTrendChart.vue`（多色 + 图例 + 悬停），`TrendsView` 加「对比」多选模式。
- **报告导出 PDF**：`report_service.to_print_html` 渲染打印友好 HTML（内联样式、`@media print` 防分页断节、HTML 转义防注入），新增 `GET /reports/{id}/print`，前端「导出 PDF」按钮 fetch 后开新窗触发打印。保留原 Markdown 导出。

## 2026-11-06 侧边栏高度与导出/下载链路

- **侧边栏**：`AppLayout` 的 aside 靠 flex stretch 拉到与内容等高（首页 1422px、评估页 1953px），底部按钮跟着内容跑、长页面首屏看不到。加 `lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)] lg:self-start`，两页 aside 都固定 516px、top 24。
- **导出 PDF**：`printPdf` 三处缺陷——`document.write` 同步完成后再监听 `load` 收不到事件（print 永不执行）；`window.open` 放在 `await fetch` 之后被弹窗拦截器挡下；`download` 的 `revokeObjectURL` 同步释放且没 append a 标签（Firefox 下载失败）。
- **下载工具**：两处重复下载逻辑抽成 `utils/download.ts::downloadBlob`，测试 4 条，变异两处咬住。别用 `vi.stubGlobal('URL')`，happy-dom 点 a 标签要 `new URL()`，会炸 TypeError 还假绿。
- **确认卡片**：`ChatView.spec.ts` 补 4 条（弹卡片、approve、reject、modify 反馈门槛）。`.glass-strong` 同时是外层 section 的类名，判断卡片消失要用文案断言。
- **首屏读失败**：`ProfileView.load()` 裸 `Promise.all`、`PlansView.load()` 只有 `try/finally`，任一路挂掉都变成没人处理的 rejection + 一片空状态。两处补 `catch` 弹后端 `message`；附加信息（急救事件、打卡总结）继续静默降级。新增 `ProfileView.spec.ts` 4 条、`PlansView.spec.ts` 5 条，计划页用真实 memory router 注入而不是 mock `vue-router`（模板里 `$router.push` 要用）。变异把两处 `toast.error` 换成 `void error`，恰好 4 条失败用例挂。前端 167 → 176 项。

## 已知取舍


1. 知识检索默认走关键词通道。BGE-M3 与 Chroma 的代码保留在 `app/integrations/chroma_client.py`，需要安装 torch 与 chromadb 并下载模型权重后把 `EMBEDDING_BACKEND` 切到 bge。两套索引独立，不混用向量。
2. 体检资料只解析 PDF 文本层，不做 OCR。图片与扫描件记 `unsupported` 并保留原件，不用模型猜字段。识别结果需要用户逐项确认才写指标表。
3. 计划调整只复制任务结构，不改任务日期。调整先生成草稿，确认才生效，放弃只作废这一版。任务内容想变只能等确认前在草稿里逐条删，模板本身不随调整原因重新生成。整体改期走 `POST /plans/{id}/shift`，只在计划未开始且当前版本无打卡时允许，已经开始就只能逐条改任务。
4. 无后台调度。提醒在访问时按需生成，这是 FDE 明确的选择。任务级开关只挡当天任务提醒，计划级提醒始终生成。
5. 周期报告只在周期结束后由用户手动生成，不随打卡自动触发。报告落 `tracking_summaries` 与 `health_reports`，同一计划同一周期只一份。
6. 前端封装层的清理只删了真正没人调的三个方法。后端 `GET /assessments/{id}/evidence`、`GET /conversations/{id}`、`GET /runs/{run_id}`、`GET /tracking/metrics` 仍保留：前两个的字段与 detail 重复，后两个是调试入口，删掉会牵动 OpenAPI 与文档示例，暂时留着。

## 待核验事项

1. 五维阈值来自公开指南要点，正式面向真实用户前需逐条核对原文与适用人群。
2. PHQ-2 与 PHQ-9 的中文验证版本与授权条件未核实，当前只用于演示量表分级。
3. 急救电话为配置项，默认 120，部署到其他地区必须改。
4. BGE-M3 在本机的加载耗时与内存占用未测。向量通道代码已就位，依赖见 `backend/requirements-vector.txt`。
5. Docker Compose 已在本机实跑，三容器 healthy，冒烟通过，见 C-01 至 C-11。
6. Postgres 上的 upgrade 与 downgrade 都实测过，一次性库上完成升降循环，见 M-04 至 M-08。
7. `~/.docker/daemon.json` 里加的 `registry-mirrors` 已被 Docker Desktop 覆盖回默认，现在文件里只剩 `builder` 与 `experimental`，`docker info` 没有 Mirrors 项。镜像是本地构建，拉取不受影响，换机部署前要在 Docker Desktop 设置里重新加。
8. 资料解析的规则按常见检验单写法覆盖，手头没有真实报告样本。真实排版的字段名变体、跨页表格、竖排文字都还没验过，拿到样本后要补规则与用例。
9. 容器实库上跑 `alembic check` 会报 LangGraph checkpointer 的四张表（`checkpoints`、`checkpoint_writes`、`checkpoint_blobs`、`checkpoint_migrations`）是「待删除」，因为这几张表由 checkpointer 自己建、不在模型里。这是噪音，不是漏迁移。空库上跑 check 才是可比对的信号。
10. 前端测试覆盖 `api/client.ts`、`api/stream.ts`、`stores/reminders.ts`、`views/planLogic.ts`、`views/profileLogic.ts`、`utils/*`（datetime、today、keyboard、redirect、sse、abort、nav、download）、`components/chartGeometry.ts`，外加 `TrendChart`（RT-01~06）、`ChatView`（CV-01~10，含确认卡片三条分支）、`MultiTrendChart`（6 条）、`ProfileView`（4 条）、`PlansView`（5 条）五组渲染用例。评估页仍没有渲染测试，也没配覆盖率阈值：判定与请求体拼装已抽成纯函数覆盖，剩下的是模板与事件接线。接口形状由 `tests/contract/test_frontend_types.py` 承担。
11. 业务日期固定在东八区（`BUSINESS_TZ`），非东八区用户看到的「今天」会是东八区的今天。急救电话默认 120、文案中文，这个假设与产品定位一致；真要支持其他时区得把偏移做成配置项。
12. 会话过期是「事后发现」：刷新由请求驱动，用户空闲着令牌过期不会主动续，要等下一次请求拿到 401 才跳转。`LoginView` 的回跳只接受站内绝对路径，底层仍靠 `router.push()` 的兜底重定向，不是唯一防线。
13. 前后端字段一致性比字段名、可空性与类型宽度（`NC`/`TC`），但不比类型**细节**：`string` 与字面量联合、`number[]` 与元素类型都算一类，元素层不再往下钻。请求体（`ProfilePatchBody`）方向相反，验「前端可能发的类型后端接得住」。嵌套结构（`ReportDetail.content`、`Recommendation`）与 `NO_MODEL` 里那些 service 拼的 dict 依旧没模型可对，只靠运行时取键。泛型接口（`ApiEnvelope<T>`、`PageData<T>`）解析时跳过。
14. 趋势图已无 echarts，改手写 SVG（`chartGeometry.ts` + `TrendChart.vue`）。代价是没有动画、缩放与多序列叠加，真需要第二条线得自己扩几何层。平滑用单调三次贝塞尔，代价是曲线比 Catmull-Rom 略「硬」——换来的是不会凭空鼓出没测到过的峰。体积已有自动化度量（`npm run size`，BG-01~03），只量 gzip 不量执行时间。
15. 流式请求只对 401 重放，其他错误（500、网络断）不重试：健康咨询是长耗时请求，自动重试有重复生成回复的风险。时间上限三层：前端空闲 45 秒、前端总时长 180 秒（靠 abort 打断 fetch，连「等响应头」阶段一起管住）、后端工作流按运行类型分档（评估/调整计划长链 `WORKFLOW_TIMEOUT_LONG` 默认 150，咨询/打卡/查报告短链 `WORKFLOW_TIMEOUT_SHORT` 默认 60，先于前端收口把 run 标成 failed）。都是硬上限，真需要更久的长咨询会被截断。流结束时若最后一帧没有空行收尾仍会被丢掉，当前后端每条事件都带 `\n\n`，实际不触发。
16. 离开聊天页会 abort 在跑的流，已收到的 token 保留在气泡里，不会补全成完整回复；后台也没有断点续流，回来只能重新发一次。`controller` 是模块级单例，同一时刻只允许一条流，重发会掐掉上一条——这是有意的，否则晚到的 token 会拼进新消息。
17. 测试永远拿不到模型：`conftest.py` 把 `LLM_API_KEY` 清空。想用真实模型验一遍聊天链路，得手动注释掉那一行再单独跑用例（或直接在浏览器里跑端到端）。这样换来的是测试与 CI 完全一致、不花钱、不随模型输出飘。
