from pathlib import Path
import os

from jenkins_build_mcp.env_loader import load_env_file


def test_load_env_file_sets_variables(tmp_path: Path) -> None:
    env_path = tmp_path / ".env.local"
    env_path.write_text(
        """
# comment
JENKINS_BASE_URL=http://127.0.0.1:8080
JENKINS_USER=tester
JENKINS_API_TOKEN=secret
""".strip(),
        encoding="utf-8",
    )

    load_env_file(env_path)

    assert os.environ["JENKINS_BASE_URL"] == "http://127.0.0.1:8080"
    assert os.environ["JENKINS_USER"] == "tester"
    assert os.environ["JENKINS_API_TOKEN"] == "secret"
