import httpx
import pytest

from jenkins_build_mcp.errors import (
    JenkinsAuthError,
    JenkinsNotFoundError,
    JenkinsUnavailableError,
)
from jenkins_build_mcp.jenkins_client import JenkinsClient
from jenkins_build_mcp.models import BuildStatus


def test_trigger_parameterized_build_returns_build_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/crumbIssuer/api/json":
            return httpx.Response(
                200,
                json={"crumbRequestField": "Jenkins-Crumb", "crumb": "crumb-value"},
            )
        if request.url.path == "/job/backend/job/order-service-build/buildWithParameters":
            assert request.headers["Jenkins-Crumb"] == "crumb-value"
            return httpx.Response(
                201,
                headers={"Location": "https://jenkins.example.com/queue/item/42/"},
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
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = JenkinsClient(
        base_url="https://jenkins.example.com",
        user="tester",
        api_token="token",
        transport=httpx.MockTransport(handler),
        queue_poll_interval=0,
    )

    result = client.trigger_job(
        "job/backend/job/order-service-build",
        {"BRANCH": "feature/demo"},
    )

    assert result.queue_id == 42
    assert result.build_url == "https://jenkins.example.com/job/backend/job/order-service-build/153/"
    assert result.status is BuildStatus.TRIGGERED
    assert result.message == "Build triggered successfully."


def test_trigger_branch_path_build_returns_queued_when_executable_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/crumbIssuer/api/json":
            return httpx.Response(404)
        if request.url.path == "/job/backend/job/payment-service/job/release%252F1.0.0/build":
            return httpx.Response(
                201,
                headers={"Location": "https://jenkins.example.com/queue/item/77/"},
            )
        if request.url.path == "/queue/item/77/api/json":
            return httpx.Response(200, json={"id": 77, "why": "Waiting for next available executor"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = JenkinsClient(
        base_url="https://jenkins.example.com",
        user="tester",
        api_token="token",
        transport=httpx.MockTransport(handler),
        queue_poll_attempts=1,
        queue_poll_interval=0,
    )

    result = client.trigger_job("job/backend/job/payment-service/job/release%252F1.0.0")

    assert result.queue_id == 77
    assert result.build_url is None
    assert result.status is BuildStatus.QUEUED
    assert result.message == "Build is queued in Jenkins: Waiting for next available executor"


def test_auth_failure_raises_jenkins_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    client = JenkinsClient(
        base_url="https://jenkins.example.com",
        user="tester",
        api_token="token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(JenkinsAuthError):
        client.trigger_job("job/backend/job/order-service-build", {"BRANCH": "feature/demo"})


def test_not_found_raises_jenkins_not_found_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/crumbIssuer/api/json":
            return httpx.Response(404)
        return httpx.Response(404)

    client = JenkinsClient(
        base_url="https://jenkins.example.com",
        user="tester",
        api_token="token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(JenkinsNotFoundError):
        client.trigger_job("job/backend/job/missing-service")


def test_server_error_raises_jenkins_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/crumbIssuer/api/json":
            return httpx.Response(404)
        return httpx.Response(503)

    client = JenkinsClient(
        base_url="https://jenkins.example.com",
        user="tester",
        api_token="token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(JenkinsUnavailableError):
        client.trigger_job("job/backend/job/order-service-build", {"BRANCH": "feature/demo"})


def test_timeout_raises_jenkins_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = JenkinsClient(
        base_url="https://jenkins.example.com",
        user="tester",
        api_token="token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(JenkinsUnavailableError):
        client.trigger_job("job/backend/job/order-service-build", {"BRANCH": "feature/demo"})
