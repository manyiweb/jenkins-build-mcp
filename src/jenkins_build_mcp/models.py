"""Core models for service config and build results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import quote
import re

from jenkins_build_mcp.errors import BuildValidationError, ConfigError


class JenkinsTriggerMode(StrEnum):
    """Supported Jenkins trigger patterns."""

    PARAMETERIZED = "parameterized"
    BRANCH_IN_PATH = "branch_in_path"


class BuildStatus(StrEnum):
    """User-facing build trigger status."""

    QUEUED = "queued"
    TRIGGERED = "triggered"
    FAILED = "failed"


@dataclass(frozen=True)
class BuildRequest:
    """Request parameters exposed by the MCP tool."""

    service: str
    branch: str
    site: str = ""


@dataclass(frozen=True)
class ServiceConfig:
    """Configuration for a single buildable service."""

    service: str
    trigger_type: JenkinsTriggerMode
    allowed_branch_pattern: str
    enabled: bool = True
    site: str | None = None
    job_path: str | None = None
    job_template: str | None = None
    branch_param_name: str | None = None
    build_parameters: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.service.strip():
            raise ConfigError("Service name cannot be empty.")

        if self.trigger_type is JenkinsTriggerMode.PARAMETERIZED:
            if not self.job_path:
                raise ConfigError(
                    f"Service '{self.service}' must define job_path for parameterized builds."
                )
            if not self.branch_param_name and not self.build_parameters:
                raise ConfigError(
                    f"Service '{self.service}' must define branch_param_name or build_parameters for parameterized builds."
                )

        if self.trigger_type is JenkinsTriggerMode.BRANCH_IN_PATH and not self.job_template:
            raise ConfigError(
                f"Service '{self.service}' must define job_template for branch_in_path builds."
            )

        try:
            re.compile(self.allowed_branch_pattern)
        except re.error as exc:
            raise ConfigError(
                f"Service '{self.service}' has an invalid allowed_branch_pattern: {exc}"
            ) from exc

    def validate_branch(self, branch: str) -> str:
        """Return a normalized branch name or raise validation error."""
        normalized = branch.strip()
        if not normalized:
            raise BuildValidationError("Branch name cannot be empty.")

        if not re.fullmatch(self.allowed_branch_pattern, normalized):
            raise BuildValidationError(
                f"Branch '{normalized}' does not match the allowed pattern."
            )

        return normalized

    def resolve_trigger(self, branch: str) -> tuple[str, dict[str, str] | None]:
        """Resolve Jenkins path and optional build parameters for a branch."""
        if self.trigger_type is JenkinsTriggerMode.PARAMETERIZED:
            assert self.job_path is not None
            parameters = dict(self.build_parameters or {})
            if self.branch_param_name:
                normalized_branch = self.validate_branch(branch)
                parameters[self.branch_param_name] = normalized_branch
            return self.job_path, parameters or None

        assert self.job_template is not None
        normalized_branch = self.validate_branch(branch)
        branch_encoded = quote(normalized_branch, safe="")
        branch_double_encoded = quote(branch_encoded, safe="")
        path = self.job_template.format(
            branch=normalized_branch,
            branch_encoded=branch_encoded,
            branch_double_encoded=branch_double_encoded,
        )
        return path, None

    def public_dict(self) -> dict[str, Any]:
        """Return the safe metadata exposed by list_services()."""
        return {
            "service": self.service,
            "site": self.site,
            "trigger_type": self.trigger_type.value,
            "allowed_branch_pattern": self.allowed_branch_pattern,
            "branch_param_name": self.branch_param_name,
            "default_parameters": self.build_parameters or {},
            "job": self.job_path or self.job_template,
        }


@dataclass(frozen=True)
class QueueBuildInfo:
    """Resolved build state after hitting Jenkins queue."""

    queue_id: int | None
    queue_url: str | None
    build_url: str | None
    status: BuildStatus
    message: str


@dataclass(frozen=True)
class BuildResult:
    """Fixed user-facing response shape for trigger_build()."""

    service: str
    site: str
    branch: str
    job: str | None
    jenkins_url: str | None
    queue_id: int | None
    build_url: str | None
    status: BuildStatus
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable output."""
        return {
            "service": self.service,
            "site": self.site,
            "branch": self.branch,
            "job": self.job,
            "jenkins_url": self.jenkins_url,
            "queue_id": self.queue_id,
            "build_url": self.build_url,
            "status": self.status.value,
            "message": self.message,
        }
