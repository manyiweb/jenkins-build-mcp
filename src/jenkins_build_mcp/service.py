"""Application service that bridges config validation and Jenkins API calls."""

from __future__ import annotations

from jenkins_build_mcp.config_loader import ServiceConfigStore
from jenkins_build_mcp.errors import BuildValidationError, ConfigError, JenkinsError
from jenkins_build_mcp.jenkins_client import JenkinsClient
from jenkins_build_mcp.models import BuildRequest, BuildResult, BuildStatus, ServiceConfig


class JenkinsBuildService:
    """High-level build operations exposed by the MCP server."""

    def __init__(self, config_store: ServiceConfigStore, jenkins_client: JenkinsClient) -> None:
        self.config_store = config_store
        self.jenkins_client = jenkins_client

    def list_services(self) -> list[dict[str, object]]:
        """Return enabled services in a model-friendly format."""
        return [service.public_dict() for service in self.config_store.list_enabled_services()]

    def trigger_build(self, service: str, branch: str = "", site: str = "") -> dict[str, object]:
        """Validate request, trigger Jenkins, and normalize error reporting."""
        request = BuildRequest(service=service.strip(), branch=branch.strip(), site=site.strip())
        resolved_config: ServiceConfig | None = None
        resolved_job: str | None = None

        try:
            resolved_config = self.config_store.get_service(request.service, request.site)
            resolved_job, parameters = resolved_config.resolve_trigger(request.branch)
            queue_info = self.jenkins_client.trigger_job(resolved_job, parameters)
            return BuildResult(
                service=request.service,
                site=request.site,
                branch=request.branch,
                job=resolved_job,
                jenkins_url=self.jenkins_client.job_url(resolved_job),
                queue_id=queue_info.queue_id,
                build_url=queue_info.build_url,
                status=queue_info.status,
                message=queue_info.message,
            ).to_dict()
        except (ConfigError, BuildValidationError, JenkinsError) as exc:
            job_value = resolved_job
            if job_value is None and resolved_config is not None and resolved_config.job_path:
                job_value = resolved_config.job_path

            jenkins_url = None
            if resolved_job is not None:
                jenkins_url = self.jenkins_client.job_url(resolved_job)
            elif resolved_config is not None and resolved_config.job_path:
                jenkins_url = self.jenkins_client.job_url(resolved_config.job_path)
            else:
                jenkins_url = self.jenkins_client.base_url

            return BuildResult(
                service=request.service,
                site=request.site,
                branch=request.branch,
                job=job_value,
                jenkins_url=jenkins_url,
                queue_id=None,
                build_url=None,
                status=BuildStatus.FAILED,
                message=str(exc),
            ).to_dict()
