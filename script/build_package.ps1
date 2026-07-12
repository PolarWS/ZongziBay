$ErrorActionPreference = "Stop"

# --- 1. 配置与变量初始化 ---
if (Test-Path "VERSION") {
    $VERSION = (Get-Content "VERSION").Trim()
} else {
    $VERSION = "latest"
}

$REPO_NAME = "zongzibay"
$IMAGE_WITH_TAG = "${REPO_NAME}:$VERSION"
$LATEST_TAG = "${REPO_NAME}:latest"
$OUTPUT_FILE = "${REPO_NAME}_${VERSION}.tar"

# --- 获取当前时区 ---
$TZ = (Get-TimeZone).Id
# Windows 时区名转换为 IANA 时区名 (针对中国)
if ($TZ -eq "China Standard Time") {
    $TZ = "Asia/Shanghai"
}
Write-Host "Detected host timezone: $TZ"

# --- 1.5 清理本地旧容器和 volume ---
$oldContainer = docker ps -a --filter "ancestor=$REPO_NAME" --format "{{.ID}}" 2>$null
if ($oldContainer) {
    Write-Host "Stopping and removing old container: $oldContainer"
    docker stop $oldContainer 2>$null
    docker rm $oldContainer 2>$null
}

$oldVolumes = docker volume ls --filter "name=$REPO_NAME" --format "{{.Name}}" 2>$null
if ($oldVolumes) {
    Write-Host "Removing old volumes: $oldVolumes"
    docker volume rm $oldVolumes 2>$null
}

# --- 2. 构建镜像 (同时打两个标签) ---
Write-Host "----------------------------------------"
Write-Host "Step 1: Building Docker Image [$IMAGE_WITH_TAG]..."
Write-Host "With Timezone: $TZ"
Write-Host "Also Tagging as [$LATEST_TAG]..."
Write-Host "----------------------------------------"

# --no-cache 确保 config.yml 等每次重新 COPY，不使用旧缓存层
docker build --no-cache --build-arg "TZ=$TZ" -t $IMAGE_WITH_TAG -t $LATEST_TAG .

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build failed!"
    exit 1
}

# --- 3. 导出镜像到 tar ---
Write-Host "`n----------------------------------------"
Write-Host "Step 2: Exporting Image to [$OUTPUT_FILE]..."
Write-Host "----------------------------------------"

# 导出时包含两个标签，确保 load 后能看到版本号和 latest
docker save -o $OUTPUT_FILE $IMAGE_WITH_TAG $LATEST_TAG

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker save failed!"
    exit 1
}

# --- 4. 最终结果输出 ---
Write-Host "`n----------------------------------------"
Write-Host "Success! Image package created: $OUTPUT_FILE"
Write-Host "The package contains both [$VERSION] and [latest] tags."
Write-Host "You can load it elsewhere using: docker load -i $OUTPUT_FILE"
Write-Host "----------------------------------------"