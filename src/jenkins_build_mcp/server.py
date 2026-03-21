"""MCP server entrypoint for Jenkins build tools."""

from __future__ import annotations

import argparse
from pathlib import Path
import os

from mcp.server.fastmcp import FastMCP

from jenkins_build_mcp.config_loader import ServiceConfigStore
from jenkins_build_mcp.env_loader import load_env_file
from jenkins_build_mcp.errors import ConfigError
from jenkins_build_mcp.jenkins_client import JenkinsClient
from jenkins_build_mcp.models import BuildResult, BuildStatus
from jenkins_build_mcp.service import JenkinsBuildService


mcp = FastMCP(
    "Jenkins Build MCP",
    instructions=(
        "Use this server when the user wants to trigger a Jenkins build by service name, "
        "optional site, and optional branch. Call list_services when the service or site is unclear. "
        "Call trigger_build only when the service is known."
    ),
    json_response=True,
    stateless_http=True,
)
_STORE_CACHE: dict[str, ServiceConfigStore] = {}


def _config_path() -> str:
    return os.getenv("SERVICES_CONFIG_PATH", "services.yaml")


def _get_store() -> ServiceConfigStore:
    path = str(Path(_config_path()).resolve())
    store = _STORE_CACHE.get(path)
    if store is None:
        store = ServiceConfigStore(path)
        _STORE_CACHE[path] = store
    return store


def _get_jenkins_client() -> JenkinsClient:
    base_url = os.getenv("JENKINS_BASE_URL")
    user = os.getenv("JENKINS_USER")
    token = os.getenv("JENKINS_API_TOKEN")

    missing = [
        name
        for name, value in (
            ("JENKINS_BASE_URL", base_url),
            ("JENKINS_USER", user),
            ("JENKINS_API_TOKEN", token),
        )
        if not value
    ]
    if missing:
        missing_fields = ", ".join(missing)
        raise ConfigError(f"Missing Jenkins environment variables: {missing_fields}")

    return JenkinsClient(base_url=base_url, user=user, api_token=token)


@mcp.tool()
def list_services() -> list[dict[str, object]]:
    """Use this when you need the allowed Jenkins build services before triggering a build."""
    store = _get_store()
    return [service.public_dict() for service in store.list_enabled_services()]


@mcp.tool()
def trigger_build(service: str, branch: str = "", site: str = "") -> dict[str, object]:
    """Use this when the user explicitly wants to trigger a Jenkins build for a known service. Site is optional unless the same service exists in multiple site variants. Branch is optional for jobs that use only configured build parameters."""
    normalized_service = service.strip()
    normalized_branch = branch.strip()
    normalized_site = site.strip()
    try:
        store = _get_store()
        with _get_jenkins_client() as client:
            app_service = JenkinsBuildService(store, client)
            return app_service.trigger_build(
                normalized_service,
                normalized_branch,
                normalized_site,
            )
    except ConfigError as exc:
        return BuildResult(
            service=normalized_service,
            site=normalized_site,
            branch=normalized_branch,
            job=None,
            jenkins_url=os.getenv("JENKINS_BASE_URL"),
            queue_id=None,
            build_url=None,
            status=BuildStatus.FAILED,
            message=str(exc),
        ).to_dict()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Jenkins Build MCP server.")
    parser.add_argument(
        "--env-file",
        help="Load environment variables from a KEY=VALUE file before starting the server.",
    )
    parser.add_argument(
        "--services-config",
        help="Override SERVICES_CONFIG_PATH for this process.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        help="Override MCP_TRANSPORT for this process.",
    )
    parser.add_argument(
        "--host",
        help="Override MCP_HOST for streamable-http transport.",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Override MCP_PORT for streamable-http transport.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the MCP server."""
    args = _parse_args()
    if args.env_file:
        load_env_file(args.env_file)
    if args.services_config:
        os.environ["SERVICES_CONFIG_PATH"] = args.services_config
    if args.transport:
        os.environ["MCP_TRANSPORT"] = args.transport
    if args.host:
        os.environ["MCP_HOST"] = args.host
    if args.port is not None:
        os.environ["MCP_PORT"] = str(args.port)

    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = int(os.getenv("MCP_PORT", "8000"))
        mcp.run(transport=transport, host=host, port=port)
        return

    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
