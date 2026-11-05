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

## 部署

先装 Docker Desktop。安装包放在 `E:\Docker\installer`，程序目录与镜像数据都放 E 盘：

```powershell
cd deployment\scripts
.\fetch-installer.ps1              # 下载安装包，中断后重跑会续传

# 管理员 PowerShell
.\install-docker.ps1
```

脚本调用安装器时带 `--installation-dir=E:\Docker\Docker` 和 `--wsl-default-data-root=E:\Docker\data`，所以镜像、数据卷、WSL 磁盘都不占 C 盘。没装 WSL2 时脚本会先装并发提示，重启后再跑一次。

安装结束不会立刻有 `ext4.vhdx`，那个文件要等 Docker Desktop 第一次启动、初始化 WSL 发行版时才建出来。安装完当前终端也认不到 `docker` 命令，PATH 要新开终端才刷新，所以下面用脚本起服务，不要手工敲 `docker compose`。

```powershell
cd deployment\scripts
.\pull-base-images.ps1   # 拉不到基础镜像时先跑这条，走镜像站
.\start.ps1              # 引擎没起会自动拉起 Docker Desktop，首次要构建镜像
.\start.ps1 -Vector      # 需要 bge 检索时带上 chroma
.\start.ps1 -Down        # 停止
```

`start.ps1` 先按 PATH 找 `docker`，找不到就去 `-InstallDir` 指定的安装目录取 `resources\bin\docker.exe`。引擎没就绪时它会启动 Docker Desktop 并最多等五分钟，首次启动要初始化 WSL 会慢一些。

`auth.docker.io` 在部分网络下连不上，构建会停在拉基础镜像那一步。`pull-base-images.ps1` 从镜像站取回四个基础镜像再打回原始标签，构建就只走本地。

第一次运行会把 `.env.example` 复制成 `.env` 并中断，填好 `JWT_SECRET` 再跑。后端在 `http://127.0.0.1:8080`，接口文档在 `/api/docs`。

compose 里 postgres、redis、backend 常开，chroma 在 `vector` profile 下按需拉起。容器只绑 127.0.0.1，日志按 10MB 三份轮转。

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
