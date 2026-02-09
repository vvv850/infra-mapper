"""Server data models for SSH connection and infrastructure info."""

from pathlib import Path
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from .container import Container
from .docker_stack import DockerStack


class ServerCredentials(BaseModel):
    """SSH credentials and connection information for a server."""

    hostname: str = Field(..., description="Server hostname or IP address")
    username: str = Field(..., description="SSH username")
    auth_method: Literal["key", "password"] = Field(
        default="key", description="Authentication method: 'key' or 'password'"
    )
    ssh_key_path: Optional[Path] = Field(
        default=None, description="Path to SSH private key (required when auth_method='key')"
    )
    port: int = Field(default=22, description="SSH port number")

    @model_validator(mode="after")
    def validate_auth_config(self) -> "ServerCredentials":
        """Ensure ssh_key_path is provided when auth_method is 'key'."""
        if self.auth_method == "key" and self.ssh_key_path is None:
            raise ValueError("ssh_key_path is required when auth_method is 'key'")
        return self

    @field_validator("ssh_key_path", mode="before")
    @classmethod
    def validate_ssh_key_path(cls, v: Optional[Path]) -> Optional[Path]:
        """Convert string to Path if needed."""
        if v is None:
            return None
        if isinstance(v, str):
            return Path(v).expanduser()
        return v.expanduser()

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port number is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v

    def __str__(self) -> str:
        """Format credentials as string for display."""
        auth = "key" if self.auth_method == "key" else "password"
        return f"{self.username}@{self.hostname}:{self.port} ({auth})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"ServerCredentials(hostname='{self.hostname}', username='{self.username}', "
            f"auth_method='{self.auth_method}', port={self.port})"
        )


class ServerInfo(BaseModel):
    """Complete server information including credentials and discovered containers."""

    credentials: ServerCredentials = Field(..., description="Server connection credentials")
    docker_stacks: List[DockerStack] = Field(
        default_factory=list, description="Docker Compose stacks on this server"
    )
    standalone_containers: List[Container] = Field(
        default_factory=list, description="Standalone containers (not in stacks)"
    )
    connection_status: str = Field(
        default="not_connected", description="Connection status"
    )
    error_message: Optional[str] = Field(None, description="Error message if connection failed")

    @property
    def total_containers(self) -> int:
        """Get total number of containers (stacks + standalone)."""
        stack_containers = sum(len(stack.containers) for stack in self.docker_stacks)
        return stack_containers + len(self.standalone_containers)

    @property
    def is_connected(self) -> bool:
        """Check if server connection was successful."""
        return self.connection_status == "success"

    def __str__(self) -> str:
        """Format server info as string for display."""
        status_icon = "✓" if self.is_connected else "✗"
        return (
            f"{status_icon} {self.credentials.hostname}: {len(self.docker_stacks)} stacks, "
            f"{len(self.standalone_containers)} standalone, "
            f"{self.total_containers} total containers"
        )

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"ServerInfo(hostname='{self.credentials.hostname}', "
            f"status='{self.connection_status}', "
            f"containers={self.total_containers})"
        )
