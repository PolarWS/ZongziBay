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

# --- 2. 构建镜像 (同时打两个标签) ---
Write-Host "----------------------------------------"
Write-Host "Step 1: Building Docker Image [$IMAGE_WITH_TAG]..."
Write-Host "Also Tagging as [$LATEST_TAG]..."
Write-Host "----------------------------------------"

# 一次构建，两个标签
docker build -t $IMAGE_WITH_TAG -t $LATEST_TAG .

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