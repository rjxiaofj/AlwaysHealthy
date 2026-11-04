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

```bash
cd deployment
docker compose up -d
```

compose 里 postgres、redis、backend 常开，chroma 在 `vector` profile 下按需拉起。

## 工程约束

改动前先看 `AGENTS.md`。权限校验、数据范围过滤、消息加密属于大动脉，动之前要写影响分析。验证记录在 `MEMORY.md`。
