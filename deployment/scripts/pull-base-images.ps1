param(
  [string]$Mirror = "docker.m.daocloud.io",
  [string]$InstallDir = "E:\Docker\Docker",
  [string[]]$Images = @("python:3.13-slim", "node:22-alpine", "postgres:16-alpine", "redis:7-alpine")
)

$ErrorActionPreference = "Stop"

# auth.docker.io 在部分网络下解析到不可达地址，构建时拉基础镜像会直接失败。
# 先从镜像站拉下来，打回原始标签，构建阶段命中本地镜像就不再走认证。
function Resolve-Docker {
  $cmd = Get-Command docker -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $candidate = Join-Path $InstallDir "resources\bin\docker.exe"
  if (Test-Path $candidate) {
    $env:PATH = (Split-Path $candidate -Parent) + ";" + $env:PATH
    return $candidate
  }

  throw "找不到 docker 命令，先装 Docker Desktop 或加 -InstallDir 指定安装位置。"
}

$docker = Resolve-Docker

$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$failed = @()

foreach ($image in $Images) {
  $source = "$Mirror/library/$image"
  & $docker image inspect $image *> $null
  if ($LASTEXITCODE -eq 0) {
    Write-Output "已有 $image，跳过"
    continue
  }

  Write-Output "拉取 $source"
  & $docker pull $source
  if ($LASTEXITCODE -ne 0) {
    $failed += $image
    continue
  }

  & $docker tag $source $image
  if ($LASTEXITCODE -ne 0) { $failed += $image }
}

$ErrorActionPreference = $previous

if ($failed.Count -gt 0) {
  throw "这些镜像没拉下来：$($failed -join ', ')。换一个镜像站重试，例如 -Mirror docker.1panel.live。"
}

Write-Output "基础镜像就绪，可以执行 start.ps1"
