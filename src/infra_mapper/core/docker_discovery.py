"""Docker container discovery service."""

import json
from typing import List, Dict, Tuple

from ..models.container import Container
from ..models.port_mapping import PortMapping
from ..models.docker_stack import DockerStack
from ..utils.exceptions import DockerNotFoundError, DockerPermissionError
from .ssh_manager import SSHConnectionManager


class DockerDiscoveryService:
    """Discovers Docker containers and their configurations on remote servers."""

    def __init__(self, ssh_manager: SSHConnectionManager):
        """
        Initialize Docker discovery service.

        Args:
            ssh_manager: Connected SSH manager instance
        """
        self.ssh = ssh_manager

    def discover_containers(self) -> Tuple[List[DockerStack], List[Container]]:
        """
        Discover all running containers and organize them into stacks and standalone.

        Returns:
            Tuple of (docker_stacks, standalone_containers)

        Raises:
            DockerNotFoundError: If Docker is not installed
            DockerPermissionError: If Docker requires permissions
        """
        # Verify Docker is available
        self._verify_docker_available()

        # Get all running containers
        containers = self._get_all_containers()

        # Separate into stacks and standalone
        stacks_dict: Dict[str, List[Container]] = {}
        standalone: List[Container] = []

        for container in containers:
            if container.is_compose_managed:
                project = container.compose_project
                if project not in stacks_dict:
                    stacks_dict[project] = []
                stacks_dict[project].append(container)
            else:
                standalone.append(container)

        # Convert to DockerStack objects
        stacks = [
            DockerStack(project_name=name, containers=containers)
            for name, containers in stacks_dict.items()
        ]

        return stacks, standalone

    def _verify_docker_available(self) -> None:
        """
        Verify Docker is installed and accessible.

        Raises:
            DockerNotFoundError: If Docker is not found
            DockerPermissionError: If Docker requires permissions
        """
        exit_code, stdout, stderr = self.ssh.execute_command("sudo docker --version")

        if exit_code != 0:
            if "permission denied" in stderr.lower():
                raise DockerPermissionError(
                    f"Docker permission denied on {self.ssh.hostname}. "
                    "User needs sudo access to Docker."
                )
            raise DockerNotFoundError(
                f"Docker not found on {self.ssh.hostname}. "
                "Please install Docker on the target server."
            )

    def _get_all_containers(self) -> List[Container]:
        """
        Get all running containers with full details.

        Returns:
            List of Container objects
        """
        # Get container IDs
        exit_code, stdout, stderr = self.ssh.execute_command(
            "sudo docker ps --format '{{.ID}}'"
        )

        if exit_code != 0 or not stdout.strip():
            return []

        container_ids = stdout.strip().split("\n")

        # Get full details for each container
        containers = []
        for container_id in container_ids:
            if not container_id.strip():
                continue

            try:
                container = self._inspect_container(container_id.strip())
                if container:
                    containers.append(container)
            except Exception as e:
                # Log but continue with other containers
                print(f"Warning: Failed to inspect container {container_id}: {e}")
                continue

        return containers

    def _inspect_container(self, container_id: str) -> Container:
        """
        Get detailed information about a specific container.

        Args:
            container_id: Docker container ID

        Returns:
            Container object with full details
        """
        exit_code, stdout, stderr = self.ssh.execute_command(
            f"sudo docker inspect {container_id}"
        )

        if exit_code != 0:
            raise RuntimeError(f"Failed to inspect container {container_id}: {stderr}")

        # Parse JSON output
        container_data = json.loads(stdout)[0]
        return self._parse_container_data(container_data)

    def _parse_container_data(self, data: Dict) -> Container:
        """
        Parse Docker inspect output into Container model.

        Args:
            data: Docker inspect JSON output

        Returns:
            Container object
        """
        # Extract port mappings
        ports = []
        port_bindings = data.get("NetworkSettings", {}).get("Ports", {})

        for container_port_proto, bindings in port_bindings.items():
            if not bindings:
                continue

            # Parse container port and protocol
            if "/" in container_port_proto:
                port_str, protocol = container_port_proto.split("/", 1)
            else:
                port_str, protocol = container_port_proto, "tcp"

            try:
                container_port = int(port_str)
            except ValueError:
                continue

            # Add each host binding
            for binding in bindings:
                try:
                    ports.append(
                        PortMapping(
                            container_port=container_port,
                            host_port=int(binding["HostPort"]),
                            protocol=protocol,
                            host_ip=binding.get("HostIp", "0.0.0.0"),
                        )
                    )
                except (KeyError, ValueError):
                    continue

        # Extract networks
        networks = list(data.get("NetworkSettings", {}).get("Networks", {}).keys())

        # Extract labels
        labels = data.get("Config", {}).get("Labels") or {}

        # Create container object
        return Container(
            container_id=data["Id"][:12],
            name=data["Name"].lstrip("/"),
            image=data["Config"]["Image"],
            status=data["State"]["Status"],
            ports=ports,
            networks=networks,
            labels=labels,
            created_at=data.get("Created"),
        )

    def __str__(self) -> str:
        """Format discovery service as string for display."""
        return f"DockerDiscovery({self.ssh.hostname})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return f"DockerDiscoveryService(ssh={self.ssh!r})"
