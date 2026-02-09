"""Custom exceptions for the Infrastructure Mapper application."""


class InfraMapperError(Exception):
    """Base exception for all Infrastructure Mapper errors."""

    pass


class SSHConnectionError(InfraMapperError):
    """Raised when SSH connection fails."""

    pass


class DockerNotFoundError(InfraMapperError):
    """Raised when Docker is not found on the target server."""

    pass


class DockerPermissionError(InfraMapperError):
    """Raised when Docker commands require elevated permissions."""

    pass


class ConfigurationError(InfraMapperError):
    """Raised when configuration is invalid or cannot be loaded."""

    pass
