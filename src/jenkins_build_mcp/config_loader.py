"""Load and cache service configuration from YAML."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from jenkins_build_mcp.errors import ConfigError
from jenkins_build_mcp.models import JenkinsTriggerMode, ServiceConfig


class ServiceConfigStore:
    """YAML-backed configuration store with mtime-based reloads."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._cached_signature: tuple[int, int] | None = None
        self._cached_services: dict[tuple[str, str], ServiceConfig] = {}

    def list_enabled_services(self) -> list[ServiceConfig]:
        """Return enabled services ordered by service name."""
        self._load_if_needed()
        return sorted(
            (service for service in self._cached_services.values() if service.enabled),
            key=lambda service: (service.service, service.site or ""),
        )

    def get_service(self, service_name: str, site_name: str = "") -> ServiceConfig:
        """Return a configured enabled service or raise ConfigError."""
        self._load_if_needed()
        normalized = service_name.strip()
        normalized_site = site_name.strip()

        if normalized_site:
            # 精确匹配
            service = self._cached_services.get((normalized, normalized_site))
            if service and service.enabled:
                return service
            # 通配符回退：("*", site)
            wildcard = self._cached_services.get(("*", normalized_site))
            if wildcard and wildcard.enabled:
                return self._expand_wildcard(wildcard, normalized)
            raise ConfigError(
                f"Service '{normalized}' with site '{normalized_site}' is not configured for Jenkins builds."
            )

        # 无站点：先精确匹配（排除带 site 的条目）
        exact_matches = [
            service
            for service in self._cached_services.values()
            if service.enabled and service.service == normalized and not service.site
        ]
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(exact_matches) > 1:
            available_sites = ", ".join(sorted(service.site or "<default>" for service in exact_matches))
            raise ConfigError(
                f"Service '{normalized}' requires site selection. Available sites: {available_sites}."
            )

        # 通配符回退：("*", "")
        wildcard = self._cached_services.get(("*", ""))
        if wildcard and wildcard.enabled:
            return self._expand_wildcard(wildcard, normalized)

        raise ConfigError(f"Service '{normalized}' is not configured for Jenkins builds.")

    def _expand_wildcard(self, config: ServiceConfig, service_name: str) -> ServiceConfig:
        """将通配符配置中的 {service} 占位符替换为实际服务名，返回新实例。"""
        job_path = config.job_path.replace("{service}", service_name) if config.job_path else None
        job_template = config.job_template.replace("{service}", service_name) if config.job_template else None
        return replace(config, service=service_name, job_path=job_path, job_template=job_template)

    def _load_if_needed(self) -> None:
        if not self.path.exists():
            raise ConfigError(
                f"Service config file '{self.path}' does not exist. Set SERVICES_CONFIG_PATH correctly."
            )

        stat = self.path.stat()
        current_signature = (stat.st_mtime_ns, stat.st_size)
        if self._cached_signature == current_signature:
            return

        raw_data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw_data, dict):
            raise ConfigError("Service config must be a YAML object.")

        services_data = raw_data.get("services", [])
        if not isinstance(services_data, list):
            raise ConfigError("The 'services' field must be a list.")

        parsed_services: dict[tuple[str, str], ServiceConfig] = {}
        for index, service_data in enumerate(services_data):
            config = self._parse_service(service_data, index)
            key = (config.service, config.site or "")
            if key in parsed_services:
                raise ConfigError(
                    f"Duplicate service config found for service '{config.service}' and site '{config.site or '<default>'}'."
                )
            parsed_services[key] = config

        self._cached_services = parsed_services
        self._cached_signature = current_signature

    def _parse_service(self, raw: Any, index: int) -> ServiceConfig:
        if not isinstance(raw, dict):
            raise ConfigError(f"services[{index}] must be an object.")

        try:
            trigger_type = JenkinsTriggerMode(raw["trigger_type"])
        except KeyError as exc:
            raise ConfigError(f"services[{index}] is missing required field 'trigger_type'.") from exc
        except ValueError as exc:
            raise ConfigError(
                f"services[{index}] has unsupported trigger_type '{raw.get('trigger_type')}'."
            ) from exc

        try:
            return ServiceConfig(
                service=str(raw["service"]),
                trigger_type=trigger_type,
                allowed_branch_pattern=str(raw["allowed_branch_pattern"]),
                enabled=bool(raw.get("enabled", True)),
                site=self._optional_str(raw.get("site")),
                job_path=self._optional_str(raw.get("job_path")),
                job_template=self._optional_str(raw.get("job_template")),
                branch_param_name=self._optional_str(raw.get("branch_param_name")),
                build_parameters=self._optional_dict(raw.get("build_parameters")),
            )
        except KeyError as exc:
            raise ConfigError(
                f"services[{index}] is missing required field '{exc.args[0]}'."
            ) from exc

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _optional_dict(value: Any) -> dict[str, str] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ConfigError("build_parameters must be a YAML object.")
        return {str(key): str(item) for key, item in value.items()}
