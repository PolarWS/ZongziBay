# 发版说明

ZongziBay 的打包发布由 GitHub Actions 全自动完成：**推送到 `release` 分支即发版**，
构建好的多架构镜像发布到 [polarws/zongzibay](https://hub.docker.com/r/polarws/zongzibay)，
同时自动打 tag、创建 GitHub Release。

流水线定义在 [`.github/workflows/release.yml`](../.github/workflows/release.yml)。

---

## 分支约定

| 分支 | 用途 | 触发的工作流 |
| --- | --- | --- |
| `develop` | 日常开发 | `Tests`：后端 pytest + 前端 vitest |
| `main` | 稳定代码 | `Tests` |
| `release` | 发版专用 | `Release`：测试 → 构建 → 推 Docker Hub → 打 tag → 建 Release |

发版前把要发布的代码合进 `release`（通常从 `main` 或 `develop` 合并），再升版本号推送。

---

## 一次性配置

1. Docker Hub → Account Settings → Security → **New Access Token**，
   权限选 **Read & Write**（不要用账号密码）。
2. 仓库 Settings → Secrets and variables → Actions → New repository secret，添加两个：

   | Secret | 值 |
   | --- | --- |
   | `DOCKERHUB_USERNAME` | Docker Hub 用户名（本项目是 `polarws`） |
   | `DOCKERHUB_TOKEN` | 上一步生成的 Access Token |

3. 首次推送发版分支：

   ```bash
   git push -u origin release
   ```

4. 建议在 Settings → Branches 里给 `release` 加保护：只允许通过 PR 或合并进入。

---

## 发一个版本

### 1. 升版本号并推送（本地一条命令）

```powershell
# Windows
.\script\release.ps1 1.0.0-rc.11
```

```bash
# macOS / Linux / WSL
./script/release.sh 1.0.0-rc.11
```

脚本会：

1. 检查当前在 `release` 分支、工作区干净、`v1.0.0-rc.11` 这个 tag 还没被占用；
2. 把 `VERSION`、`web/package.json`、`web/package-lock.json` 的版本号统一改成新版本；
3. 提交 `chore(release): v1.0.0-rc.11` 并推送到 `release` 分支。

只想看看会改什么、不提交：加 `--dry-run`（PowerShell 是 `-DryRun`）。

### 2. CI 自动完成的部分

推送后 `Release` 工作流依次执行：

1. **校验版本号**：`VERSION`、`web/package.json`、`web/package-lock.json`（两处）
   必须完全一致；tag 不能已经指向别的提交（防止重复发同一版）。
2. **测试门禁**：后端 `pytest` + 前端 `vitest`，任一失败直接终止，不会动 Docker Hub。
3. **多架构构建**：`linux/amd64` + `linux/arm64`（arm64 走 QEMU 模拟），
   推送两个标签：`1.0.0-rc.11` 和 `latest`。
4. **校验 manifest**：确认推送后的镜像里两种架构都在。
5. **打 tag**：自动创建并推送 `v1.0.0-rc.11`（提交信息为 `ZongziBay v1.0.0-rc.11`）。
6. **建 Release**：自动生成变更说明；版本号里带 `-` 的自动勾选 **Pre-release**，
   并在正文追加 Docker 拉取命令。

因为 tag 是在镜像推送成功之后才创建，构建失败不会留下“有 tag 没镜像”的版本；
同一版本可以在修好问题后重复推送重跑。

### 3. 用户侧拉取

```bash
docker pull polarws/zongzibay:latest        # 最新发布
docker pull polarws/zongzibay:1.0.0-rc.11   # 固定版本
```

---

## 手动 / 补发

| 场景 | 做法 |
| --- | --- |
| 重跑当前 `release` 分支上的版本 | Actions → Release → Run workflow，版本号留空 |
| 指定版本重发 | 填版本号（必须与仓库里的 `VERSION` 一致），否则校验会失败 |
| 从某个历史提交补发 | 给该提交推一个 `v*` tag，走同一套流程 |
| 只想重跑测试 | Actions → Tests → Run workflow |

注意：**版本号不能复用**。tag 已经指向别的提交流水线会直接报错，
请先升版本号（`script/release.ps1 1.0.0-rc.12`）。

---

## 回滚

Docker Hub 上的 `latest` 始终指向最近一次成功发版。要回滚：

1. 把要回滚到的旧版本代码合回 `release`；
2. 用一个**更高的版本号**重新发版（例如线上是 `1.0.0-rc.12` 出问题，回滚到 `rc.11` 的代码，
   但仍以 `1.0.0-rc.13` 发布）。

不建议在 Docker Hub 上手动改 tag，容易和仓库里的 tag、Release 对不上。

---

## 常见问题

**`DOCKERHUB_TOKEN` 登录失败**
Secret 没配、token 没给 Read & Write、或者 token 过期。重新生成并在仓库里更新。

**版本号不一致**
工作流会打印每个文件的当前值。跑一遍 `script/release.ps1 <版本>` 统一，
或者手动把 `VERSION`、`web/package.json`、`web/package-lock.json`（`version` 与
`packages[""].version` 两处）改成同一个值。

**`tag vX 已存在于 <commit>`**
这个版本发过了，换版本号。

**arm64 构建很慢**
QEMU 模拟 arm64 本来就慢，首次构建 20~40 分钟属正常，之后有 GHA 缓存会快很多。
`publish` 任务设了 120 分钟超时。

**NAS 上拉取报 `no matching manifest for linux/amd64`**
镜像是多架构 manifest list，老版本 Docker 对 `unknown/unknown` 条目兼容不好。
工作流里已经用 `provenance: false` 规避；如果还遇到，升级 NAS 上的 Docker，
或者改用 `script/build_package.ps1` 生成离线 tar 包导入。

**为什么只有一个 `Release` 工作流了？**
原来的 `docker-publish.yml` 已合并进 `release.yml`：同一份构建逻辑同时支持
“推分支”和“推 tag”，避免同一个 tag 触发两次重复构建。
