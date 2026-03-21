from pathlib import Path

from jenkins_build_mcp.config_loader import ServiceConfigStore
from jenkins_build_mcp.errors import JenkinsAuthError
from jenkins_build_mcp.models import BuildStatus, QueueBuildInfo
from jenkins_build_mcp.service import JenkinsBuildService


class FakeJenkinsClient:
    def __init__(self) -> None:
        self.base_url = "https://jenkins.example.com"
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def trigger_job(self, job_path: str, parameters: dict[str, str] | None = None) -> QueueBuildInfo:
        self.calls.append((job_path, parameters))
        if "auth-error" in job_path:
            raise JenkinsAuthError("Jenkins authentication failed.")
        return QueueBuildInfo(
            queue_id=42,
            queue_url="https://jenkins.example.com/queue/item/42/",
            build_url="https://jenkins.example.com/job/example/42/",
            status=BuildStatus.TRIGGERED,
            message="Build triggered successfully.",
        )

    def job_url(self, job_path: str) -> str:
        return f"{self.base_url}/{job_path.strip('/')}/"


def _write_config(path: Path) -> None:
    path.write_text(
        """
services:
  - service: order-service
    trigger_type: parameterized
    job_path: job/backend/job/order-service-build
    branch_param_name: BRANCH
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
  - service: payment-service
    trigger_type: branch_in_path
    job_template: job/backend/job/payment-service/job/{branch_double_encoded}
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
  - service: auth-service
    trigger_type: parameterized
    job_path: job/backend/job/auth-error
    branch_param_name: BRANCH
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
  - service: api-auto-test
    trigger_type: parameterized
    job_path: job/api-auto-test
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    build_parameters:
      ENV: fat
    enabled: true
  - service: reabam-file-new-docker
    site: blue
    trigger_type: parameterized
    job_path: job/reabam-file-new-docker
    branch_param_name: app_v
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    build_parameters:
      app_name: reabam-file
      app_port: "9012"
      app_user: reabam
      app_env: fat
      app_jdk_v: jdk21
      app_act: push
    enabled: true
  - service: reabam-file-new-docker
    site: green
    trigger_type: parameterized
    job_path: job/reabam-file-new-docker-green
    branch_param_name: app_v
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    build_parameters:
      app_name: reabam-file
      app_port: "9012"
      app_user: reabam
      app_env: fat
      app_jdk_v: jdk21
      app_act: push
    enabled: true
  - service: disabled-service
    trigger_type: parameterized
    job_path: job/backend/job/disabled-service-build
    branch_param_name: BRANCH
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: false
""".strip(),
        encoding="utf-8",
    )


def test_list_services_returns_enabled_entries_only(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    _write_config(config_path)

    build_service = JenkinsBuildService(ServiceConfigStore(config_path), FakeJenkinsClient())
    services = build_service.list_services()

    assert [item["service"] for item in services] == [
        "api-auto-test",
        "auth-service",
        "order-service",
        "payment-service",
        "reabam-file-new-docker",
        "reabam-file-new-docker",
    ]
    assert [item["site"] for item in services] == [
        None,
        None,
        None,
        None,
        "blue",
        "green",
    ]


def test_trigger_build_parameterized_success(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    _write_config(config_path)
    client = FakeJenkinsClient()
    build_service = JenkinsBuildService(ServiceConfigStore(config_path), client)

    result = build_service.trigger_build("order-service", "feature/demo")

    assert result["status"] == "triggered"
    assert result["job"] == "job/backend/job/order-service-build"
    assert result["site"] == ""
    assert result["queue_id"] == 42
    assert client.calls == [("job/backend/job/order-service-build", {"BRANCH": "feature/demo"})]


def test_trigger_build_branch_in_path_success(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    _write_config(config_path)
    client = FakeJenkinsClient()
    build_service = JenkinsBuildService(ServiceConfigStore(config_path), client)

    result = build_service.trigger_build("payment-service", "release/1.0.0")

    assert result["status"] == "triggered"
    assert result["job"] == "job/backend/job/payment-service/job/release%252F1.0.0"
    assert result["site"] == ""
    assert client.calls == [("job/backend/job/payment-service/job/release%252F1.0.0", None)]


def test_trigger_build_unknown_service_returns_failed(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    _write_config(config_path)

    build_service = JenkinsBuildService(ServiceConfigStore(config_path), FakeJenkinsClient())
    result = build_service.trigger_build("missing-service", "feature/demo")

    assert result["status"] == "failed"
    assert result["message"] == "Service 'missing-service' is not configured for Jenkins builds."
    assert result["site"] == ""


def test_trigger_build_invalid_branch_returns_failed(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    _write_config(config_path)

    build_service = JenkinsBuildService(ServiceConfigStore(config_path), FakeJenkinsClient())
    result = build_service.trigger_build("order-service", "feature/demo?")

    assert result["status"] == "failed"
    assert result["message"] == "Branch 'feature/demo?' does not match the allowed pattern."
    assert result["site"] == ""


def test_trigger_build_auth_failure_returns_failed(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    _write_config(config_path)

    build_service = JenkinsBuildService(ServiceConfigStore(config_path), FakeJenkinsClient())
    result = build_service.trigger_build("auth-service", "feature/demo")

    assert result["status"] == "failed"
    assert result["message"] == "Jenkins authentication failed."
    assert result["site"] == ""


def test_trigger_build_with_fixed_parameters_and_no_branch(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    _write_config(config_path)
    client = FakeJenkinsClient()
    build_service = JenkinsBuildService(ServiceConfigStore(config_path), client)

    result = build_service.trigger_build("api-auto-test")

    assert result["status"] == "triggered"
    assert result["job"] == "job/api-auto-test"
    assert result["site"] == ""
    assert client.calls == [("job/api-auto-test", {"ENV": "fat"})]


def test_trigger_build_with_site_and_branch_parameter(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    _write_config(config_path)
    client = FakeJenkinsClient()
    build_service = JenkinsBuildService(ServiceConfigStore(config_path), client)

    result = build_service.trigger_build(
        "reabam-file-new-docker",
        "origin/develop",
        "blue",
    )

    assert result["status"] == "triggered"
    assert result["site"] == "blue"
    assert result["job"] == "job/reabam-file-new-docker"
    assert client.calls == [
        (
            "job/reabam-file-new-docker",
            {
                "app_name": "reabam-file",
                "app_port": "9012",
                "app_user": "reabam",
                "app_env": "fat",
                "app_jdk_v": "jdk21",
                "app_act": "push",
                "app_v": "origin/develop",
            },
        )
    ]
