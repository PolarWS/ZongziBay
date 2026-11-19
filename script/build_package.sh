#!/bin/bash
set -e

# ============================================================================
# ZongziBay 离线镜像打包脚本
#
# 产出三个文件（默认同时出 amd64 与 arm64）：
#   zongzibay_<版本>.tar           多架构 OCI 归档，一个文件通吃两种架构
#   zongzibay_<版本>_amd64.tar     仅 amd64 的 docker-archive
#   zongzibay_<版本>_arm64.tar     仅 arm64 的 docker-archive
#
# 用法：
#   ./script/build_package.sh                        # amd64 + arm64
#   ./script/build_package.sh -p linux/amd64         # 只出 amd64
#   ./script/build_package.sh --no-cache             # 不用构建缓存
#   ./script/build_package.sh --load                 # 顺手导入本机架构到本地 docker
#
# 目标机器怎么选文件：
#   Docker 25+（含 containerd 镜像存储）：用多架构的 zongzibay_<版本>.tar，
#     docker load -i zongzibay_<版本>.tar 会自动挑当前机器能跑的那个架构。
#   老版本 Docker（NAS 上常见）：用对应架构的 _amd64/_arm64.tar，
#     它跟以前的老 tar 是同一种格式，兼容性最好。
# ============================================================================

# --- 1. 配置部分 ---
VERSION=$(cat VERSION 2>/dev/null | tr -d '\r\n' || echo "latest")
REPO_NAME="zongzibay"
IMAGE_WITH_TAG="${REPO_NAME}:${VERSION}"
LATEST_TAG="${REPO_NAME}:latest"

# 目标架构。默认两种都出；只想出一种时用 -p 或设 PLATFORMS 环境变量
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"

MULTI_FILE="${REPO_NAME}_${VERSION}.tar"
BUILDER_NAME="${BUILDER_NAME:-zongzibay-builder}"

NO_CACHE=""
DO_LOAD=0

usage() {
    # 直接回放文件顶部的注释块。用文字锚点而不是行号，
    # 免得以后改注释把行号改漂了、-h 打出半截帮助
    sed -n '/^# 产出三个文件/,/^# ===/p' "$0" | sed 's/^# \{0,1\}//; $d'
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        -p|--platform)  PLATFORMS="$2"; shift 2 ;;
        --platform=*)   PLATFORMS="${1#*=}"; shift ;;
        --no-cache)     NO_CACHE="--no-cache"; shift ;;
        --load)         DO_LOAD=1; shift ;;
        -h|--help)      usage ;;
        *) echo "未知参数：$1（用 -h 看用法）" >&2; exit 1 ;;
    esac
done

# 去掉可能混进来的空格，免得 "linux/amd64, linux/arm64" 这种写法解析出空架构
PLATFORMS=$(echo "$PLATFORMS" | tr -d ' ')
[ -z "$PLATFORMS" ] && { echo "错误：平台列表为空" >&2; exit 1; }

# --- 1.5 获取当前时区 ---
TZ="${TZ:-$(cat /etc/timezone 2>/dev/null || echo UTC)}"
echo "检测到宿主机时区: $TZ"

# --- 1.6 准备 buildx 构建器 ---
# 多架构构建只有 BuildKit 才做得到，docker build 不行。
if ! docker buildx version >/dev/null 2>&1; then
    echo "错误：未找到 docker buildx，无法构建多架构镜像。" >&2
    echo "  Docker Desktop 自带；Linux 上请安装 docker-buildx-plugin。" >&2
    exit 1
fi

# 当前的构建器如果是 docker 驱动，只有开了 containerd 镜像存储才支持多平台。
# 没开就另起一个 docker-container 驱动的构建器，免得卡在
# "multiple platforms feature is currently not supported for docker driver"。
BUILDER_ARGS=()
if [ "$(docker buildx inspect 2>/dev/null | awk -F': *' '/^Driver:/{print $2}')" = "docker" ] \
   && ! docker info 2>/dev/null | grep -qi "io.containerd.snapshotter"; then
    if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
        echo "当前 docker 驱动不支持多架构，创建构建器 [$BUILDER_NAME]（docker-container 驱动）…"
        docker buildx create --name "$BUILDER_NAME" --driver docker-container >/dev/null
    fi
    BUILDER_ARGS=(--builder "$BUILDER_NAME")
