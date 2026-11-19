<#
============================================================================
 ZongziBay 离线镜像打包脚本（Windows / PowerShell）

 产出三个文件（默认同时出 amd64 与 arm64）：
   zongzibay_<版本>.tar           多架构 OCI 归档，一个文件通吃两种架构
   zongzibay_<版本>_amd64.tar     仅 amd64 的 docker-archive
   zongzibay_<版本>_arm64.tar     仅 arm64 的 docker-archive

 用法：
   .\script\build_package.ps1                       # amd64 + arm64
   .\script\build_package.ps1 -Platform linux/amd64  # 只出 amd64
   .\script\build_package.ps1 -NoCache              # 不用构建缓存
   .\script\build_package.ps1 -Load                 # 顺手导入本机架构到本地 docker
   .\script\build_package.ps1 -CleanVolumes         # 顺带删掉旧的 zongzibay_* volume（会丢数据）

 目标机器怎么选文件：
   Docker 25+（含 containerd 镜像存储）：用多架构的 zongzibay_<版本>.tar，
     docker load -i zongzibay_<版本>.tar 会自动挑当前机器能跑的那个架构。
   老版本 Docker（NAS 上常见）：用对应架构的 _amd64/_arm64.tar，
     它跟以前的老 tar 是同一种格式，兼容性最好。
============================================================================
#>
param(
    [string]$Platform = $(if ($env:PLATFORMS) { $env:PLATFORMS } else { "linux/amd64,linux/arm64" }),
    [switch]$NoCache,
    [switch]$Load,
    # 删掉名字含 zongzibay 的 volume（数据库/配置/下载文件都在里面），默认不删
    [switch]$CleanVolumes,
    [string]$BuilderName = $(if ($env:BUILDER_NAME) { $env:BUILDER_NAME } else { "zongzibay-builder" })
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# PowerShell 里对原生命令要用这个，否则 $LASTEXITCODE 不刷新
function Invoke-Docker {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & docker @Args
    if ($LASTEXITCODE -ne 0) { throw "docker $($Args[0]) $($Args[1]) 执行失败（退出码 $LASTEXITCODE）" }
}

# --- 1. 配置与变量初始化 ---
if (Test-Path "VERSION") {
    $VERSION = (Get-Content "VERSION").Trim()
} else {
    $VERSION = "latest"
}

$REPO_NAME = "zongzibay"
$IMAGE_WITH_TAG = "${REPO_NAME}:$VERSION"
$LATEST_TAG = "${REPO_NAME}:latest"
$MULTI_FILE = "${REPO_NAME}_${VERSION}.tar"

$Platform = ($Platform -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }) -join ","
if (-not $Platform) { throw "错误：平台列表为空" }

# --- 获取当前时区 ---
$TZ = (Get-TimeZone).Id
# Windows 时区名转 IANA 名，容器里的 tzdata 只认 IANA
$tzMap = @{
    "China Standard Time" = "Asia/Shanghai"
    "Taipei Standard Time" = "Asia/Taipei"
    "Tokyo Standard Time"  = "Asia/Tokyo"
    "Korea Standard Time"  = "Asia/Seoul"
    "Singapore Standard Time" = "Asia/Singapore"
}
if ($tzMap.ContainsKey($TZ)) {
    $TZ = $tzMap[$TZ]
} elseif ($TZ -notmatch "^[A-Za-z]+/[A-Za-z_]+$") {
    # 没映射到又不是 IANA 写法的话，直接塞给容器会静默变成错的时间
    Write-Warning "时区「$TZ」无法转换成 IANA 名称，本次改用 UTC；需要别的时区请手动设 `$env:TZ"
    $TZ = "UTC"
}
Write-Host "检测到宿主机时区: $TZ"

# --- 1.5 清理本地旧容器（volume 需要显式 -CleanVolumes 才动）---
$oldContainer = docker ps -a --filter "ancestor=$REPO_NAME" --format "{{.ID}}" 2>$null
if ($oldContainer) {
    Write-Host "停止并删除旧容器: $oldContainer"
    docker stop $oldContainer 2>$null | Out-Null
    docker rm $oldContainer 2>$null | Out-Null
}

# volume 里装的是数据库、下载器配置和已下载的文件，删掉不可恢复。
# 而且 --filter name= 是子串匹配，任何名字里带 zongzibay 的卷都会命中
# （比如 docker compose 项目建的 zongzibay_app_config / zongzibay_downloads），
# 所以这里默认只提示、不删，要删请显式加 -CleanVolumes。
$oldVolumes = @(docker volume ls --filter "name=$REPO_NAME" --format "{{.Name}}" 2>$null)
if ($oldVolumes.Count -gt 0 -and -not $CleanVolumes) {
    Write-Host ""
    Write-Warning "发现 $($oldVolumes.Count) 个名字含 [$REPO_NAME] 的 volume，本次未删除："
    $oldVolumes | ForEach-Object { Write-Host "    $_" }
    Write-Warning "这些卷里通常有数据库和已下载的文件。确认可以丢弃后加 -CleanVolumes 重跑。"
    Write-Host ""
}
elseif ($oldVolumes.Count -gt 0) {
    Write-Host "删除旧 volume: $($oldVolumes -join ', ')"
    docker volume rm $oldVolumes 2>$null | Out-Null
}

