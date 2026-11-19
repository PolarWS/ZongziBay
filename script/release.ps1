<#
============================================================================
 ZongziBay 发版脚本（Windows / PowerShell）

 做三件事：统一版本号 → 提交 → 推到 release 分支。
 推送后 GitHub Actions 会自动：校验 → 前后端测试 → 构建多架构镜像
 → 推 Docker Hub → 打 tag → 建 GitHub Release。

 用法：
   .\script\release.ps1 1.0.0-rc.11            # 发版
   .\script\release.ps1 v1.0.0-rc.11           # v 前缀会自动去掉
   .\script\release.ps1 1.0.0-rc.11 -DryRun    # 只改文件看 diff，随后还原

 前置条件：
   - 已切到 release 分支（git switch release）
   - 工作区干净，没有别的未提交改动
   - 本机有 node / npm（用来同步 web/package-lock.json）
============================================================================
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Version,

    # 只改文件、显示 diff，然后还原，不提交不推送
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = Split-Path -Parent $SCRIPT_DIR
Set-Location $ROOT

# PowerShell 里对原生命令要用这个，否则 $LASTEXITCODE 不会被检查
function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & git @Args
    if ($LASTEXITCODE -ne 0) { throw "git $($Args -join ' ') 执行失败（退出码 $LASTEXITCODE）" }
}

Write-Host "=== ZongziBay 发版 ==="

# --- 1. 版本号格式 ---
$Version = $Version.Trim()
if ($Version.StartsWith("v")) { $Version = $Version.Substring(1) }
if ($Version -notmatch '^\d+\.\d+\.\d+(-[0-9A-Za-z][0-9A-Za-z.-]*)?$') {
    throw "版本号格式不合法：$Version（示例：1.0.0、1.0.0-rc.11）"
}

# --- 2. 必须在 release 分支，且工作区干净 ---
$branch = (& git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -ne "release") {
    throw "当前分支是 [$branch]，发版请先切到 release：git switch release"
}

$dirty = @(& git status --porcelain)
if ($dirty.Count -gt 0) {
    Write-Host "工作区有未提交的改动：" -ForegroundColor Yellow
    $dirty | ForEach-Object { Write-Host "  $_" }
    throw "先提交或还原这些改动再发版（发版提交里只应该包含版本号）"
}

# --- 3. 版本号不能被占用（本地 tag 与远端 tag 都查）---
Write-Host "拉取远端 tags ..."
& git fetch --tags --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Warning "拉取远端 tags 失败（可能没网），继续执行；重复发版会被 Actions 拦下来"
}
if (& git tag -l "v$Version") {
    throw "tag v$Version 已存在，换个版本号（或先删掉旧 tag）"
}

$oldVersion = (Get-Content "VERSION" -Raw).Trim()
if ($oldVersion -eq $Version) {
    throw "当前版本号已经是 $Version，发版请填一个更高的版本号"
}
Write-Host "版本号：$oldVersion -> $Version"

# --- 4. 改 VERSION + web/package.json + web/package-lock.json ---
Set-Content -Path "VERSION" -Value $Version -NoNewline
Push-Location "web"
try {
    # 注意：PowerShell 里直接调 npm 会命中 npm.ps1 的参数解析 bug（报 Unknown command: "pm"），
    # Windows 上必须走 npm.cmd
    $npm = if (Get-Command "npm.cmd" -ErrorAction SilentlyContinue) { "npm.cmd" } else { "npm" }
    & $npm version $Version --no-git-tag-version --ignore-scripts --silent
    if ($LASTEXITCODE -ne 0) { throw "npm version 执行失败，检查 web/package.json 和包管理环境" }
}
finally {
    Pop-Location
}

# --- 5. DryRun：看完 diff 就还原 ---
if ($DryRun) {
    Write-Host ""
    Write-Host "[DryRun] 将要提交的改动：" -ForegroundColor Cyan
    & git --no-pager diff --stat
    & git --no-pager diff
    Invoke-Git checkout -- VERSION web/package.json web/package-lock.json
    Write-Host ""
    Write-Host "[DryRun] 已还原，没有提交" -ForegroundColor Cyan
    exit 0
}

# --- 6. 提交并推送，剩下的交给 GitHub Actions ---
Invoke-Git add VERSION web/package.json web/package-lock.json
Invoke-Git commit -m "chore(release): v$Version"
Invoke-Git push origin release

Write-Host ""
Write-Host "已推送 release 分支。" -ForegroundColor Green
Write-Host "到仓库的 Actions → Release 页面看进度："
Write-Host "  校验版本 → 前后端测试 → 构建 amd64/arm64 → 推 Docker Hub → 打 tag → 建 Release"
