"""Local smoke test for the Jenkins Build MCP project."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from jenkins_build_mcp.config_loader import ServiceConfigStore
from jenkins_build_mcp.jenkins_client import JenkinsClient
from jenkins_build_mcp.service import JenkinsBuildService


def main() -> None:
    with TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "services.yaml"
        config_path.write_text(
            """
services:
  - service: order-service
    trigger_type: parameterized
    job_path: job/backend/job/order-service-build
    branch_param_name: BRANCH
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
  - service: reabam-file-new-docker
    site: blue
    trigger_type: parameterized
    job_path: job/reabam-file-new-docker
    branch_param_name: app_v
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    build_parameters:
      app_name: reabam-file
      app_env: fat
    enabled: true
""".strip(),
            encoding="utf-8",
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/crumbIssuer/api/json":
                return httpx.Response(
                    200,
                    json={"crumbRequestField": "Jenkins-Crumb", "crumb": "crumb-value"},
                )
            if request.url.path == "/job/backend/job/order-service-build/buildWithParameters":
                return httpx.Response(
                    201,
                    headers={"Location": "https://jenkins.example.com/queue/item/42/"},
                )
            if request.url.path == "/job/reabam-file-new-docker/buildWithParameters":
                return httpx.Response(
                    201,
                    headers={"Location": "https://jenkins.example.com/queue/item/43/"},
                )
            if request.url.path == "/queue/item/42/api/json":
                return httpx.Response(
                    200,
                    json={
                        "id": 42,
                        "executable": {
                            "url": "https://jenkins.example.com/job/backend/job/order-service-build/153/"
                        },
                    },
                )
            if request.url.path == "/queue/item/43/api/json":
                return httpx.Response(
                    200,
                    json={
                        "id": 43,
                        "executable": {
                            "url": "https://jenkins.example.com/job/reabam-file-new-docker/7/"
                        },
                    },
                )
            return httpx.Response(404)

        store = ServiceConfigStore(config_path)
        client = JenkinsClient(
            base_url="https://jenkins.example.com",
            user="tester",
            api_token="token",
            transport=httpx.MockTransport(handler),
            queue_poll_interval=0,
        )
        service = JenkinsBuildService(store, client)

        services = service.list_services()
        assert [item["service"] for item in services] == ["order-service", "reabam-file-new-docker"]

        order_result = service.trigger_build("order-service", "feature/demo")
        assert order_result["status"] == "triggered"
        assert order_result["queue_id"] == 42

        site_result = service.trigger_build("reabam-file-new-docker", "origin/develop", "blue")
        assert site_result["status"] == "triggered"
        assert site_result["queue_id"] == 43
        assert site_result["site"] == "blue"

        print("Local smoke test passed.")


if __name__ == "__main__":
    main()
