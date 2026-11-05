param(
  [string]$Installer = "E:\Docker\installer\DockerDesktopInstaller.exe",
  [string]$InstallDir = "E:\Docker\Docker",
  [string]$DataRoot = "E:\Docker\data"
)

$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "需要管理员权限。右键 PowerShell 选择以管理员身份运行，再执行本脚本。"
}

if (-not (Test-Path $Installer)) {
  throw "找不到安装包：$Installer。先下载 Docker Desktop Installer.exe 放到该路径。"
}

# WSL2 是 Linux 容器的前提。没装就先装，装完必须重启，重启后再跑一次本脚本
# 原生命令往 stderr 写东西时 ErrorActionPreference=Stop 会误判成失败，这里临时放宽
$wslReady = $false
$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
  wsl --status 2> $null | Out-Null
  $wslReady = $LASTEXITCODE -eq 0
} catch {
  $wslReady = $false
}
$ErrorActionPreference = $previous

if (-not $wslReady) {
  Write-Output "未检测到 WSL2，正在安装。完成后请重启系统，再运行一次本脚本。"
  wsl --install --no-distribution
  exit 0
}

New-Item -ItemType Directory -Force -Path $InstallDir, $DataRoot | Out-Null

# 程序装 E 盘，镜像与数据卷也落 E 盘，C 盘只剩少量用户配置
$arguments = @(
  "install",
  "--quiet",
  "--accept-license",
  "--backend=wsl-2",
  "--installation-dir=$InstallDir",
  "--wsl-default-data-root=$DataRoot"
)

Write-Output "开始安装 Docker Desktop 到 $InstallDir"
Start-Process -FilePath $Installer -ArgumentList $arguments -Wait -NoNewWindow

$service = Get-Service -Name "com.docker.service" -ErrorAction SilentlyContinue
if ($null -eq $service) {
  throw "安装进程结束但没有找到 com.docker.service，请查看 Docker 安装日志后再试。"
}

# 数据盘落在 E 盘的标志是这里出现 ext4.vhdx，没有就是被装回了 C 盘
$vhdx = Get-ChildItem -Path $DataRoot -Recurse -Filter "ext4.vhdx" -ErrorAction SilentlyContinue
if ($vhdx) {
  Write-Output "数据盘已落在 $DataRoot：$($vhdx[0].FullName)"
} else {
  Write-Output "暂时没看到 ext4.vhdx。首次启动 Docker Desktop 后回到这一步确认，若出现在 C 盘需要改设置里的磁盘镜像位置。"
}

Write-Output "安装完成。打开开始菜单里的 Docker Desktop，等状态变成 Running 后执行 scripts\start.ps1。"
