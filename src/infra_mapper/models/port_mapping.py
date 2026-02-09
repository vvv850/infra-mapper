"""Port mapping data model for Docker containers."""

from pydantic import BaseModel, Field


class PortMapping(BaseModel):
    """Represents a port mapping from container to host."""

    container_port: int = Field(..., description="Port inside the container")
    host_port: int = Field(..., description="Port on the host machine")
    protocol: str = Field(default="tcp", description="Protocol (tcp/udp)")
    host_ip: str = Field(default="0.0.0.0", description="Host IP address")

    def __str__(self) -> str:
        """Format port mapping as string for display."""
        if self.host_ip == "0.0.0.0":
            return f"{self.host_port} → {self.container_port}/{self.protocol}"
        return f"{self.host_ip}:{self.host_port} → {self.container_port}/{self.protocol}"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"PortMapping(host_ip='{self.host_ip}', host_port={self.host_port}, "
            f"container_port={self.container_port}, protocol='{self.protocol}')"
        )
