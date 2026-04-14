"""MCP server entrypoint for Jenkins build tools."""

from __future__ import annotations

import argparse
import re
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
        "Call trigger_build only when the service is known.\n\n"
        "## Branch and site mapping\n"
        "The server automatically converts shorthand inputs:\n"
        "- Branch: 'dev' → 'origin/develop', date like '316'/'3.16' → 'origin/hotfix/pro_2603.16.02'\n"
        "- Site: '蓝'/'blue' → blue, '绿'/'green' → green, 'h5' → h5\n"
        "Pass the user's input directly — no pre-processing needed.\n\n"
        "## Service name rules\n"
        "The service name is used directly in the Jenkins job path pattern "
        "'reabam-{service}-new-docker'. Pass the exact service name as it appears in the job."
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


def _normalize_branch(raw: str) -> str:
    """Convert shorthand branch input to the actual Jenkins branch name."""
    raw = raw.strip()
    if not raw:
        return raw
    # dev / develop → origin/develop
    if raw.lower() in ("dev", "develop"):
        return "origin/develop"
    # Date formats: '316', '3.16', '330', '3.30', '415', '4.15' etc.
    m = re.match(r"^(\d{1,2})\.?(\d{1,2})$", raw)
    if m:
        month = int(m.group(1))
        day = int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"origin/hotfix/pro_26{month:02d}.{day:02d}.02"
    return raw


def _normalize_site(raw: str) -> str:
    """Convert Chinese / shorthand site input to the standard site parameter."""
    raw = raw.strip()
    if not raw:
        return raw
    mapping = {
        "蓝": "blue", "蓝站点": "blue", "blue": "blue",
        "绿": "green", "绿站点": "green", "green": "green",
        "h5": "h5",
    }
    return mapping.get(raw.lower(), raw)


@mcp.tool()
def trigger_build(service: str, branch: str = "", site: str = "") -> dict[str, object]:
    """Use this when the user explicitly wants to trigger a Jenkins build for a known service. Site is optional unless the same service exists in multiple site variants. Branch is optional for jobs that use only configured build parameters."""
    normalized_service = service.strip()
    normalized_branch = _normalize_branch(branch)
    normalized_site = _normalize_site(site)
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
