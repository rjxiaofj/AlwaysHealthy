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

## 已知取舍

1. 知识检索默认走关键词通道。BGE-M3 与 Chroma 的代码保留在 `app/integrations/chroma_client.py`，需要安装 torch 与 chromadb 并下载模型权重后把 `EMBEDDING_BACKEND` 切到 bge。两套索引独立，不混用向量。
2. 体检资料只解析 PDF 文本层，不做 OCR。图片与扫描件记 `unsupported` 并保留原件，不用模型猜字段。识别结果需要用户逐项确认才写指标表。
3. 计划调整只复制任务结构，不改任务日期。整体改期走 `POST /plans/{id}/shift`，只在计划未开始且当前版本无打卡时允许，已经开始就只能逐条改任务。
4. 无后台调度。提醒在访问时按需生成，这是 FDE 明确的选择。

## 待核验事项

1. 五维阈值来自公开指南要点，正式面向真实用户前需逐条核对原文与适用人群。
2. PHQ-2 与 PHQ-9 的中文验证版本与授权条件未核实，当前只用于演示量表分级。
3. 急救电话为配置项，默认 120，部署到其他地区必须改。
4. BGE-M3 在本机的加载耗时与内存占用未测。向量通道代码已就位，依赖见 `backend/requirements-vector.txt`。
5. Docker Compose 已在本机实跑，三容器 healthy，冒烟通过，见 C-01 至 C-10。
6. Postgres 上的 upgrade 已实测。downgrade 只在 sqlite 上跑过，Postgres 上没做降级，动迁移脚本前要先在一次性库上验一遍。
7. `~/.docker/daemon.json` 里加的 `registry-mirrors` 需要重启引擎才生效，重启后确认 `docker info` 的 Mirrors 是否非空。
8. 资料解析的规则按常见检验单写法覆盖，手头没有真实报告样本。真实排版的字段名变体、跨页表格、竖排文字都还没验过，拿到样本后要补规则与用例。
