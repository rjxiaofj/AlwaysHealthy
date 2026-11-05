param(
  [string]$Target = "$PSScriptRoot\..\..\backup_data"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "找不到 docker 命令，先装 Docker Desktop 并启动。"
}

$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$compose = Join-Path $root "deployment\docker-compose.yml"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$work = Join-Path $Target $stamp
New-Item -ItemType Directory -Force -Path $work | Out-Null

# 二进制转储不能走 PowerShell 管道，字符编码会把 dump 写坏，交给 cmd 重定向
# docker 往 stderr 写告警时 Stop 会误判成失败，靠退出码判断
$dump = Join-Path $work "alwayshealthy.dump"
$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
cmd /c "docker compose -f `"$compose`" exec -T postgres pg_dump -U alwayshealthy -d alwayshealthy -Fc > `"$dump`""
$code = $LASTEXITCODE
$ErrorActionPreference = $previous
if ($code -ne 0) {
  throw "pg_dump 失败，确认 postgres 容器正在运行"
}

$paths = @()
foreach ($name in @("knowledge", "storage")) {
  $path = Join-Path $root $name
  if (Test-Path $path) { $paths += $path }
}
if ($paths.Count -gt 0) {
  Compress-Archive -Path $paths -DestinationPath (Join-Path $work "files.zip") -Force
}

Copy-Item "$root\backend\app\tools\risk_engine\rules" -Destination $work -Recurse

Compress-Archive -Path $work -DestinationPath (Join-Path $Target "alwayshealthy-$stamp.zip") -Force
Remove-Item $work -Recurse -Force

Get-ChildItem $Target -Filter "alwayshealthy-*.zip" |
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
  Remove-Item -Force

Write-Output "备份完成 $(Join-Path $Target "alwayshealthy-$stamp.zip")"
