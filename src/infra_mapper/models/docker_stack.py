"""Docker Compose stack data model."""

from typing import List
from pydantic import BaseModel, Field

from .container import Container


class DockerStack(BaseModel):
    """Represents a Docker Compose stack (group of related containers)."""

    project_name: str = Field(..., description="Docker Compose project name")
    containers: List[Container] = Field(
        default_factory=list, description="Containers in this stack"
    )

    @property
    def total_ports(self) -> int:
        """Get total number of exposed ports across all containers in the stack."""
        return sum(len(container.ports) for container in self.containers)

    @property
    def container_count(self) -> int:
        """Get number of containers in the stack."""
        return len(self.containers)

    def __str__(self) -> str:
        """Format stack as string for display."""
        return (
            f"Stack '{self.project_name}': {self.container_count} containers, "
            f"{self.total_ports} ports"
        )

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"DockerStack(project_name='{self.project_name}', "
            f"containers={len(self.containers)})"
        )
