"""HTTP client wrapper for Jenkins API operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin
import re
import time

import httpx

from jenkins_build_mcp.errors import (
    JenkinsAuthError,
    JenkinsNotFoundError,
    JenkinsUnavailableError,
)
from jenkins_build_mcp.models import BuildStatus, QueueBuildInfo


QUEUE_ID_PATTERN = re.compile(r"/queue/item/(?P<queue_id>\d+)/?$")


@dataclass(frozen=True)
class JenkinsCrumb:
    """CSRF crumb metadata returned by Jenkins."""

    field_name: str
    value: str


class JenkinsClient:
    """Small client for the subset of Jenkins APIs needed by the MCP server."""

    def __init__(
        self,
        base_url: str,
        user: str,
        api_token: str,
        *,
        timeout: float = 10.0,
        queue_poll_attempts: int = 3,
        queue_poll_interval: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.queue_poll_attempts = queue_poll_attempts
        self.queue_poll_interval = queue_poll_interval
        self._crumb: JenkinsCrumb | None = None
        self._client = httpx.Client(
            base_url=self.base_url,
            auth=(user, api_token),
            follow_redirects=False,
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> "JenkinsClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._client.close()

    def job_url(self, job_path: str) -> str:
        """Return the user-facing Jenkins page URL for a job."""
        normalized_path = self._normalize_job_path(job_path)
        return f"{self.base_url}/{normalized_path}/"

    def trigger_job(
        self, job_path: str, parameters: dict[str, str] | None = None
    ) -> QueueBuildInfo:
        """Trigger a Jenkins build and inspect queue state if available."""
        normalized_path = self._normalize_job_path(job_path)
        endpoint = (
            f"/{normalized_path}/buildWithParameters"
            if parameters
            else f"/{normalized_path}/build"
        )
        headers = self._crumb_headers()
        response = self._send("POST", endpoint, headers=headers, data=parameters)

        queue_url = response.headers.get("Location")
        if not queue_url:
            return QueueBuildInfo(
                queue_id=None,
                queue_url=None,
                build_url=None,
                status=BuildStatus.TRIGGERED,
                message="Build triggered, but Jenkins did not return a queue location.",
            )

        full_queue_url = urljoin(f"{self.base_url}/", queue_url)
        return self.inspect_queue(full_queue_url)

    def inspect_queue(self, queue_url: str) -> QueueBuildInfo:
        """Poll a Jenkins queue item and return the best available build state."""
        queue_id = self._parse_queue_id(queue_url)
        queue_api_url = urljoin(queue_url if queue_url.endswith("/") else f"{queue_url}/", "api/json")
        last_payload: dict[str, Any] | None = None

        for attempt in range(self.queue_poll_attempts):
            response = self._send("GET", queue_api_url)
            payload = self._safe_json(response)
            last_payload = payload

            if payload.get("cancelled"):
                return QueueBuildInfo(
                    queue_id=queue_id,
                    queue_url=queue_url,
                    build_url=None,
                    status=BuildStatus.FAILED,
                    message="Build was cancelled while waiting in Jenkins queue.",
                )

            executable = payload.get("executable") or {}
            build_url = executable.get("url")
            if build_url:
                return QueueBuildInfo(
                    queue_id=queue_id,
                    queue_url=queue_url,
                    build_url=str(build_url),
                    status=BuildStatus.TRIGGERED,
                    message="Build triggered successfully.",
                )

            if attempt < self.queue_poll_attempts - 1:
                time.sleep(self.queue_poll_interval)

        return QueueBuildInfo(
            queue_id=queue_id,
            queue_url=queue_url,
            build_url=None,
            status=BuildStatus.QUEUED,
            message=self._queue_pending_message(last_payload),
        )

    def _crumb_headers(self) -> dict[str, str]:
        if self._crumb is not None:
            return {self._crumb.field_name: self._crumb.value}

        response = self._send("GET", "/crumbIssuer/api/json", allow_not_found=True)
        if response.status_code == 404:
            return {}

        payload = self._safe_json(response)
        field_name = payload.get("crumbRequestField")
        value = payload.get("crumb")
        if not field_name or not value:
            raise JenkinsUnavailableError("Jenkins crumb issuer returned an invalid response.")

        self._crumb = JenkinsCrumb(field_name=str(field_name), value=str(value))
        return {self._crumb.field_name: self._crumb.value}

    def _send(
        self,
        method: str,
        url: str,
        *,
        allow_not_found: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise JenkinsUnavailableError("Jenkins is unavailable.") from exc
        except httpx.HTTPError as exc:
            raise JenkinsUnavailableError("Jenkins is unavailable.") from exc

        if response.status_code in (401, 403):
            raise JenkinsAuthError("Jenkins authentication failed.")
        if response.status_code == 404 and not allow_not_found:
            raise JenkinsNotFoundError("Jenkins job not found or mapping is invalid.")
        if 500 <= response.status_code < 600:
            raise JenkinsUnavailableError("Jenkins is unavailable.")

        return response

    @staticmethod
    def _normalize_job_path(job_path: str) -> str:
        return job_path.strip().strip("/")

    @staticmethod
    def _parse_queue_id(queue_url: str) -> int | None:
        match = QUEUE_ID_PATTERN.search(queue_url)
        if not match:
            return None
        return int(match.group("queue_id"))

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise JenkinsUnavailableError("Jenkins returned an invalid response.") from exc

        if not isinstance(payload, dict):
            raise JenkinsUnavailableError("Jenkins returned an unexpected response payload.")
        return payload

    @staticmethod
    def _queue_pending_message(payload: dict[str, Any] | None) -> str:
        if not payload:
            return "Build is queued in Jenkins."

        why = payload.get("why")
        if why:
            return f"Build is queued in Jenkins: {why}"
        return "Build is queued in Jenkins."
