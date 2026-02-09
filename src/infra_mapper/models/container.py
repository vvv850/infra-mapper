"""Container data model for Docker containers."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from .port_mapping import PortMapping


class Container(BaseModel):
    """Represents a Docker container with all its metadata."""

    container_id: str = Field(..., description="Container ID (short form)")
    name: str = Field(..., description="Container name")
    image: str = Field(..., description="Docker image name and tag")
    status: str = Field(..., description="Container status (running, exited, etc.)")
    ports: List[PortMapping] = Field(default_factory=list, description="Port mappings")
    networks: List[str] = Field(default_factory=list, description="Connected networks")
    labels: Dict[str, str] = Field(default_factory=dict, description="Container labels")
    created_at: Optional[str] = Field(None, description="Container creation timestamp")

    @property
    def is_compose_managed(self) -> bool:
        """Check if container is managed by Docker Compose."""
        return "com.docker.compose.project" in self.labels

    @property
    def compose_project(self) -> Optional[str]:
        """Get Docker Compose project name if available."""
        return self.labels.get("com.docker.compose.project")

    @property
    def compose_service(self) -> Optional[str]:
        """Get Docker Compose service name if available."""
        return self.labels.get("com.docker.compose.service")

    def __str__(self) -> str:
        """Format container as string for display."""
        port_str = f", {len(self.ports)} ports" if self.ports else ""
        if self.is_compose_managed:
            return f"{self.name} ({self.image}) [Compose: {self.compose_project}]{port_str}"
        return f"{self.name} ({self.image}){port_str}"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"Container(id='{self.container_id}', name='{self.name}', "
            f"image='{self.image}', status='{self.status}')"
        )
