from pathlib import Path

from jenkins_build_mcp.config_loader import ServiceConfigStore


def test_list_enabled_services_only(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    config_path.write_text(
        """
services:
  - service: order-service
    trigger_type: parameterized
    job_path: job/backend/job/order-service-build
    branch_param_name: BRANCH
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
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

    store = ServiceConfigStore(config_path)
    services = store.list_enabled_services()

    assert [service.service for service in services] == ["order-service"]
    assert [service.site for service in services] == [None]


def test_store_reloads_when_file_changes(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    config_path.write_text(
        """
services:
  - service: order-service
    trigger_type: parameterized
    job_path: job/backend/job/order-service-build
    branch_param_name: BRANCH
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
""".strip(),
        encoding="utf-8",
    )

    store = ServiceConfigStore(config_path)
    assert [service.service for service in store.list_enabled_services()] == ["order-service"]

    config_path.write_text(
        """
services:
  - service: payment-service
    trigger_type: branch_in_path
    job_template: job/backend/job/payment-service/job/{branch_double_encoded}
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
""".strip(),
        encoding="utf-8",
    )

    assert [service.service for service in store.list_enabled_services()] == ["payment-service"]


def test_parameterized_service_can_use_fixed_parameters_without_branch(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    config_path.write_text(
        """
services:
  - service: api-auto-test
    trigger_type: parameterized
    job_path: job/api-auto-test
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    build_parameters:
      ENV: fat
    enabled: true
""".strip(),
        encoding="utf-8",
    )

    store = ServiceConfigStore(config_path)
    service = store.get_service("api-auto-test")
    job_path, parameters = service.resolve_trigger("")

    assert job_path == "job/api-auto-test"
    assert parameters == {"ENV": "fat"}


def test_service_requires_site_when_multiple_variants_exist(tmp_path: Path) -> None:
    config_path = tmp_path / "services.yaml"
    config_path.write_text(
        """
services:
  - service: reabam-file-new-docker
    site: blue
    trigger_type: parameterized
    job_path: job/reabam-file-new-docker
    branch_param_name: app_v
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
  - service: reabam-file-new-docker
    site: green
    trigger_type: parameterized
    job_path: job/reabam-file-new-docker-green
    branch_param_name: app_v
    allowed_branch_pattern: "^[A-Za-z0-9._/-]+$"
    enabled: true
""".strip(),
        encoding="utf-8",
    )

    store = ServiceConfigStore(config_path)

    try:
        store.get_service("reabam-file-new-docker")
    except Exception as exc:
        assert str(exc) == (
            "Service 'reabam-file-new-docker' requires site selection. Available sites: blue, green."
        )
    else:
        raise AssertionError("Expected site selection error")
