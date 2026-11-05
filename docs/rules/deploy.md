# 部署与本地环境

单机 Docker Compose，只绑 127.0.0.1。本机演示环境的安装位置固定，换机器时改脚本参数即可。

## 路径约定

- Docker Desktop 程序目录 `E:\Docker\Docker`，WSL 数据盘 `E:\Docker\data`。
- 程序与数据分两个目录：重装 Docker 不会带走镜像与数据卷。
- 镜像、命名卷、WSL 虚拟磁盘都在数据盘里，C 盘只剩少量用户配置。

安装参数写在 `deployment/scripts/install-docker.ps1`：

```
--installation-dir=E:\Docker\Docker
--wsl-default-data-root=E:\Docker\data
--backend=wsl-2
```

## 不要跨盘挂 Postgres 数据

Postgres 数据目录用命名卷，不 bind mount 到 NTFS。initdb 需要固定属主，Windows 盘的权限映射会让容器起不来。数据库跟着 WSL 数据盘走，本身已经在 E 盘。

上传件与导出报告可以 bind mount，走 `STORAGE_DIR`，默认 `../storage`，要换盘就写绝对路径。

## 备份脚本

`deployment/scripts/backup.ps1` 里的 `pg_dump -Fc` 是二进制格式，必须用 cmd 重定向写文件。走 PowerShell 管道会被字符编码破坏，恢复时报归档损坏。

## env 文件不能带 BOM

PowerShell 的 `Set-Content -Encoding utf8` 会写 BOM，第一行的键名变成 `\ufeffPOSTGRES_PASSWORD`，compose 读不到该变量，初始化时密码为空。生成 `.env` 用 `[System.IO.File]::WriteAllText` 或 python 写，`start.ps1` 起容器前会先查前三字节。

## ps1 脚本反过来必须带 BOM

`deployment/scripts/*.ps1` 一律存成 UTF-8 带 BOM。Windows PowerShell 5.1 读无 BOM 的文件按 GBK 解码，中文字符串里的全角字符会吃掉引号，`Parser::ParseFile` 直接报语法错误，脚本跑不起来。改完脚本用 `Parser::ParseFile` 过一遍再提交。

## 原生命令的 stderr 与退出码

curl、docker 都会往 stderr 写进度和告警。脚本开了 `$ErrorActionPreference = "Stop"` 时这些输出会被当成终止错误，正常进度也会把脚本打断，所以调原生命令前把该项临时改成 `Continue`，成败一律看 `$LASTEXITCODE`。

反过来，命令本身不存在时只产生非终止错误，`$LASTEXITCODE` 保持为空，`$code -ne 0` 会把空值当成功放过去。`start.ps1` 与 `backup.ps1` 开头都用 `Get-Command docker` 先挡一次。

## 镜像构建

`.dockerignore` 必须排除 `backend/.env`、`*.db`、`.venv`、`frontend/node_modules`。构建上下文是仓库根目录，漏掉一条就会把本地密钥打进镜像。

`auth.docker.io` 在部分网络下解析到不可达地址，构建到 `FROM python:3.13-slim` 就报 `failed to fetch oauth token`。这时先跑 `scripts\pull-base-images.ps1`，它从镜像站拉下四个基础镜像再打回原始标签，构建阶段命中本地镜像就不再走认证。也可以在 `~/.docker/daemon.json` 里加 `registry-mirrors`，但那要重启引擎才生效。

脚本按安装目录找到 `docker.exe` 后会把同目录加进 PATH，`docker-credential-desktop` 和它在一起，漏加就报凭据助手找不到。

## 起停

```powershell
cd deployment\scripts
.\pull-base-images.ps1   # 只在拉不到基础镜像时需要
.\start.ps1
.\start.ps1 -Vector
.\start.ps1 -Down
```

装完 Docker Desktop 后当前终端拿不到 `docker` 命令，PATH 要新开终端才刷新，所以脚本按 `-InstallDir` 兜底找 `resources\bin\docker.exe`，不依赖 PATH。

引擎没起来时 compose 一律报连接失败，脚本先 `docker info` 探一次，不通就启动 `Docker Desktop.exe` 并最多等五分钟。首次启动要初始化 WSL 发行版，慢是正常的。安装结束没有 `ext4.vhdx` 不是失败，那个文件由第一次启动建出来。

`-Down` 在引擎没运行时直接返回，不需要先起引擎才能停。

## 端口

只对外暴露 backend 的 8080 与 postgres 的 5432，都绑 127.0.0.1。

redis 只写 `expose` 不写 `ports`。需求文档要求 Redis 不直接对外开放，而且后端目前没有接任何 Redis 客户端，宿主端口放开只会和本机原生 redis 抢 6379，报 `bind: An attempt was made to access a socket in a way forbidden by its access permissions`。

## 常见问题

- `JWT_SECRET` 未填：compose 直接报错停下，这是故意的，缺密钥不允许启动。
- 改了 `POSTGRES_PASSWORD` 后后端连不上：命名卷里的密码只在第一次初始化时写入，容器重启不会重设。要么 `start.ps1 -Down` 后连卷一起删，要么进库执行 `ALTER USER`。
- 端口占用：先 `Get-NetTCPConnection -LocalPort 8080 -State Listen` 看是谁占的，本地起过 uvicorn 忘了关是最常见的原因，改映射只是掩盖问题。
- 容器起来但页面 404：镜像里没有 `frontend/dist`，构建阶段失败时检查 npm 那一步日志。
- 报 `Docker Desktop is unable to start`：多半是它拉不起 `wsl.exe`。在被安全策略限制的会话里启动 Docker Desktop 就会这样，换成手动从开始菜单打开。
