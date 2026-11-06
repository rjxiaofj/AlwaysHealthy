# AlwaysHealthy

基于 LangGraph 的健康评估与管理平台。用户在对话里给出身体数据，系统抽取画像、跑规则引擎做五维风险评估、生成可执行的改善计划，并在计划周期内跟进打卡。

## 目录

```
backend/           FastAPI 服务、LangGraph 主图、规则引擎、迁移
frontend/          Vue3 前端，构建产物由后端同源托管
knowledge/         检索用健康知识语料
deployment/        docker compose 与备份脚本
docs/              模块规则与影响分析
```

## 本地启动

后端依赖 Python 3.13。

```bash
cd backend
python -m venv ../.venv
../.venv/Scripts/activate          # Windows
pip install -r requirements.txt
cp .env.example .env               # 填 LLM_API_KEY
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`.env.example` 指向 Postgres。只想先跑通流程的话，把 `DATABASE_URL` 改成 `sqlite+aiosqlite:///./alwayshealthy.db`，`CHECKPOINTER` 改成 `memory`，就不需要起数据库。

前端：

```bash
cd frontend
npm install
npm run build                      # 产物 frontend/dist 由后端直接返回
```

开发态要热更新时另起 `npm run dev`，Vite 已把 `/api` 代理到 8000。

## 环境变量

关键项见 `backend/.env.example`。

- `DATABASE_URL`：默认 sqlite，换 Postgres 时改成 `postgresql+asyncpg://...`
- `CHECKPOINTER`：`memory` 或 `postgres`，后者需要 `DATABASE_URL` 指向 Postgres
- `LLM_API_KEY`：DeepSeek 兼容接口密钥，留空时降级到规则回答
- `EMBEDDING_BACKEND`：`keyword` 走本地 TF-IDF，`bge` 走 BGE-M3 加 Chroma

切到 `bge` 之前先装可选依赖，首次启动会下载模型权重并建索引：

```bash
pip install -r requirements-vector.txt
```

## 测试

```bash
cd backend
pytest                             # 单元测试加接口流测试
python smoke_check.py              # 端到端冒烟，打印每一步的状态
```

```bash
cd frontend
npm test                           # vitest，跑 src 下的 *.spec.ts
npm run type-check                 # vue-tsc，spec 文件一并检查
npm run build                      # 产物进 backend 镜像的 /srv/frontend/dist
```

后端测试用 SQLite，每次会话从空库起，不需要 Postgres。前端测试环境是 happy-dom，不依赖浏览器。

`backend/tests/contract/` 直接读 `frontend/src/api/types.ts`，比字段名：前端声明过的字段，后端模型必须有。改 `types.ts` 或 `app/schemas/` 时它会先红。

`.github/workflows/ci.yml` 在每次 push 与 PR 上跑同样这两组命令，后端用 Python 3.13（与镜像基础版本一致），前端用 Node 22（vitest 5 要求 ^22.12.0）。

## 部署

### 一键部署（Docker 已就绪）

前提只有两个：Docker 引擎在跑（`docker info` 能返回版本号），以及 `deployment/.env` 里的 `JWT_SECRET` 已填。前端构建、数据库迁移、知识库同步都在镜像里自动完成，不需要本地装 Python/Node，也不用先 `npm run build`。

```bash
# 仓库根目录；已有 .env 就跳过第一行，别把填好的密钥覆盖掉
test -f deployment/.env || cp deployment/.env.example deployment/.env
# 编辑 deployment/.env 填 JWT_SECRET（必填，compose 会校验）
docker compose -f deployment/docker-compose.yml up -d --build
```

PowerShell 里第一行换成 `if (-not (Test-Path deployment/.env)) { Copy-Item deployment/.env.example deployment/.env }`。生成密钥：

```bash
python -c "import secrets; print(secrets.token_urlsafe(36))"
```

compose 会自动读同目录的 `deployment/.env`，不用额外 `--env-file`。`--build` 触发多阶段构建：`node:22-alpine` 阶段跑 `npm ci && npm run build`，产物拷进 `python:3.13-slim` 的 `/srv/frontend/dist`；容器启动时先 `alembic upgrade head` 再起 uvicorn。首次构建约 5–10 分钟。

