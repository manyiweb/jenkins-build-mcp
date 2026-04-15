# Jenkins Build MCP

一个用于通过服务名、站点和分支触发 Jenkins 构建的 MCP 服务器。

## 快速开始

### 1. 配置 MCP Server

在 Claude Code 的配置文件中添加 MCP server 配置：

**Windows:** `C:\Users\你的用户名\.claude.json`  
**Mac/Linux:** `~/.claude.json`

参考 [mcp-config.example.json](mcp-config.example.json)，在 `mcpServers` 字段中添加：

```json
{
  "mcpServers": {
    "jenkinsBuild": {
      "command": "uvx",
      "args": [
        "--from", "git+ssh://git@github.com/manyiweb/jenkins-build-mcp.git",
        "jenkins-build-mcp"
      ],
      "env": {
        "JENKINS_BASE_URL": "http://your-jenkins-server:8080/jenkins",
        "JENKINS_USER": "your-username",
        "JENKINS_API_TOKEN": "your-api-token-here"
      },
      "type": "stdio"
    }
  }
}
```

**配置说明：**
- `JENKINS_BASE_URL`: Jenkins 服务器地址（包含路径，如 `/jenkins`）
- `JENKINS_USER`: Jenkins 用户名
- `JENKINS_API_TOKEN`: Jenkins API Token（在 Jenkins 用户设置中生成）

> 无需手动安装或 clone 仓库，`uvx` 会自动从 GitHub 拉取代码并运行。  
> 服务配置（services.yaml）已内置在包中，开箱即用。

### 2. 重启 Claude Code

配置完成后重启 Claude Code，MCP server 即可生效。

### 3. 使用

在 Claude Code 中直接说：
- "帮我构建 dock 服务 dev 分支"
- "发布 retail 绿站点 3.16 分支"

**自动映射规则：**
- `dev` → `origin/develop`
- `316` / `3.16` → `origin/hotfix/pro_2603.16.02`
- `蓝` / `blue` → blue 站点
- `绿` / `green` → green 站点

## 功能特性

- ✅ 列出可用服务：`list_services()`
- ✅ 触发构建：`trigger_build(service, branch, site)`
- ✅ 支持参数化构建（parameterized）
- ✅ 支持分支路径构建（branch_in_path）
- ✅ 支持多站点服务（blue/green/h5）
- ✅ 自动分支名和站点名映射

## 服务配置详解

### 基础配置

```yaml
services:
  - service: order-service          # 服务名
    trigger_type: parameterized     # 构建类型
    job_path: job/backend/job/order-service-build  # Jenkins 任务路径
    branch_param_name: BRANCH       # 分支参数名
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"  # 分支名校验正则
    enabled: true                   # 是否启用
```

### 多站点配置

```yaml
services:
  - service: retail
    site: blue
    trigger_type: parameterized
    job_path: job/reabam-retail-new-docker
    branch_param_name: app_v
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
    
  - service: retail
    site: green
    trigger_type: parameterized
    job_path: job/reabam-retail-new-docker
    branch_param_name: app_v
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
```

### 固定参数配置

如果需要传递固定的构建参数：

```yaml
services:
  - service: my-service
    trigger_type: parameterized
    job_path: job/my-service-build
    branch_param_name: BRANCH
    build_parameters:
      ENV: production
      DEPLOY: "true"
    enabled: true
```

## 开发

### 本地安装

```bash
git clone https://github.com/manyiweb/jenkins-build-mcp.git
cd jenkins-build-mcp
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest
python scripts/local_smoke_test.py
```

### 构建发布

```bash
python -m build
```

## 安全提示

- ⚠️ 不要将 Jenkins API Token 提交到 Git
- ⚠️ 建议使用专门的服务账号，仅授予必要的 Jenkins 权限
- ⚠️ `.claude.json` 包含敏感信息，确保文件权限正确

## 故障排查

**MCP 无法连接？**
- 检查 `.claude.json` 配置是否正确
- 确认本机已安装 `uv`（`uvx` 依赖它）：`pip install uv`
- 确认 SSH key 已配置（用于访问 GitHub 仓库）
- 重启 Claude Code

**构建失败？**
- 检查 Jenkins URL、用户名、Token 是否正确
- 确认 `services.yaml` 中的 `job_path` 与 Jenkins 任务路径一致
- 查看 Jenkins 任务是否启用参数化构建

**分支名不对？**
- 服务器会自动转换 `dev` → `origin/develop`
- 日期格式会自动转换为 hotfix 分支
- 其他分支名原样传递

## License

MIT
