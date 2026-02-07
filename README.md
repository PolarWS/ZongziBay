## 启动命令
```bash
conda activate ZongziBay
$env:APP_ENV="prod"
python -m app.main
```

http://localhost:8000/docs
http://127.0.0.1.nip.io:8000/

## Docker 部署指南

本指引适用于使用打包好的镜像文件（如 `zongzibay_latest.tar`）进行部署。

### 1. 导入镜像
在目标机器上执行以下命令导入镜像：
```bash
docker load -i zongzibay_latest.tar
```

### 2. 准备配置目录
在运行容器的目录下创建一个 `config` 文件夹，用于存放配置文件和数据库，确保数据持久化。
```bash
mkdir config
```
*注：容器首次启动时会自动在 `config` 目录下生成 `config.yml` 和数据库文件。*

### 3. 启动容器
执行以下命令启动服务：

**Linux/Mac:**
```bash
docker run -d \
  --name zongzibay \
  --restart unless-stopped \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  zongzibay:latest
```

**Windows (PowerShell):**
```powershell
docker run -d `
  --name zongzibay `
  --restart unless-stopped `
  -p 8000:8000 `
  -v ${PWD}/config:/app/config `
  zongzibay:latest
```

### 部署要点
1.  **数据持久化 (`-v`)**：必须挂载 `/app/config` 目录，否则重启容器后，数据库 (`ZongziBay.db`) 和配置文件修改将会丢失。
2.  **端口映射 (`-p`)**：默认端口为 `8000`。如果需要修改外部访问端口，请修改 `-p` 参数（例如 `-p 9000:8000`）。
3.  **配置文件**: 容器启动后，您可以随时修改挂载目录 (`config/config.yml`) 中的配置，重启容器 (`docker restart zongzibay`) 后生效。
