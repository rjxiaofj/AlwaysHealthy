param(
  [string]$Target = "$PSScriptRoot\..\..\backup_data"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$work = Join-Path $Target $stamp
New-Item -ItemType Directory -Force -Path $work | Out-Null

docker compose -f "$root\deployment\docker-compose.yml" exec -T postgres pg_dump -U alwayshealthy -d alwayshealthy -Fc |
  Set-Content -Path (Join-Path $work "alwayshealthy.dump") -Encoding Byte

Compress-Archive -Path "$root\knowledge", "$root\storage" -DestinationPath (Join-Path $work "files.zip") -Force
Copy-Item "$root\backend\app\tools\risk_engine\rules" -Destination $work -Recurse

Compress-Archive -Path $work -DestinationPath (Join-Path $Target "alwayshealthy-$stamp.zip") -Force
Remove-Item $work -Recurse -Force

Get-ChildItem $Target -Filter "alwayshealthy-*.zip" |
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
  Remove-Item -Force

Write-Output "备份完成 $Target\alwayshealthy-$stamp.zip"