检查与访问：

```bash
docker compose -f deployment/docker-compose.yml ps   # postgres / redis / backend 都 healthy
curl http://127.0.0.1:8080/health/live              # 200
```

前端与接口都在 `http://127.0.0.1:8080`，接口文档在 `/api/docs`。容器只绑 127.0.0.1，不对局域网开放。

Windows 下也有现成的一键脚本，额外兜住「找 `docker.exe`、引擎没起就拉起 Docker Desktop、首次生成 `.env`」：

```powershell
.\deployment\scripts\start.ps1              # 起
.\deployment\scripts\start.ps1 -Vector      # 带 chroma，用 bge 检索时
.\deployment\scripts\start.ps1 -Down        # 停
```

| 目的 | 命令 |
| --- | --- |
| 看后端日志 | `docker compose -f deployment/docker-compose.yml logs -f backend` |
| 改了代码后重建 | `docker compose -f deployment/docker-compose.yml up -d --build` |
| 只改了 `.env` | `docker compose -f deployment/docker-compose.yml up -d`（重建容器，镜像不用重编） |
| 停止并保留数据 | `docker compose -f deployment/docker-compose.yml down` |
| 停止并删库（危险） | 上面加 `-v`，连命名卷一起删 |

`LLM_API_KEY` 留空时降级到规则回答、不调外部模型；要接 DeepSeek 就填进 `deployment/.env` 再 `up -d`。`EMBEDDING_BACKEND=bge` 时还要带 `--profile vector`（或 `start.ps1 -Vector`）把 chroma 拉起来。

### 首次安装 Docker Desktop（Windows）

安装包放在 `E:\Docker\installer`，程序目录与镜像数据都放 E 盘：

```powershell
cd deployment\scripts
.\fetch-installer.ps1              # 下载安装包，中断后重跑会续传

# 管理员 PowerShell
.\install-docker.ps1
```

脚本调用安装器时带 `--installation-dir=E:\Docker\Docker` 和 `--wsl-default-data-root=E:\Docker\data`，所以镜像、数据卷、WSL 磁盘都不占 C 盘。没装 WSL2 时脚本会先装并发提示，重启后再跑一次。

安装结束不会立刻有 `ext4.vhdx`，那个文件要等 Docker Desktop 第一次启动、初始化 WSL 发行版时才建出来。安装完的**当前终端**认不到 `docker` 命令，PATH 要新开终端才刷新——这时用 `start.ps1` 兜底，它先按 PATH 找 `docker`，找不到再去 `-InstallDir`（默认 `E:\Docker\Docker`）下取 `resources\bin\docker.exe`；新开终端后直接敲上面的 `docker compose` 即可。

`start.ps1` 在引擎未就绪时会启动 Docker Desktop 并最多等五分钟，首次初始化 WSL 会慢一些。`auth.docker.io` 在部分网络下连不上、构建停在拉基础镜像时，先跑 `.\pull-base-images.ps1`，它从镜像站取回四个基础镜像再打回原始标签，构建就只走本地。

第一次运行会把 `.env.example` 复制成 `.env` 并中断，填好 `JWT_SECRET` 再跑。

### 数据与备份

compose 里 postgres、redis、backend 常开，chroma 在 `vector` profile 下按需拉起。日志按 10MB 三份轮转。

数据分两处：

| 内容 | 位置 | 说明 |
| --- | --- | --- |
| 数据库与向量索引 | 命名卷，随 WSL 数据盘 | 安装脚本已把 WSL 数据盘指到 `E:\Docker\data` |
| 上传件与导出报告 | `deployment/.env` 的 `STORAGE_DIR` | 默认 `../storage`，可直接改成 E 盘绝对路径 |

备份脚本 `scripts\backup.ps1` 默认写到仓库下 `backup_data`，换盘加参数：

```powershell
.\backup.ps1 -Target E:\Docker\backup
```

## 工程约束

改动前先看 `AGENTS.md`。权限校验、数据范围过滤、消息加密属于大动脉，动之前要写影响分析。验证记录在 `MEMORY.md`。
