"""Mermaid diagram generator for infrastructure visualization."""

from datetime import datetime
from pathlib import Path
from typing import List, Dict

from ..models.server import ServerInfo
from ..models.docker_stack import DockerStack
from ..models.container import Container


class MermaidGenerator:
    """Generates Mermaid diagrams from infrastructure data."""

    def __init__(self):
        """Initialize Mermaid generator."""
        self.node_counter = 0
        self.node_map: Dict[str, str] = {}

    def generate(self, servers: List[ServerInfo]) -> str:
        """
        Generate Mermaid diagram from server information.

        Args:
            servers: List of server information objects

        Returns:
            Mermaid diagram as string
        """
        # Reset node mapping for fresh generation
        self.node_counter = 0
        self.node_map = {}

        lines = ["```mermaid", "graph LR"]

        # Add class definitions for styling
        lines.extend(self._generate_styles())

        for server in servers:
            server_hostname = server.credentials.hostname

            if server.connection_status != "success":
                # Show failed servers with different styling
                server_id = self._get_node_id("server", server_hostname)
                lines.append(f"    {server_id}[\"🖥️ {server_hostname} (failed)\"]")
                lines.append(f"    class {server_id} serverFailed")
                continue

            server_id = self._get_node_id("server", server_hostname)
            lines.append(f"    {server_id}[\"🖥️ {server_hostname}\"]")
            lines.append(f"    class {server_id} server")

            # Add Docker stacks
            for stack in server.docker_stacks:
                stack_lines = self._generate_stack(server_id, server_hostname, stack)
                lines.extend(stack_lines)

            # Add standalone containers
            for container in server.standalone_containers:
                container_lines = self._generate_container(
                    server_id, server_hostname, container, is_standalone=True
                )
                lines.extend(container_lines)

        lines.append("```")
        return "\n".join(lines)

    def _generate_styles(self) -> List[str]:
        """Generate CSS class definitions for Mermaid styling."""
        return [
            "    classDef server fill:#b3d9ff,stroke:#01579b,stroke-width:3px,color:#000",
            "    classDef serverFailed fill:#ffcdd2,stroke:#c62828,stroke-width:2px,color:#000",
            "    classDef stack fill:#ffe0b2,stroke:#e65100,stroke-width:2px,color:#000",
            "    classDef container fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#000",
            "    classDef standalone fill:#e1bee7,stroke:#6a1b9a,stroke-width:2px,color:#000",
            "    classDef port fill:#f8bbd0,stroke:#c2185b,stroke-width:1px,color:#000",
            "",
        ]

    def _generate_stack(self, parent_id: str, server_hostname: str, stack: DockerStack) -> List[str]:
        """
        Generate nodes for a Docker Compose stack.

        Args:
            parent_id: Parent server node ID
            server_hostname: Hostname of the server (for unique node IDs)
            stack: Docker stack object

        Returns:
            List of Mermaid diagram lines
        """
        lines = []
        stack_id = self._get_node_id("stack", f"{server_hostname}_{stack.project_name}")

        lines.append(f"    {parent_id} --> {stack_id}")
        lines.append(f"    {stack_id}[\"📦 Stack: {stack.project_name}\"]")
        lines.append(f"    class {stack_id} stack")

        for container in stack.containers:
            container_lines = self._generate_container(
                stack_id, server_hostname, container, is_standalone=False
            )
            lines.extend(container_lines)

        return lines

    def _generate_container(
        self, parent_id: str, server_hostname: str, container: Container, is_standalone: bool
    ) -> List[str]:
        """
        Generate nodes for a container.

        Args:
            parent_id: Parent node ID (server or stack)
            server_hostname: Hostname of the server (for unique node IDs)
            container: Container object
            is_standalone: Whether container is standalone (not in stack)

        Returns:
            List of Mermaid diagram lines
        """
        lines = []
        container_id = self._get_node_id("container", f"{server_hostname}_{container.name}")

        icon = "🐳" if is_standalone else "🔷"
        # Sanitize container name and image for Mermaid
        safe_name = self._sanitize_text(container.name)
        safe_image = self._sanitize_text(container.image)

        lines.append(f"    {parent_id} --> {container_id}")
        lines.append(f'    {container_id}["{icon} {safe_name}<br/><small>{safe_image}</small>"]')

        if is_standalone:
            lines.append(f"    class {container_id} standalone")
        else:
            lines.append(f"    class {container_id} container")

        # Add port mappings (deduplicate IPv4/IPv6)
        seen_ports = {}
        for port in container.ports:
            port_key = f"{port.host_port}_{port.container_port}_{port.protocol}"

            if port_key not in seen_ports:
                # First time seeing this port mapping
                port_id = self._get_node_id("port", f"{server_hostname}_{container.name}_{port_key}")
                port_display = f"{port.host_port} → {port.container_port}/{port.protocol}"

                lines.append(f"    {container_id} --> {port_id}")
                lines.append(f'    {port_id}["🔌 {port_display}"]')
                lines.append(f"    class {port_id} port")

                # Add clickable link to access the service
                # Use https for port 443, http for everything else
                protocol = "https" if port.host_port == 443 else "http"
                url = f"{protocol}://{server_hostname}:{port.host_port}"
                lines.append(f'    click {port_id} href "{url}"')

                seen_ports[port_key] = port_id

        return lines

    def _get_node_id(self, prefix: str, name: str) -> str:
        """
        Get or create unique node ID for Mermaid diagram.

        Args:
            prefix: Node type prefix (server, stack, container, port)
            name: Node name

        Returns:
            Unique node ID
        """
        # Create a safe key from name
        safe_name = "".join(c if c.isalnum() else "_" for c in name)
        key = f"{prefix}_{safe_name}"

        if key not in self.node_map:
            self.node_map[key] = f"{prefix}{self.node_counter}"
            self.node_counter += 1

        return self.node_map[key]

    def _sanitize_text(self, text: str) -> str:
        """
        Sanitize text for Mermaid diagram (escape special characters).

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text
        """
        # Replace characters that might break Mermaid syntax
        replacements = {
            '"': "'",
            "[": "(",
            "]": ")",
            "{": "(",
            "}": ")",
            "|": "/",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def save_to_file(
        self, content: str, filename: str = "infrastructure.md", output_dir: Path = None
    ) -> Path:
        """
        Save diagram to markdown file.

        Args:
            content: Mermaid diagram content
            filename: Output filename (default: infrastructure.md)
            output_dir: Output directory (default: current directory)

        Returns:
            Path to saved file
        """
        if output_dir is None:
            output_path = Path(filename)
        else:
            output_path = Path(output_dir) / filename

        # Create full document with metadata
        document = f"""# Docker Infrastructure Map

*Generated by Infrastructure Mapper on {self._get_timestamp()}*

## Overview

This diagram shows the current state of Docker containers across all configured servers.

{content}

## Legend

- 🖥️ **Server**: Physical or virtual server
- 📦 **Stack**: Docker Compose project (group of related containers)
- 🐳 **Standalone Container**: Individual Docker container (not part of a stack)
- 🔷 **Stack Container**: Container managed by Docker Compose
- 🔌 **Port Mapping**: Exposed port (format: host_port → container_port/protocol)

## Notes

- Only running containers are shown
- Port mappings show how services are exposed on the host
- Containers in the same stack share the same Docker Compose project

---

*To update this diagram, run `infra-mapper` again*
"""

        output_path.write_text(document, encoding="utf-8")
        return output_path

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in readable format."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def __str__(self) -> str:
        """Format generator as string for display."""
        return "MermaidGenerator"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return f"MermaidGenerator(nodes={self.node_counter})"