fi

# 构建参数：多架构与单架构两次导出共用，标签必须带上，
# 否则 docker load 后只剩 <none>
BUILD_ARGS=("${BUILDER_ARGS[@]}" --build-arg "TZ=$TZ" \
    -t "$IMAGE_WITH_TAG" -t "$LATEST_TAG" --provenance=false)
[ -n "$NO_CACHE" ] && BUILD_ARGS+=("$NO_CACHE")

# 一共几步：1 次多架构导出 + 每个架构各 1 次单架构导出
TOTAL_STEPS=$(( $(echo "$PLATFORMS" | awk -F',' '{print NF}') + 1 ))

echo "----------------------------------------"
echo "版本:     $VERSION"
echo "标签:     $IMAGE_WITH_TAG , $LATEST_TAG"
echo "架构:     $PLATFORMS"
echo "----------------------------------------"

# --- 2. 多架构单文件归档 ---
echo ""
echo "[1/$TOTAL_STEPS] 构建多架构镜像并导出 OCI 归档 -> $MULTI_FILE"
docker buildx build "${BUILD_ARGS[@]}" --platform "$PLATFORMS" \
    --output "type=oci,dest=$MULTI_FILE" .
PRODUCED=("$MULTI_FILE")

# --- 3. 每个架构各出一个 docker-archive ---
# buildx 会复用上一步的构建缓存，这一步不会重跑编译
i=2
for p in ${PLATFORMS//,/ }; do
    suffix="${p#linux/}"; suffix="${suffix//\//_}"     # linux/arm/v7 -> arm_v7
    out="${REPO_NAME}_${VERSION}_${suffix}.tar"
    echo ""
    echo "[$i/$TOTAL_STEPS] 导出 $p 的 docker-archive -> $out"
    docker buildx build "${BUILD_ARGS[@]}" --platform "$p" \
        --output "type=docker,dest=$out" .
    PRODUCED+=("$out")
    i=$((i + 1))
done

# --- 4. 可选：把本机架构导入本地 docker ---
# 多架构构建走的是 buildx，默认不会把镜像留在本机 docker 里
if [ "$DO_LOAD" = "1" ]; then
    case "$(uname -m)" in
        x86_64|amd64)  HOST_ARCH=amd64 ;;
        aarch64|arm64) HOST_ARCH=arm64 ;;
        *)             HOST_ARCH="" ;;
    esac
    HOST_TAR="${REPO_NAME}_${VERSION}_${HOST_ARCH}.tar"
    if [ -n "$HOST_ARCH" ] && [ -f "$HOST_TAR" ]; then
        echo ""
        echo "[--load] 导入本机架构（$HOST_ARCH）到本地 docker"
        docker load -i "$HOST_TAR"
    else
        echo ""
        echo "[--load] 跳过：本次未导出本机架构（$(uname -m)）的 tar"
    fi
fi

# --- 5. 成功输出 ---
echo ""
echo "----------------------------------------"
echo "打包完成："
for f in "${PRODUCED[@]}"; do
    [ -f "$f" ] && ls -lh "$f" | awk '{print "  " $9 "  " $5}'
done

# 上次用别的架构组合跑过的话，会留下本次没重新生成的 tar，
# 列出来免得被当成这一次的产物（不自动删，用户可能还要用）
stale=()
for f in "${REPO_NAME}_${VERSION}"*.tar; do
    [ -e "$f" ] || continue
    for p in "${PRODUCED[@]}"; do
        [ "$f" = "$p" ] && continue 2
    done
    stale+=("$f")
done
if [ ${#stale[@]} -gt 0 ]; then
    echo ""
    echo "注意：下面这些是之前跑别的架构组合留下的，本次没有重新生成："
    for f in "${stale[@]}"; do echo "  $f"; done
fi

echo ""
echo "多架构通吃（Docker 25+）：docker load -i $MULTI_FILE"
echo "按架构选用（老版本 Docker）：docker load -i ${REPO_NAME}_${VERSION}_<架构>.tar"
echo "----------------------------------------"
