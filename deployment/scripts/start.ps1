param(
  [switch]$Down,
  [switch]$Vector,
  [string]$InstallDir = "E:\Docker\Docker"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

# Docker Desktop 装完不会立刻写 PATH，当前终端要重开才认。这里按安装目录兜底找
function Resolve-Docker {
  $cmd = Get-Command docker -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $candidate = Join-Path $InstallDir "resources\bin\docker.exe"
  if (Test-Path $candidate) {
    # 同目录的 docker-credential-desktop 也要在 PATH 里，否则拉镜像报凭据助手找不到
    $env:PATH = (Split-Path $candidate -Parent) + ";" + $env:PATH
    return $candidate
  }

  throw "找不到 docker 命令，也没在 $InstallDir 下找到 docker.exe。先按 README 装好 Docker Desktop。"
}

# 引擎没就绪时 compose 一律报连接失败。原生命令的 stderr 会干扰 Stop，这里放宽
function Test-Engine([string]$Docker) {
  $previous = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  & $Docker info --format "{{.ServerVersion}}" *> $null
  $ok = $LASTEXITCODE -eq 0
  $ErrorActionPreference = $previous
  return $ok
}

function Wait-Engine([string]$Docker, [int]$Seconds) {
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-Engine $Docker) { return $true }
    Start-Sleep -Seconds 3
  }
  return $false
}

# docker 把构建进度写到 stderr，Stop 会把正常进度当成错误中断，统一靠退出码判失败
function Invoke-Compose([string]$Docker, [string[]]$Arguments) {
  $previous = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  & $Docker @Arguments
  $code = $LASTEXITCODE
  $ErrorActionPreference = $previous
  return $code
}

$docker = Resolve-Docker

if ($Down) {
  if (-not (Test-Engine $docker)) {
    Write-Output "引擎没在运行，没有需要停止的容器"
    exit 0
  }
  exit (Invoke-Compose $docker @("compose", "down"))
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  throw "已生成 deployment\.env，先填 JWT_SECRET 再运行本脚本。"
}

# PowerShell 生成的 env 带 BOM 时，第一行键名被污染，compose 读不到该变量
$envBytes = [System.IO.File]::ReadAllBytes((Resolve-Path ".env"))
if ($envBytes.Length -ge 3 -and $envBytes[0] -eq 0xEF -and $envBytes[1] -eq 0xBB -and $envBytes[2] -eq 0xBF) {
  throw "deployment\.env 带 BOM，第一行变量会失效。用 UTF-8 无 BOM 重写该文件。"
}

# 装机后第一次启动要初始化 WSL 发行版，比日常启动慢很多
if (-not (Wait-Engine $docker 5)) {
  $desktop = Join-Path $InstallDir "Docker Desktop.exe"
  if (-not (Test-Path $desktop)) {
    throw "引擎没起来，也没在 $InstallDir 下找到 Docker Desktop.exe。确认安装路径后用 -InstallDir 指定。"
  }
  Write-Output "引擎未运行，正在启动 Docker Desktop。首次启动要初始化 WSL，耐心等"
  Start-Process -FilePath $desktop | Out-Null
  if (-not (Wait-Engine $docker 300)) {
    throw "等了五分钟引擎仍未就绪。手动打开 Docker Desktop 看它的报错，常见是 WSL2 没装或虚拟化没开。"
  }
}

$composeArgs = @("compose", "-f", "docker-compose.yml")
if ($Vector) { $composeArgs += @("--profile", "vector") }

# 第一次会构建镜像，约五到十分钟
$code = Invoke-Compose $docker ($composeArgs + @("up", "-d", "--build"))
if ($code -ne 0) { exit $code }

Invoke-Compose $docker ($composeArgs + @("ps")) | Out-Null
Write-Output "后端地址 http://127.0.0.1:8080 接口文档 http://127.0.0.1:8080/api/docs"
