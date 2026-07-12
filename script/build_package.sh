#!/bin/bash
set -e

# --- 1. 配置部分 ---
# 读取 VERSION 文件，如果不存在则默认为 latest
VERSION=$(cat VERSION 2>/dev/null | tr -d '\r\n' || echo "latest")
REPO_NAME="zongzibay"
IMAGE_WITH_TAG="${REPO_NAME}:${VERSION}"
LATEST_TAG="${REPO_NAME}:latest"
OUTPUT_FILE="${REPO_NAME}_${VERSION}.tar"

# --- 1.5 获取当前时区 ---
# 尝试从 /etc/timezone 获取，如果不存在则使用 UTC
TZ=$(cat /etc/timezone 2>/dev/null || echo "UTC")
echo "Detected host timezone: $TZ"

# --- 2. 构建镜像 (同时打两个标签) ---
echo "----------------------------------------"
echo "Step 1: Building Docker Image..."
echo "Tag 1: $IMAGE_WITH_TAG"
echo "Tag 2: $LATEST_TAG"
echo "Timezone: $TZ"
echo "----------------------------------------"

# 使用多个 -t 参数，确保同一个 Image ID 拥有两个标签，并传入时区参数
docker build --build-arg TZ="$TZ" -t "$IMAGE_WITH_TAG" -t "$LATEST_TAG" .

# --- 3. 导出镜像到 tar ---
echo ""
echo "----------------------------------------"
echo "Step 2: Exporting Image to [$OUTPUT_FILE]..."
echo "----------------------------------------"

# 关键点：导出时必须同时写上两个标签名，
# 这样在目标机器 docker load 时才会同时出现版本号和 latest
docker save -o "$OUTPUT_FILE" "$IMAGE_WITH_TAG" "$LATEST_TAG"

# --- 4. 成功输出 ---
echo ""
echo "----------------------------------------"
echo "Success! Image package created: $OUTPUT_FILE"
echo "The package contains both [$VERSION] and [latest] tags."
echo "You can load it elsewhere using: docker load -i $OUTPUT_FILE"
echo "----------------------------------------"