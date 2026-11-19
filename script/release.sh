#!/usr/bin/env bash
# ============================================================================
#  ZongziBay 发版脚本（macOS / Linux / WSL）
#
#  做三件事：统一版本号 → 提交 → 推到 release 分支。
#  推送后 GitHub Actions 会自动：校验 → 前后端测试 → 构建多架构镜像
#  → 推 Docker Hub → 打 tag → 建 GitHub Release。
#
#  用法：
#    ./script/release.sh 1.0.0-rc.11            # 发版
#    ./script/release.sh v1.0.0-rc.11           # v 前缀会自动去掉
#    ./script/release.sh 1.0.0-rc.11 --dry-run  # 只改文件看 diff，随后还原
#
#  前置条件：
#    - 已切到 release 分支（git switch release）
#    - 工作区干净，没有别的未提交改动
#    - 本机有 node / npm（用来同步 web/package-lock.json）
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

DRY_RUN=false
VERSION=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    -*) echo "未知参数：$arg" >&2; exit 1 ;;
    *) VERSION="$arg" ;;
  esac
done

if [[ -z "$VERSION" ]]; then
  echo "用法：$0 <版本号> [--dry-run]（示例：$0 1.0.0-rc.11）" >&2
  exit 1
fi

echo "=== ZongziBay 发版 ==="

# --- 1. 版本号格式 ---
VERSION="${VERSION#v}"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z][0-9A-Za-z.-]*)?$ ]]; then
  echo "版本号格式不合法：$VERSION（示例：1.0.0、1.0.0-rc.11）" >&2
  exit 1
fi

# --- 2. 必须在 release 分支，且工作区干净 ---
branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" != "release" ]]; then
  echo "当前分支是 [$branch]，发版请先切到 release：git switch release" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "工作区有未提交的改动：" >&2
  git status --short >&2
  echo "先提交或还原这些改动再发版（发版提交里只应该包含版本号）" >&2
  exit 1
fi

# --- 3. 版本号不能被占用（本地 tag 与远端 tag 都查）---
echo "拉取远端 tags ..."
if ! git fetch --tags --quiet; then
  echo "警告：拉取远端 tags 失败（可能没网），继续执行；重复发版会被 Actions 拦下来" >&2
fi
if [[ -n "$(git tag -l "v$VERSION")" ]]; then
  echo "tag v$VERSION 已存在，换个版本号（或先删掉旧 tag）" >&2
  exit 1
fi

old_version="$(tr -d ' \t\r\n' < VERSION)"
if [[ "$old_version" == "$VERSION" ]]; then
  echo "当前版本号已经是 $VERSION，发版请填一个更高的版本号" >&2
  exit 1
fi
echo "版本号：$old_version -> $VERSION"

# --- 4. 改 VERSION + web/package.json + web/package-lock.json ---
printf '%s' "$VERSION" > VERSION
(
  cd web
  npm version "$VERSION" --no-git-tag-version --ignore-scripts --silent >/dev/null
)

# --- 5. DryRun：看完 diff 就还原 ---
if [[ "$DRY_RUN" == "true" ]]; then
  echo ""
  echo "[DryRun] 将要提交的改动："
  git --no-pager diff --stat
  git --no-pager diff
  git checkout -- VERSION web/package.json web/package-lock.json
  echo ""
  echo "[DryRun] 已还原，没有提交"
  exit 0
fi

# --- 6. 提交并推送，剩下的交给 GitHub Actions ---
git add VERSION web/package.json web/package-lock.json
git commit -m "chore(release): v$VERSION"
git push origin release

echo ""
echo "已推送 release 分支。到仓库的 Actions → Release 页面看进度："
echo "  校验版本 → 前后端测试 → 构建 amd64/arm64 → 推 Docker Hub → 打 tag → 建 Release"
