param(
  [string]$Target = "E:\Docker\installer\DockerDesktopInstaller.exe",
  [string]$Url = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
)

$ErrorActionPreference = "Stop"

# 只看大小判不了完整，签名为 Valid 且签发者是 Docker Inc 才算能用的安装包
function Test-Installer([string]$Path) {
  if (-not (Test-Path $Path)) { return $false }
  $sig = Get-AuthenticodeSignature $Path
  return ($sig.Status -eq "Valid" -and $sig.SignerCertificate.Subject -like "*O=Docker Inc*")
}

$dir = Split-Path $Target -Parent
New-Item -ItemType Directory -Force -Path $dir | Out-Null

# 文件已完整时再用 -C - 续传会收到 416，直接走签名判断省掉这次请求
if (Test-Installer $Target) {
  Write-Output "安装包已完整，跳过下载 $Target"
  exit 0
}

# curl 的进度与告警写 stderr，Stop 会把它当错误终止脚本，这里放宽并靠下面的签名判断收口
$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
curl.exe -sS -L --http1.1 --retry 6 --retry-delay 5 --retry-all-errors -C - -o $Target $Url
$ErrorActionPreference = $previous

if (-not (Test-Installer $Target)) {
  $sizeMB = 0
  if (Test-Path $Target) { $sizeMB = [math]::Round((Get-Item $Target).Length / 1MB, 1) }
  throw "安装包不完整或签名无效，当前 ${sizeMB}MB。重跑本脚本续传。"
}

$sizeMB = [math]::Round((Get-Item $Target).Length / 1MB, 1)
Write-Output "下载完成 $Target 大小 ${sizeMB}MB"
