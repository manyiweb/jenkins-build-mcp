# Jenkins Build MCP

A standalone Python MCP server for triggering Jenkins builds by service, site, and branch.

## Features

- `list_services()`
- `trigger_build(service, branch="", site="")`
- Supports `parameterized` Jenkins jobs
- Supports `branch_in_path` Jenkins jobs
- Supports multi-site service variants such as `blue` and `green`
- Supports fixed Jenkins parameters plus a branch parameter such as `app_v`

## Install

```bash
pip install .
```

From Git:

```bash
pip install git+https://your.git.server/your-team/jenkins-build-mcp.git
```

After installation:

```bash
jenkins-build-mcp --help
```

## Configuration

Copy `.env.example` to `.env.local` and fill in real values.

Copy one of the example service mappings to `services.yaml`:

- `services.example.yaml`
- `services.company.example.yaml`

## Run

Stdio transport:

```bash
jenkins-build-mcp --env-file .env.local
```

HTTP transport:

```bash
jenkins-build-mcp --env-file .env.local --transport streamable-http --host 0.0.0.0 --port 8000
```

## Service Mapping

Simple branch-based mapping:

```yaml
services:
  - service: order-service
    trigger_type: parameterized
    job_path: job/backend/job/order-service-build
    branch_param_name: BRANCH
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
```

Company-style site-aware mapping where branch goes into `app_v`:

```yaml
services:
  - service: reabam-retail-blue
    site: blue
    trigger_type: parameterized
    job_path: job/reabam-retail-new-docker
    branch_param_name: app_v
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
```

If the Jenkins job already has correct default selections for the other parameters, the MCP can send only `app_v` and rely on Jenkins defaults for the rest.

For the blue-site retail example you provided, this means a user request such as:

```text
Build blue retail from origin/develop
```

maps to:

```json
{
  "service": "reabam-retail-blue",
  "branch": "origin/develop"
}
```

and Jenkins receives `app_v=origin/develop`.

If you want stricter reproducibility, inspect the job once and add fixed values under `build_parameters`.

If your Jenkins base URL is under a path such as `http://192.168.1.200:8080/jenkins`, set:

```bash
JENKINS_BASE_URL=http://192.168.1.200:8080/jenkins
```

Then use only the relative job path in config:

```yaml
job_path: job/reabam-retail-new-docker
```

## Codex Config

Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.jenkinsBuild]
command = "jenkins-build-mcp"
args = ["--env-file", "C:/path/to/jenkins-build-mcp/.env.local"]
```

## Package Build

```bash
pip install -e ".[dev]"
python -m build
```

## Tests

```bash
pytest
python scripts/local_smoke_test.py
```

## Security Notes

- Do not commit `.env.local`
- Do not commit real Jenkins tokens
- Prefer a service account with minimum required Jenkins permissions
