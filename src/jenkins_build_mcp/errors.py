"""Error types for the Jenkins Build MCP server."""


class JenkinsBuildMcpError(Exception):
    """Base exception for the project."""


class ConfigError(JenkinsBuildMcpError):
    """Configuration loading or validation failed."""


class BuildValidationError(JenkinsBuildMcpError):
    """User-provided build input is invalid."""


class JenkinsError(JenkinsBuildMcpError):
    """Base exception for Jenkins API failures."""


class JenkinsAuthError(JenkinsError):
    """Jenkins authentication failed."""


class JenkinsNotFoundError(JenkinsError):
    """The configured Jenkins job could not be found."""


class JenkinsUnavailableError(JenkinsError):
    """Jenkins is unavailable or timed out."""