# --- 1.6 准备 buildx 构建器 ---
# 多架构构建只有 BuildKit 才做得到，docker build 不行
& docker buildx version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "未找到 docker buildx，无法构建多架构镜像。Docker Desktop 自带；Linux 上请安装 docker-buildx-plugin。"
}

# 当前的构建器如果是 docker 驱动，只有开了 containerd 镜像存储才支持多平台。
# 没开就另起一个 docker-container 驱动的构建器，免得卡在
# "multiple platforms feature is currently not supported for docker driver"。
$builderArgs = @()
$driver = ""
$driverLine = docker buildx inspect 2>$null |
              Select-String -Pattern '^Driver:\s*(.+)$' | Select-Object -First 1
# 解析不出来就留空、按“当前构建器可用”处理，别在这里抛 null 异常把整个打包打断
if ($driverLine) { $driver = $driverLine.Matches.Groups[1].Value.Trim() }
$hasContainerd = (docker info 2>$null | Select-String -Pattern "io\.containerd\.snapshotter" -Quiet)

if ($driver -eq "docker" -and -not $hasContainerd) {
    docker buildx inspect $BuilderName *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "当前 docker 驱动不支持多架构，创建构建器 [$BuilderName]（docker-container 驱动）…"
        Invoke-Docker buildx create --name $BuilderName --driver docker-container | Out-Null
    }
    $builderArgs = @("--builder", $BuilderName)
}

# 构建参数：多架构与单架构两次导出共用，标签必须带上，
# 否则 docker load 后只剩 <none>
$buildArgs = $builderArgs + @(
    "--build-arg", "TZ=$TZ",
    "-t", $IMAGE_WITH_TAG,
    "-t", $LATEST_TAG,
    "--provenance=false"
)
if ($NoCache) { $buildArgs += "--no-cache" }

# 一共几步：1 次多架构导出 + 每个架构各 1 次单架构导出
$totalSteps = ($Platform -split ",").Count + 1

Write-Host "----------------------------------------"
Write-Host "版本:     $VERSION"
Write-Host "标签:     $IMAGE_WITH_TAG , $LATEST_TAG"
Write-Host "架构:     $Platform"
Write-Host "----------------------------------------"

# --- 2. 多架构单文件归档 ---
Write-Host "`n[1/$totalSteps] 构建多架构镜像并导出 OCI 归档 -> $MULTI_FILE"
Invoke-Docker buildx build @buildArgs --platform $Platform --output "type=oci,dest=$MULTI_FILE" .
$produced = @($MULTI_FILE)

# --- 3. 每个架构各出一个 docker-archive ---
# buildx 会复用上一步的构建缓存，这一步不会重跑编译
$i = 2
foreach ($p in ($Platform -split ",")) {
    $suffix = $p -replace "^linux/", "" -replace "/", "_"   # linux/arm/v7 -> arm_v7
    $out = "${REPO_NAME}_${VERSION}_${suffix}.tar"
    Write-Host "`n[$i/$totalSteps] 导出 $p 的 docker-archive -> $out"
    Invoke-Docker buildx build @buildArgs --platform $p --output "type=docker,dest=$out" .
    $produced += $out
    $i++
}

# --- 4. 可选：把本机架构导入本地 docker ---
# 多架构构建走的是 buildx，默认不会把镜像留在本机 docker 里
if ($Load) {
    $hostArch = (docker version --format "{{.Server.Arch}}" 2>$null)
    $hostTar = "${REPO_NAME}_${VERSION}_${hostArch}.tar"
    if ($hostArch -and (Test-Path $hostTar)) {
        Write-Host "`n[-Load] 导入本机架构（$hostArch）到本地 docker"
        Invoke-Docker load -i $hostTar
    } else {
        Write-Host "`n[-Load] 跳过：本次未导出本机架构（$hostArch）的 tar"
    }
}

# --- 5. 最终结果输出 ---
Write-Host "`n----------------------------------------"
Write-Host "打包完成："
foreach ($f in $produced) {
    if (Test-Path $f) {
        $item = Get-Item $f
        Write-Host ("  {0}  {1:N1} MB" -f $item.Name, ($item.Length / 1MB))
    }
}

# 上次用别的架构组合跑过的话，会留下本次没重新生成的 tar，
# 列出来免得被当成这一次的产物（不自动删，用户可能还要用）
$stale = Get-ChildItem -Path "${REPO_NAME}_${VERSION}*.tar" -ErrorAction SilentlyContinue |
         Where-Object { $produced -notcontains $_.Name }
if ($stale) {
    Write-Host ""
    Write-Host "注意：下面这些是之前跑别的架构组合留下的，本次没有重新生成："
    $stale | ForEach-Object { Write-Host "  $($_.Name)" }
}
Write-Host ""
Write-Host "多架构通吃（Docker 25+）：docker load -i $MULTI_FILE"
Write-Host "按架构选用（老版本 Docker）：docker load -i ${REPO_NAME}_${VERSION}_<架构>.tar"
Write-Host "----------------------------------------"
